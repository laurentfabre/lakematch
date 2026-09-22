#!/usr/bin/env python3
"""Bounded LF-B identity experiment; writes fresh evidence and owns its database."""
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

from lakematch.mastering.contracts import DomainContract, digest
from lakematch.mastering.identity_contract import IdentityContext, LegacyAlias, SourceRef
from lakematch.mastering.identity_registry import PostgresIdentityRegistry
from lakematch.mastering.registry import PostgresRegistry, apply_migrations
from local_postgres import LocalPostgres

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tests-output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.tests_output.exists():
        parser.error("Use fresh evidence paths; prior results remain immutable")
    started = time.monotonic()
    server = None
    report = {"phase": "LF-B", "packages": ["LM-004", "LM-007"], "status": "running",
              "started_at": datetime.now(timezone.utc).isoformat(), "cloud_calls": 0,
              "confirmation_materialized": False, "corpus": "small synthetic identity fixtures only",
              "actor_source": "trusted synthetic worker fixtures; no HTTP authentication claim",
              "driver": {"psycopg": version("psycopg")}, "cleanup": "not started"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.tests_output.parent.mkdir(parents=True, exist_ok=True)
    try:
        freeze = json.loads((ROOT / "spec/lakefusion/frozen/phase-a-v0.1.json").read_text())
        assert all(sha(ROOT / p) == h for p, h in freeze["files"].items()), "Frozen Phase A content drifted"
        report["phase_a_freeze_verified"] = True
        report["source_hashes"] = {str(p.relative_to(ROOT)): sha(p) for p in [
            *sorted((ROOT / "src/lakematch/mastering").glob("identity*.py")), ROOT / "src/lakematch/identity.py",
            ROOT / "spec/lakefusion/IDENTITY.md", ROOT / "bench/lakefusion/IDENTITY_PLAN.md",
            ROOT / "tools/lakefusion_identity_run.py", ROOT / "requirements-postgres.lock",
            *sorted((ROOT / "app/migrations/mastering").glob("*.sql"))]}
        command = [sys.executable, "-m", "pytest", "-q", "tests/test_mastering_contracts.py",
                   "tests/test_mastering_policy.py", "tests/test_mastering_retrieval.py",
                   "tests/test_mastering_execution.py", "tests/test_mastering_identity_contract.py",
                   "tests/test_config.py", "tests/test_source_hygiene.py", "tests/test_source_scan.py",
                   "tests/postgres", "tests/test_identity.py", "tests/test_identity_bridge.py",
                   "--junitxml=" + str(args.tests_output)]
        report["test_command"] = command
        tests = subprocess.run(command, cwd=ROOT, env={**os.environ, "LAKEMATCH_TEST_POSTGRES": "1"}, timeout=180)
        suites = list(ET.parse(args.tests_output).getroot().iter("testsuite"))
        report["tests"] = {k: sum(int(s.attrib[k]) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
        if tests.returncode or any(report["tests"][k] for k in ("failures", "errors", "skipped")):
            raise RuntimeError("Required identity/registry/compatibility checks did not all pass")
        domain = DomainContract.from_dict(json.loads((ROOT / "examples/mastering/company_pilot/domain.json").read_text()))
        context = IdentityContext(domain.domain_id, domain.version, domain.sha256)
        report["context"] = asdict(context)
        with LocalPostgres() as server:
            report["postgres"] = subprocess.check_output([server.binaries["postgres"], "--version"], text=True).strip()
            with server.connect() as connection:
                report["migrations"] = apply_migrations(connection, ROOT / "app/migrations/mastering")
                assert connection.execute("SHOW listen_addresses").fetchone()[0] == ""
                assert connection.execute("SHOW fsync").fetchone()[0] == "on"
            registry = PostgresRegistry(server.connect)
            registry.submit_domain(domain, actor="fixture_engineer", expected_latest=0)
            registry.transition("domain", "company", "company", 1, state="approved", expected_revision=1,
                                actor="fixture_approver", reason="Approved frozen company identity granularity")
            identities = PostgresIdentityRegistry(server.connect, context)
            def options(key):
                return {"actor": "fixture_worker", "reason": "Synthetic identity lifecycle demonstration", "key": key}
            a_alias, b_alias = LegacyAlias("synthetic_example", "a" * 64), LegacyAlias("synthetic_example", "b" * 64)
            a_members = [SourceRef("erp_vendor", "vendor-100"), SourceRef("crm_account", "account-100")]
            b_members = [SourceRef("erp_vendor", "vendor-200"), SourceRef("crm_account", "account-200")]
            a_receipt = identities.allocate(a_members, aliases=[a_alias], **options("allocate-a"))
            b_receipt = identities.allocate(b_members, aliases=[b_alias], **options("allocate-b"))
            a, b = (r["result"]["master_id"] for r in (a_receipt, b_receipt))
            earlier = SourceRef("erp_vendor", "vendor-000")
            attached = identities.attach(a, 1, members=[earlier], **options("attach-earlier"))
            assert identities.resolve_source(earlier)["master_id"] == a
            merged = identities.merge(a, {a: 2, b: 1}, **options("merge"))
            assert identities.resolve_alias(b_alias)["master_id"] == a
            restored = identities.restore_merge(merged["event_id"], {a: 3, b: 2}, **options("restore"))
            assert identities.resolve_alias(a_alias)["master_id"] == a
            assert identities.resolve_alias(b_alias)["master_id"] == b
            split = identities.split_new(a, 4, [earlier], **options("split-new"))
            new_id = split["result"]["new_master_id"]
            assert identities.resolve_source(earlier)["master_id"] == new_id
            assert identities.resolve_alias(a_alias)["master_id"] == a
            before = {"a": identities.get(a), "b": identities.get(b), "new": identities.get(new_id),
                      "events": identities.history()}
            server.restart()
            after = {"a": identities.get(a), "b": identities.get(b), "new": identities.get(new_id),
                     "events": identities.history()}
            assert before == after
            assert identities.allocate(a_members, aliases=[a_alias], **options("allocate-a")) == a_receipt
            assert identities.merge(a, {a: 2, b: 1}, **options("merge")) == merged
            assert identities.restore_merge(merged["event_id"], {a: 3, b: 2}, **options("restore")) == restored
            assert identities.split_new(a, 4, [earlier], **options("split-new")) == split
            assert len(identities.history()) == 6
            report.update(earlier_key_preserves_id=True, explicit_survivor_verified=True,
                          legacy_alias_redirect_and_restore=True, new_id_split_verified=True,
                          original_receipts_replay_after_later_changes=True,
                          database_restart_exact=True, lifecycle=after, lifecycle_sha256=digest(after),
                          commands=[a_receipt, b_receipt, attached, merged, restored, split])
        report["cleanup"] = server.cleanup
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report["main_process_peak_rss_bytes"] = peak if sys.platform == "darwin" else peak * 1024
        if report["main_process_peak_rss_bytes"] > 4 * 1024**3:
            raise RuntimeError("Main process memory exceeds the declared 4 GiB limit")
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
    finally:
        if server is not None:
            report["cleanup"] = server.cleanup
        report.update(ended_at=datetime.now(timezone.utc).isoformat(), wall_seconds=round(time.monotonic() - started, 3))
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k: report.get(k) for k in ("status", "tests", "database_restart_exact", "cleanup", "error")}), flush=True)
    return int(report["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
