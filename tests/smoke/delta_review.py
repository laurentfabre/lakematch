"""Opt-in retry check using disposable owned Delta tables, never real review labels."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "app/src")]
from workspace_support import APP, NAMESPACE, WAREHOUSE_NAME, client
from lakematch_review.backend.models import PairOut, ReviewIn
from lakematch_review.backend.store import Conflict, DeltaStore, TABLE_DDL, pair_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    w = client(args.profile)
    if w.apps.get(APP).compute_status.state.value != "STOPPED":
        raise RuntimeError("Run this separate smoke only after stopping the owned app")
    warehouses = [x for x in w.warehouses.list() if x.name == WAREHOUSE_NAME]
    if len(warehouses) != 1:
        raise RuntimeError("Expected exactly one owned warehouse")
    warehouse = w.warehouses.get(warehouses[0].id)
    if warehouse.num_active_sessions:
        raise RuntimeError("Owned warehouse has active sessions")
    prefix = "lm_deploy_probe_" + uuid4().hex[:12] + "_"
    deadline = time.monotonic() + 600
    cleaning = False

    class ProbeStore(DeltaStore):
        def query(self, statement, params=None):
            if not cleaning and time.monotonic() >= deadline:
                raise TimeoutError("Delta probe exceeded its 600-second work deadline")
            print("Delta probe:", statement.split()[0], flush=True)
            return super().query(statement, params)

        def table(self, name):
            if name not in TABLE_DDL:
                raise ValueError("Unknown probe table")
            return ".".join(f"`{part}`" for part in [*NAMESPACE.split("."), prefix + name])

    store = ProbeStore(w, warehouse.id, NAMESPACE)
    report = {"observed_at": datetime.now(timezone.utc).isoformat(), "profile": args.profile,
              "warehouse_id": warehouse.id, "prefix": prefix, "status": "running", "cleanup": {}}
    created = []
    try:
        w.warehouses.start_and_wait(warehouse.id, timeout=timedelta(minutes=5))
        for name, ddl in TABLE_DDL.items():
            created.append(name)
            store.query(f"CREATE TABLE {store.table(name)} ({ddl}) USING DELTA")
        pair = PairOut(pair_id=pair_key("redeployment-smoke", "a", "b"), a_id="a", b_id="b",
                       left={"name": "Synthetic A"}, right={"name": "Synthetic A"},
                       model_version="redeployment-smoke", probability=.5, threshold=.5)
        store.enqueue(pair)
        store.enqueue(pair)
        assert store.queue(1) == [pair]
        body = ReviewIn(request_id=uuid4().hex, pair_id=pair.pair_id, model_version=pair.model_version,
                        decision="match", reason="Disposable deployment retry check")
        saved = store.review(body, "deployment-smoke")
        for _ in range(2):
            store.insert_once("review_labels", dict(request_id=saved.request_id, pair_id=saved.pair_id,
                              payload=saved.model_dump_json()), ("request_id", "pair_id"))
        fresh = ProbeStore(w, warehouse.id, NAMESPACE)
        assert fresh.review(body, "deployment-smoke") == saved
        assert fresh.reviews() == [saved]
        assert fresh.queue(1) == []
        fresh.set_metadata("probe", 7)
        fresh.set_metadata("probe", 7)
        try:
            fresh.set_metadata("probe", 8)
        except Conflict:
            pass
        else:
            raise AssertionError("Changed immutable metadata was accepted")
        report.update(status="passed", review_rows=1, merge_replays=2,
                      stable_receipt_after_reload=True, changed_metadata_rejected=True, int_limit_passed=True)
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        cleaning = True
        errors = []
        for name in reversed(created):
            try:
                store.query(f"DROP TABLE IF EXISTS {store.table(name)}")
                report["cleanup"][name] = "dropped disposable table"
            except Exception as error:
                errors.append(str(error))
        try:
            stopped = w.warehouses.stop_and_wait(warehouse.id, timeout=timedelta(minutes=3))
            report["cleanup"]["warehouse"] = stopped.state.value
        except Exception as error:
            errors.append(str(error))
        if errors:
            report.update(status="cleanup_failed", cleanup_errors=errors)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
        if errors:
            raise RuntimeError("; ".join(errors))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
