#!/usr/bin/env python3
"""Bounded LF-B scalar policy acceptance; owns all temporary databases."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from lakematch.mastering.contracts import digest
from lakematch.mastering.identity_contract import IdentityContext, SourceRef
from lakematch.mastering.identity_registry import PostgresIdentityRegistry
from lakematch.mastering.registry import PostgresRegistry, apply_migrations
from lakematch.mastering.survivorship import calculate
from lakefusion_survivorship_fixture import AS_OF, ROOT, override, seed
from local_postgres import LocalPostgres


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tests-output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.tests_output.exists():
        parser.error("Use fresh paths; retain prior evidence")
    started = time.monotonic()
    server = None
    report = {"phase": "LF-B", "packages": ["LM-005"], "status": "running",
              "started_at": datetime.now(timezone.utc).isoformat(), "cloud_calls": 0,
              "confirmation_materialized": False, "fixture": "13 synthetic integration rows; declared truth memberships",
              "authority": "trusted workers and synthetic approval actors; no authenticated workflow claim",
              "cleanup": "not started"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.tests_output.parent.mkdir(parents=True, exist_ok=True)
    try:
        freeze = json.loads((ROOT / "spec/lakefusion/frozen/phase-a-v0.1.json").read_text())
        assert all(sha(ROOT / p) == h for p, h in freeze["files"].items()), "Frozen Phase A content drift"
        report["phase_a_freeze_verified"] = True
        paths = [*sorted((ROOT / "src/lakematch/mastering").glob("*.py")),
                 *sorted((ROOT / "app/migrations/mastering").glob("*.sql")),
                 *sorted((ROOT / "tools").glob("lakefusion_survivorship*.py")),
                 ROOT / "tools/check_changes.py", ROOT / "tests/test_mastering_survivorship.py",
                 ROOT / "tests/postgres/test_survivorship_registry.py", ROOT / "tests/postgres/test_registry.py",
                 ROOT / "tests/postgres/test_identity_registry.py", ROOT / "requirements-postgres.lock",
                 ROOT / "spec/lakefusion/SURVIVORSHIP.md", ROOT / "bench/lakefusion/SURVIVORSHIP_PLAN.md",
                 ROOT / "examples/mastering/company_pilot/survivorship_policy.json"]
        report["source_hashes"] = {str(p.relative_to(ROOT)): sha(p) for p in paths}
        command = [sys.executable, "-m", "pytest", "-q", "tests/test_mastering_contracts.py",
                   "tests/test_mastering_policy.py", "tests/test_mastering_retrieval.py",
                   "tests/test_mastering_execution.py", "tests/test_mastering_identity_contract.py",
                   "tests/test_mastering_survivorship.py", "tests/test_config.py", "tests/postgres",
                   "tests/test_source_hygiene.py", "tests/test_source_scan.py", "--junitxml=" + str(args.tests_output)]
        report["test_command"] = command
        result = subprocess.run(command, cwd=ROOT, env={**os.environ, "LAKEMATCH_TEST_POSTGRES": "1"}, timeout=180)
        suites = list(ET.parse(args.tests_output).getroot().iter("testsuite"))
        report["tests"] = {k: sum(int(s.attrib[k]) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
        if result.returncode or any(report["tests"][k] for k in ("failures", "errors", "skipped")):
            raise RuntimeError("Required scalar/registry checks did not all pass")
        with LocalPostgres() as server:
            report["postgres"] = subprocess.check_output([server.binaries["postgres"], "--version"], text=True).strip()
            with server.connect() as connection:
                report["migrations"] = apply_migrations(connection, ROOT / "app/migrations/mastering")
                assert connection.execute("SHOW listen_addresses").fetchone()[0] == ""
                assert connection.execute("SHOW fsync").fetchone()[0] == "on"
            registry = PostgresRegistry(server.connect)
            binding, data, records = seed(registry)
            identities = PostgresIdentityRegistry(server.connect, IdentityContext("company", 1, binding.domain.sha256))
            results, snapshots, inputs = {}, {}, {}
            for company in data["truth"]:
                name = company["truth_id"]
                members = [SourceRef(*m) for m in company["members"]]
                receipt = identities.allocate(members, actor="synthetic_worker", reason="Declared integration memberships", key=name)
                snapshot = {**identities.get(receipt["result"]["master_id"]), "domain_id": "company",
                            "domain_version": 1, "domain_sha256": binding.domain.sha256}
                source = [records[(m.source_id, m.source_key)] for m in members]
                output = calculate(binding, snapshot, source, as_of=AS_OF)
                assert output["status"] == "calculated"
                assert output["values"]["legal_name"] == source[0]["values"]["legal_name"]
                assert output == calculate(binding, snapshot, list(reversed(source)), as_of=AS_OF)
                results[name], snapshots[name], inputs[name] = output, snapshot, source
            assert len(results) == 6
            assert all(r["source_key"] != "A101" for r in results["cedar"]["inputs"]["records"])
            before = results["cedar"]
            changed = deepcopy(inputs["cedar"])
            changed[0]["version"] = 2
            changed[0]["values"]["address_line1"] = "99 Updated Example Avenue"
            updated = calculate(binding, snapshots["cedar"], changed, as_of=AS_OF)
            assert updated["values"]["address_line1"] == "99 Updated Example Avenue"
            assert before["values"]["address_line1"] == "10 Example Avenue"
            changed[0].update(version=3, deleted=True, values={}, assessments={})
            deleted = calculate(binding, snapshots["cedar"], changed, as_of=AS_OF)
            assert deleted["values"]["legal_name"] == changed[1]["values"]["legal_name"]
            decision = override(binding, snapshots["cedar"])
            overridden = calculate(binding, snapshots["cedar"], changed, as_of=AS_OF, overrides=[decision])
            assert overridden["values"]["legal_name"] == decision["value"]
            atlas = deepcopy(inputs["atlas_fr"])
            atlas[1].update(version=2, deleted=True, values={}, assessments={})
            atlas_deleted = calculate(binding, snapshots["atlas_fr"], atlas, as_of=AS_OF)
            assert atlas_deleted["values"] == results["atlas_fr"]["values"]
            assert atlas_deleted["input_sha256"] != results["atlas_fr"]["input_sha256"]
            server.restart()
            replay = registry.resolve_survivorship("company", binding.policy.policy_id, 1)
            for name in results:
                assert identities.get(snapshots[name]["master_id"])["members"] == snapshots[name]["members"]
                assert calculate(replay, snapshots[name], inputs[name], as_of=AS_OF) == results[name]
            report.update(companies_calculated=6, legal_company_rows=12, branch_rows_excluded=1,
                          exact_replay_after_restart=True, unchanged_public_ids=True,
                          update_and_delete_verified=True, approved_override_verified=True,
                          source_deletion_does_not_remove_identity_binding=True,
                          policy_sha256=binding.policy.sha256,
                          result_hashes={name: r["result_sha256"] for name, r in results.items()},
                          lifecycle_hashes={"before": before["result_sha256"], "update": updated["result_sha256"],
                                            "delete": deleted["result_sha256"], "override": overridden["result_sha256"]},
                          sample={"master_id": before["master_id"], "values": before["values"],
                                  "address_explanation": before["fields"]["address_line1"],
                                  "override_explanation": overridden["fields"]["legal_name"]})
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report["main_process_peak_rss_bytes"] = peak if sys.platform == "darwin" else peak * 1024
        if report["main_process_peak_rss_bytes"] > 4 * 1024**3:
            raise RuntimeError("Observed main-process RSS exceeds 4 GiB")
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
    finally:
        report.update(cleanup=server.cleanup if server else "no lifecycle server started; test databases owned by fixtures",
                      ended_at=datetime.now(timezone.utc).isoformat(), wall_seconds=round(time.monotonic() - started, 3))
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k: report.get(k) for k in ("status", "tests", "companies_calculated", "cleanup", "error")}), flush=True)
    return int(report["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
