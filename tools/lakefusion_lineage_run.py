#!/usr/bin/env python3
"""Local provenance acceptance, retaining fresh evidence and a remote input fixture."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

from lakematch.mastering.lineage import entity_detail
from lakematch.mastering.lineage_publication import LocalLineageStore
from lakematch.mastering.registry import apply_migrations
from lakefusion_lineage_fixture import dataset
from local_postgres import LocalPostgres

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tests-output", required=True, type=Path)
    parser.add_argument("--fixture-output", required=True, type=Path)
    args = parser.parse_args()
    if any(p.exists() for p in (args.output, args.tests_output, args.fixture_output)):
        parser.error("Fresh output paths required")
    started = time.monotonic()
    report = {"phase": "LF-B", "packages": ["LM-006", "LM-009 foundation"], "status": "running",
              "started_at": datetime.now(timezone.utc).isoformat(), "cloud_calls": 0,
              "confirmation_materialized": False, "cleanup": "pending"}
    for p in (args.output, args.tests_output, args.fixture_output):
        p.parent.mkdir(parents=True, exist_ok=True)
    try:
        freeze = json.loads((ROOT / "spec/lakefusion/frozen/phase-a-v0.1.json").read_text())
        assert all(sha(ROOT / p) == h for p, h in freeze["files"].items())
        report["phase_a_freeze_verified"] = True
        paths = [*sorted((ROOT / "src/lakematch/mastering").glob("*.py")),
                 ROOT / "src/lakematch/publication.py", ROOT / "src/lakematch/delta_publication.py",
                 *sorted((ROOT / "app/migrations/mastering").glob("*.sql")),
                 *sorted((ROOT / "tools").glob("lakefusion_lineage*.py")),
                 ROOT / "tools/check_changes.py", ROOT / "tests/test_mastering_lineage.py",
                 ROOT / "spec/lakefusion/LINEAGE.md", ROOT / "bench/lakefusion/LINEAGE_PLAN.md"]
        paths.append(ROOT / "bench/lakefusion/LINEAGE_RETRY_PLAN.md")
        report["source_hashes"] = {str(p.relative_to(ROOT)): sha(p) for p in paths}
        command = [sys.executable, "-m", "pytest", "-q", "tests/test_mastering_contracts.py", "tests/test_mastering_policy.py",
                   "tests/test_mastering_retrieval.py", "tests/test_mastering_execution.py", "tests/test_mastering_identity_contract.py",
                   "tests/test_mastering_survivorship.py", "tests/test_mastering_lineage.py", "tests/test_publication.py",
                   "tests/test_config.py", "tests/postgres", "tests/test_source_hygiene.py", "tests/test_source_scan.py",
                   "--junitxml=" + str(args.tests_output)]
        report["test_command"] = command
        tests = subprocess.run(command, cwd=ROOT, env={**os.environ, "LAKEMATCH_TEST_POSTGRES": "1"}, timeout=180)
        suites = list(ET.parse(args.tests_output).getroot().iter("testsuite"))
        report["tests"] = {k: sum(int(s.attrib[k]) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
        if tests.returncode or any(report["tests"][k] for k in ("failures", "errors", "skipped")):
            raise RuntimeError("Required provenance checks did not all pass")
        with LocalPostgres() as server, tempfile.TemporaryDirectory(prefix="lm-lineage-") as directory:
            with server.connect() as connection:
                apply_migrations(connection, ROOT / "app/migrations/mastering")
            data = dataset(server.connect)
            store = LocalLineageStore(Path(directory) / "published")
            first = store.publish("first", data["first"], data["context"], expected_previous=None)
            old = store.read("first")
            second = store.publish("second", data["second"], data["context"], expected_previous="first")
            new = store.current()
            server.restart()
            reopened = LocalLineageStore(store.root)
            assert reopened.read("first") == old and reopened.current() == new
            assert reopened.publish("first", data["first"], data["context"], expected_previous=None)["reused"]
            assert reopened.current() == new
            before = entity_detail(old, data["cedar_id"])
            after = entity_detail(new, data["cedar_id"])
            assert before["values"]["address_line1"] == "10 Example Avenue"
            assert after["values"]["address_line1"] == "99 Updated Example Avenue"
            assert (before["revision"], after["revision"], before["identity_revision"], after["identity_revision"]) == (1, 2, 1, 1)
            data["expected_snapshots"] = {"first": old["snapshot_sha256"], "second": new["snapshot_sha256"]}
            data["source_hashes"] = report["source_hashes"]
            args.fixture_output.write_text(json.dumps(data, sort_keys=True) + "\n")
            report.update(snapshot_hashes=data["expected_snapshots"], counts=new["counts"], historical_restart_exact=True,
                          old_batch_retry_does_not_rewind=True, publications=[first["batch_id"], second["batch_id"]],
                          fixture={"path": str(args.fixture_output), "sha256": sha(args.fixture_output)},
                          sample={"master_id": data["cedar_id"], "old_revision": before["revision"], "new_revision": after["revision"],
                                  "identity_revision": after["identity_revision"], "old_address": before["values"]["address_line1"],
                                  "new_address": after["values"]["address_line1"], "old_field": before["fields"]["address_line1"],
                                  "new_field": after["fields"]["legal_name"]})
        report["cleanup"] = server.cleanup + "; owned local publication directory removed"
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report["main_process_peak_rss_bytes"] = peak if sys.platform == "darwin" else peak * 1024
        assert report["main_process_peak_rss_bytes"] <= 4 * 1024**3
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
    finally:
        report.update(ended_at=datetime.now(timezone.utc).isoformat(), wall_seconds=round(time.monotonic() - started, 3))
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k: report.get(k) for k in ("status", "tests", "counts", "cleanup", "error")}), flush=True)
    return int(report["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
