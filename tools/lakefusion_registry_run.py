#!/usr/bin/env python3
"""Generate bounded LF-B registry experiment evidence; not a read-only verifier."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from lakematch.mastering.contracts import DomainContract, SourceMapping, digest
from lakematch.mastering.execution import ExecutionSpec, preview_mapping, retrieval_digest
from lakematch.mastering.registry import PostgresRegistry, apply_migrations
from lakematch.mastering.retrieval import Limits
from local_postgres import LocalPostgres

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tests-output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.tests_output.exists():
        parser.error("Use fresh evidence paths; earlier receipts remain immutable")
    started = time.monotonic()
    report = {"phase": "LF-B", "packages": ["LM-002", "LM-003"], "status": "running",
              "started_at": datetime.now(timezone.utc).isoformat(),
              "driver": {"psycopg": version("psycopg"), "psycopg-binary": version("psycopg-binary")},
              "dependency_lock_sha256": sha(ROOT / "requirements-postgres.lock"),
              "confirmation_materialized": False, "cloud_calls": 0,
              "actor_source": "synthetic internal fixtures; not authenticated application users",
              "cleanup": "not started"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.tests_output.parent.mkdir(parents=True, exist_ok=True)
    try:
        command = [sys.executable, "-m", "pytest", "-q", "tests/test_mastering_contracts.py",
                   "tests/test_mastering_policy.py", "tests/test_mastering_retrieval.py",
                   "tests/test_mastering_execution.py", "tests/test_config.py", "tests/test_source_hygiene.py",
                   "tests/postgres", "--junitxml=" + str(args.tests_output)]
        tests = subprocess.run(command, env={**os.environ, "LAKEMATCH_TEST_POSTGRES": "1"}, timeout=120)
        suites = list(ET.parse(args.tests_output).getroot().iter("testsuite"))
        report["tests"] = {k: sum(int(s.attrib[k]) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
        if tests.returncode or any(report["tests"][k] for k in ("failures", "errors", "skipped")):
            raise RuntimeError("Required registry checks did not all pass")
        freeze = json.loads((ROOT / "spec/lakefusion/frozen/phase-a-v0.1.json").read_text())
        if any(sha(ROOT / path) != value for path, value in freeze["files"].items()):
            raise RuntimeError("A frozen Phase A contract changed")
        fixture = ROOT / "examples/mastering/company_pilot"
        domain = DomainContract.from_dict(json.loads((fixture / "domain.json").read_text()))
        mappings = [SourceMapping.from_dict(json.loads((fixture / f"{s}_mapping.json").read_text()), domain)
                    for s in ("erp_vendor", "crm_account")]
        left, right = mappings
        spec = ExecutionSpec("company_validation", 1, domain.domain_id, domain.version, domain.sha256,
                             left.source_id, left.version, left.sha256, right.source_id, right.version, right.sha256,
                             "identifier_name", retrieval_digest(), Limits(seconds=120))
        manifest = json.loads((ROOT / "bench/lakefusion/company-pilot-v0.1.json").read_text())
        source = ROOT / "data/lakefusion/company-pilot-v0.1"
        inputs = {}
        report["input_hashes"] = {}
        for kind in ("erp_vendor", "crm_account", "truth"):
            name = f"validation.{kind}.jsonl"
            path = source / name
            if sha(path) != manifest["files"][name]["sha256"]:
                raise RuntimeError("Validation input checksum mismatch")
            report["input_hashes"][name] = sha(path)
            inputs[kind] = [json.loads(line) for line in path.read_text().splitlines()]
        previous = json.loads((ROOT / "bench/lakefusion/candidates-validation-v0.1.json").read_text())
        baseline = next(a for a in previous["alternatives"] if a["alternative"] == spec.retrieval_alternative)
        raw = ROOT / baseline["raw_artifact"]
        if sha(raw) != baseline["raw_sha256"]:
            raise RuntimeError("Previous candidate artifact checksum mismatch")
        expected_rows = json.loads(raw.read_text())["rows"]
        with LocalPostgres() as postgres:
            report["postgres"] = subprocess.check_output([postgres.binaries["postgres"], "--version"], text=True).strip()
            with postgres.connect() as connection:
                report["migrations"] = apply_migrations(connection, ROOT / "app/migrations/mastering")
            registry = PostgresRegistry(postgres.connect)
            registry.submit_domain(domain, actor="fixture_engineer", expected_latest=0)
            registry.transition("domain", "company", "company", 1, state="approved", expected_revision=1,
                                actor="fixture_approver", reason="Reviewed frozen company domain")
            for mapping in mappings:
                registry.submit_mapping(mapping, actor="fixture_engineer", expected_latest=0)
                registry.transition("mapping", "company", mapping.source_id, 1, state="approved", expected_revision=1,
                                    actor="fixture_approver", reason="Reviewed frozen mapping and source preview")
            registry.submit_execution(spec, actor="fixture_engineer", expected_latest=0)
            registry.transition("execution", "company", spec.execution_id, 1, state="approved", expected_revision=1,
                                actor="fixture_approver", reason="Pin existing cheapest-passing validation retrieval; retain known misses")
            before = registry.resolve("company", spec.execution_id, 1).manifest()
            postgres.restart()
            result = registry.run_candidates("company", spec.execution_id, 1, inputs["erp_vendor"], inputs["crm_account"])
            if before != result["binding"] or result["candidate_rows_sha256"] != digest(expected_rows):
                raise AssertionError("Persisted binding or candidate rows changed")
            known = {t["erp_key"]: t["crm_key"] for t in inputs["truth"]}
            found = sum(known[row["left_id"]] in {c["right_id"] for c in row["candidates"]} for row in result["result"]["rows"])
            assert (found, result["result"]["retained_pairs"]) == (baseline["found_positives"], baseline["retained_pairs"])
            preview = preview_mapping(right, json.loads((fixture / "fixture.json").read_text())["sources"]["crm_account"])
            report.update(binding=result["binding"], input_snapshots=result["input_snapshots"],
                          candidate_rows_sha256=result["candidate_rows_sha256"], baseline_candidate_rows_sha256=digest(expected_rows),
                          baseline_commit="e4cf355", candidates_equal=True, approvals_survive_restart=True,
                          candidate_recall=found / len(known), known_positives=len(known), found_positives=found,
                          retained_pairs=result["result"]["retained_pairs"], retrieval_wall_seconds=result["result"]["wall_seconds"],
                          crm_integration_preview={"input_rows": preview["input_rows"], "accepted": len(preview["accepted"]), "errors": preview["errors"]})
        report["cleanup"] = postgres.cleanup
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report["process_peak_rss_bytes"] = peak if sys.platform == "darwin" else peak * 1024
        if report["process_peak_rss_bytes"] > 4 * 1024**3:
            raise RuntimeError("Observed process memory exceeded the approved limit")
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
    finally:
        report.update(ended_at=datetime.now(timezone.utc).isoformat(), wall_seconds=round(time.monotonic() - started, 3))
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k: report.get(k) for k in ("status", "tests", "candidate_recall", "candidates_equal", "cleanup", "error")}), flush=True)
    return int(report["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
