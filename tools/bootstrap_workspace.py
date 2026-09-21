"""Check/create campaign prerequisites; preserve existing tables, labels and inputs."""
import argparse
from datetime import timedelta
import json
from pathlib import Path
import re
import sys

from workspace_support import APP, CATALOG, NAMESPACE, SCHEMA, VOLUME, WAREHOUSE_NAME, client, sql

ROOT = Path(__file__).resolve().parents[1]


def main():
    from databricks.sdk.errors import NotFound
    from databricks.sdk.service.catalog import VolumeType
    from databricks.sdk.service.sql import (CreateWarehouseRequestWarehouseType, EndpointTags, EndpointTagPair)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--apply", action="store_true", help="Create missing prerequisites")
    parser.add_argument("--review-tables", action="store_true", help="Create empty app tables/grants after app bundle deploy")
    args = parser.parse_args()
    if args.review_tables and not args.apply:
        parser.error("--review-tables requires --apply")
    w = client(args.profile)
    report = {"profile": args.profile, "created": [], "missing": [], "schema": NAMESPACE}
    # The workspace/catalog and their managed storage are external prerequisites.
    w.catalogs.get(CATALOG)
    for key, get, create in (
        (NAMESPACE, lambda: w.schemas.get(NAMESPACE), lambda: w.schemas.create(
            SCHEMA, CATALOG, comment="lakematch campaign; public/synthetic corpora only; owned by Laurent Fabre")),
        (VOLUME, lambda: w.volumes.read(VOLUME), lambda: w.volumes.create(
            CATALOG, SCHEMA, "artifacts", VolumeType.MANAGED,
            comment="Public/synthetic experiment artifacts and model staging")),
    ):
        try:
            get()
        except NotFound:
            if args.apply:
                create()
                report["created"].append(key)
            else:
                report["missing"].append(key)
    warehouses = [item for item in w.warehouses.list() if item.name == WAREHOUSE_NAME]
    if len(warehouses) > 1:
        raise RuntimeError("Ambiguous owned warehouse name")
    if not warehouses and args.apply:
        pending = w.warehouses.create(
            name=WAREHOUSE_NAME, cluster_size="2X-Small", auto_stop_mins=10,
            min_num_clusters=1, max_num_clusters=1, enable_serverless_compute=True,
            enable_photon=True, warehouse_type=CreateWarehouseRequestWarehouseType.PRO,
            tags=EndpointTags(custom_tags=[EndpointTagPair(key="campaign", value="lakematch-20260919")]))
        warehouse_id = pending.response.id
        try:
            pending.result(timeout=timedelta(minutes=5))
        finally:
            w.warehouses.stop_and_wait(warehouse_id, timeout=timedelta(minutes=3))
        warehouses = [w.warehouses.get(warehouse_id)]
        report["created"].append("warehouse:" + warehouse_id)
    if not warehouses:
        report["missing"].append("owned warehouse")
    else:
        warehouse = warehouses[0]
        report["warehouse_id"] = warehouse.id
        if not warehouse.enable_serverless_compute or warehouse.max_num_clusters != 1:
            raise RuntimeError("Owned warehouse configuration differs; review before changing it")
    if args.review_tables:
        # No seed data, deletes, overwrite, or publication/benchmark runs here.
        app = w.apps.get(APP)
        principal = app.service_principal_client_id
        if not principal or not re.fullmatch(r"[0-9a-f-]{36}", principal):
            raise RuntimeError("Wait for the app service principal to finish provisioning")
        if app.compute_status.state.value != "STOPPED":
            raise RuntimeError("Stop the app before preparing its review store")
        sys.path.insert(0, str(ROOT / "app/src"))
        from lakematch_review.backend.store import TABLE_DDL
        was_stopped = warehouse.state.value == "STOPPED"
        try:
            if was_stopped:
                w.warehouses.start_and_wait(warehouse.id, timeout=timedelta(minutes=5))
            for name, ddl in TABLE_DDL.items():
                sql(w, warehouse.id, f"CREATE TABLE IF NOT EXISTS {NAMESPACE}.{name} ({ddl}) USING DELTA")
            sql(w, warehouse.id, f"GRANT USE CATALOG ON CATALOG {CATALOG} TO `{principal}`")
            sql(w, warehouse.id, f"GRANT USE SCHEMA ON SCHEMA {NAMESPACE} TO `{principal}`")
            for name in TABLE_DDL:
                privileges = "SELECT, MODIFY" if name == "review_labels" else "SELECT"
                sql(w, warehouse.id, f"GRANT {privileges} ON TABLE {NAMESPACE}.{name} TO `{principal}`")
            report["review_tables"] = "created if absent; existing rows preserved; app grants applied"
        finally:
            if was_stopped:
                w.warehouses.stop_and_wait(warehouse.id, timeout=timedelta(minutes=3))
    print(json.dumps(report, indent=2))
    if report["missing"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
