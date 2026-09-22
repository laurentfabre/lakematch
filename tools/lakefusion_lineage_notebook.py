# Databricks notebook source
"""One bounded synthetic provenance proof; drops only its fresh owned tables."""
import hashlib
import json
from pathlib import Path
import re
import sys
import time

dbutils.widgets.text("source_root", "")
dbutils.widgets.text("namespace", "")
source_root = Path(dbutils.widgets.get("source_root"))
namespace = dbutils.widgets.get("namespace")
if not re.fullmatch(r"lfb_lineage_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}", namespace):
    raise ValueError("Fresh experiment namespace required")
sys.path.insert(0, str(source_root / "src"))

from lakematch.mastering.lineage import build_snapshot, entity_detail
from lakematch.mastering.lineage_delta import DeltaLineageStore, frames

started = time.monotonic()
schema = "gdpr2_catalog.lakematch_20260919"
store = DeltaLineageStore(spark, schema, namespace)
prefix = store.publisher.prefix
pattern = re.compile(re.escape(prefix) + r"_(commits|[0-9a-f]{32}_(golden_records|attribute_lineage|source_versions|memberships|contracts))")
owned = False
report = {"status": "running", "namespace": namespace, "schema": schema, "prefix": prefix,
          "observed_cost": None, "cost_status": "unreconciled", "cleanup": {}, "source_hashes": {}}


def owned_tables():
    return sorted(schema + "." + row.tableName for row in spark.sql(f"SHOW TABLES IN {schema}").collect()
                  if pattern.fullmatch(row.tableName))


try:
    assert not owned_tables(), "Namespace unexpectedly exists; do not change or clean it"
    owned = True
    fixture = source_root / "fixture.json"
    data = json.loads(fixture.read_text())
    report["fixture_sha256"] = hashlib.sha256(fixture.read_bytes()).hexdigest()
    for name, expected in data["source_hashes"].items():
        if name.startswith("src/"):
            observed = hashlib.sha256((source_root / name).read_bytes()).hexdigest()
            report["source_hashes"][name] = observed
            assert observed == expected, "Remote source content differs: " + name
    first = store.publish("first", data["first"], data["context"], expected_previous=None)
    old = store.read("first")
    assert old["snapshot_sha256"] == data["expected_snapshots"]["first"]
    class InterruptedProjection:
        @property
        def write(self):
            raise RuntimeError("planned interruption after one Delta table")
    def interrupted(previous):
        assert previous["batch_id"] == "first"
        snapshot = build_snapshot("second", data["second"], data["context"], expected_previous="first", previous=old)
        staged = frames(spark, snapshot)
        return {"golden_records": staged["golden_records"], "attribute_lineage": InterruptedProjection()}, {}
    try:
        store.publisher.publish("interrupted", "0" * 64, interrupted)
        raise AssertionError("Planned interruption did not occur")
    except RuntimeError as error:
        assert str(error) == "planned interruption after one Delta table"
        report["planned_interruption"] = str(error)
    assert store.current() == old
    assert store.read("interrupted") is None
    assert len(owned_tables()) == 7
    second = store.publish("second", data["second"], data["context"], expected_previous="first")
    assert len(second["recovered_tables"]) == 1
    reopened = DeltaLineageStore(spark, schema, namespace)
    new = reopened.current()
    assert new["snapshot_sha256"] == data["expected_snapshots"]["second"]
    assert reopened.read("first") == old
    retry = reopened.publish("first", data["first"], data["context"], expected_previous=None)
    assert retry["reused"] and retry["attempt"] == first["attempt"]
    assert reopened.publisher.current()["batch_id"] == "second"
    from lakematch.mastering import lineage
    original_calculate = lineage.calculate
    def unavailable(*args, **kwargs):
        raise RuntimeError("current scalar implementation unavailable")
    try:
        lineage.calculate = unavailable
        assert reopened.publish("first", data["first"], data["context"], expected_previous=None)["reused"]
        try:
            reopened.publish("new", data["second"], data["context"], expected_previous="second")
            raise AssertionError("New publication skipped required scalar replay")
        except RuntimeError as error:
            assert str(error) == "current scalar implementation unavailable"
        assert reopened.read("new") is None
    finally:
        lineage.calculate = original_calculate
    before, after = (entity_detail(s, data["cedar_id"]) for s in (old, new))
    assert before["values"]["address_line1"] == "10 Example Avenue"
    assert after["values"]["address_line1"] == "99 Updated Example Avenue"
    assert after["fields"]["legal_name"]["reason"] == "approved_override"
    assert (before["revision"], after["revision"], before["identity_revision"], after["identity_revision"]) == (1, 2, 1, 1)
    atlas = entity_detail(new, data["atlas_id"])
    assert any(s["deleted"] for s in atlas["sources"])
    assert len(owned_tables()) == 11
    report.update(status="passed", local_delta_hash_parity=True, historical_read_exact=True,
                  committed_retry_without_current_code=True, new_publication_requires_current_code=True,
                  partial_tables_invisible=True, abandoned_table_recovered=True, old_retry_preserves_head=True,
                  snapshot_hashes={"first": old["snapshot_sha256"], "second": new["snapshot_sha256"]},
                  counts=new["counts"], publications=[first, second],
                  sample={"master_id": data["cedar_id"], "old_address": before["values"]["address_line1"],
                          "new_address": after["values"]["address_line1"], "override": after["fields"]["legal_name"]["winner"]})
except Exception as error:
    report.update(status="failed", error=f"{type(error).__name__}: {error}")
finally:
    if owned:
        removed, errors = [], []
        try:
            tables = owned_tables()
            assert len(tables) <= 16, "Owned table bound exceeded"
            for table in tables:
                try:
                    spark.sql(f"DROP TABLE {table}").collect()
                    removed.append(table)
                except Exception as error:
                    errors.append(f"{table}: {type(error).__name__}: {error}")
            remaining = owned_tables()
            report["cleanup"] = {"removed": removed, "remaining": remaining, "errors": errors}
            if remaining or errors:
                report["status"] = "failed"
        except Exception as error:
            report.update(status="failed", cleanup={"errors": [f"{type(error).__name__}: {error}"]})
    report["wall_seconds"] = round(time.monotonic() - started, 3)

dbutils.notebook.exit(json.dumps(report, sort_keys=True))
