#!/usr/bin/env python3
"""Test control-schema assumptions on an isolated local Postgres; no cloud access.

Uses installed initdb/postgres/psql. Owns a fresh private data/socket directory,
disables TCP, and stops its server before returning. Does not touch local services.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "app/migrations/mastering/0001_control.sql"


def migration_script(body):
    checksum = hashlib.sha256(body.encode()).hexdigest()
    return f"""BEGIN;
SELECT pg_advisory_xact_lock(127934, 1);
CREATE SCHEMA IF NOT EXISTS lm_control;
CREATE TABLE IF NOT EXISTS lm_control.schema_migration (
    version INTEGER PRIMARY KEY, sha256 TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now());
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM lm_control.schema_migration WHERE version=1 AND sha256 <> '{checksum}') THEN
        RAISE EXCEPTION 'Migration checksum mismatch';
    END IF;
END $$;
SELECT EXISTS (SELECT 1 FROM lm_control.schema_migration WHERE version=1) AS applied \\gset
\\if :applied
\\else
{body}
INSERT INTO lm_control.schema_migration(version, sha256) VALUES (1, '{checksum}');
\\endif
COMMIT;
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh evidence path")
    binaries = {name: shutil.which(name) for name in ("initdb", "postgres", "psql")}
    if not all(binaries.values()):
        parser.error("A local PostgreSQL installation is required")
    report = {"phase": "LF-A", "started_at": datetime.now(timezone.utc).isoformat(),
              "postgres": subprocess.check_output([binaries["postgres"], "--version"], text=True).strip(),
              "migration_sha256": hashlib.sha256(MIGRATION.read_bytes()).hexdigest(),
              "checks": [], "cleanup": "not_started"}
    server = None
    try:
        with tempfile.TemporaryDirectory(prefix="lm-pg-") as directory:
            base = Path(directory)
            data, sock = base / "db", base / "s"
            sock.mkdir(mode=0o700)
            subprocess.run([binaries["initdb"], "-D", str(data), "-U", "lf_spike", "--auth-local=trust",
                            "--auth-host=reject", "--no-locale", "--encoding=UTF8"],
                           check=True, capture_output=True, text=True, timeout=30)
            command = [binaries["psql"], "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-h", str(sock),
                       "-p", "55437", "-U", "lf_spike", "-d", "postgres"]

            def sql(text, *, fails=None):
                result = subprocess.run(command, input=text, capture_output=True, text=True, timeout=15)
                if fails is not None:
                    assert result.returncode and fails in result.stderr, result.stderr
                elif result.returncode:
                    raise RuntimeError(result.stderr)
                return result.stdout.strip()

            def check(name, assertion):
                assert assertion, name
                report["checks"].append({"name": name, "passed": True})

            with (base / "server.log").open("w") as log:
                server = subprocess.Popen([binaries["postgres"], "-D", str(data), "-k", str(sock),
                                           "-p", "55437", "-c", "listen_addresses=", "-c", "fsync=on"],
                                          stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 15
                    while True:
                        try:
                            sql("SELECT 1;")
                            break
                        except RuntimeError:
                            if server.poll() is not None or time.monotonic() >= deadline:
                                raise RuntimeError("Owned Postgres failed to start")
                            time.sleep(.1)
                    body = MIGRATION.read_text()
                    sql(migration_script(body))
                    sql(migration_script(body))
                    check("migration_retry_once", sql("SELECT count(*) FROM lm_control.schema_migration;") == "1")
                    sql(migration_script(body + "\n-- altered"), fails="Migration checksum mismatch")
                    check("changed_migration_rejected", True)
                    sql("INSERT INTO lm_control.domain(domain_id) VALUES ('company'), ('product');")
                    sql("INSERT INTO lm_control.domain_version VALUES ('company',1,'{}',repeat('a',64),'draft');")
                    sql("INSERT INTO lm_control.source_mapping_version VALUES ('company',2,'erp',1,'{}',repeat('b',64),'draft');", fails="foreign key")
                    check("mapping_requires_existing_domain_version", True)
                    task = "00000000-0000-0000-0000-000000000001"
                    op = "00000000-0000-0000-0000-000000000002"
                    event = "00000000-0000-0000-0000-000000000003"
                    decision = "00000000-0000-0000-0000-000000000004"
                    sql(f"INSERT INTO lm_control.steward_task(domain_id,task_id,kind,entity_ids,state) VALUES ('company','{task}','merge','[]','open');")
                    def claim(actor):
                        return sql(f"BEGIN; UPDATE lm_control.steward_task SET state='claimed', assignee='{actor}', lease_until=now()+interval '1 minute', revision=revision+1 WHERE task_id='{task}' AND domain_id='company' AND state='open' AND revision=1 RETURNING assignee; SELECT pg_sleep(0.2); COMMIT;")
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        claims = list(pool.map(claim, ("steward_a", "steward_b")))
                    check("concurrent_claim_has_one_winner", len([x for x in claims if x]) == 1)
                    check("stale_revision_updates_nothing", sql(f"UPDATE lm_control.steward_task SET priority=9 WHERE task_id='{task}' AND revision=1 RETURNING task_id;") == "")
                    insert_op = f"INSERT INTO lm_control.operation(operation_id,domain_id,caller,idempotency_key,payload_sha256,expected_versions,payload,state) VALUES ('{op}','company','steward_a','request-1',repeat('a',64),'{{}}','{{}}','approved');"
                    sql("BEGIN;" + insert_op + "ROLLBACK;")
                    check("rolled_back_intent_is_absent", sql("SELECT count(*) FROM lm_control.operation;") == "0")
                    sql("BEGIN;" + insert_op + f"INSERT INTO lm_control.outbox_event(event_id,operation_id,kind,payload,state) VALUES ('{event}','{op}','approved','{{}}','pending');COMMIT;")
                    sql(insert_op.replace(op, "00000000-0000-0000-0000-000000000005"), fails="unique constraint")
                    check("caller_idempotency_key_is_unique", sql("SELECT count(*) FROM lm_control.operation;") == "1")
                    check("intent_and_outbox_committed_together", sql("SELECT count(*) FROM lm_control.outbox_event;") == "1")
                    sql(f"INSERT INTO lm_control.steward_decision VALUES ('{decision}','product','{task}','{op}','steward_a','merge','reason',1,NULL,'{{}}',now());", fails="foreign key")
                    check("decision_cannot_cross_domains", True)
                    sql(f"INSERT INTO lm_control.steward_decision VALUES ('{decision}','company','{task}','{op}','steward_a','merge','reason',1,NULL,'{{}}',now());")
                    sql(f"UPDATE lm_control.steward_decision SET reason='changed' WHERE decision_id='{decision}';", fails="append-only")
                    sql(f"DELETE FROM lm_control.steward_decision WHERE decision_id='{decision}';", fails="append-only")
                    check("decisions_are_append_only", True)
                    sql(f"UPDATE lm_control.operation SET state='published' WHERE operation_id='{op}';", fails="check constraint")
                    check("publication_receipt_required", True)
                    sql(f"UPDATE lm_control.operation SET state='published', publication_id='  ' WHERE operation_id='{op}';", fails="check constraint")
                    check("blank_publication_receipt_rejected", True)
                    report["status"] = "passed"
                finally:
                    server.send_signal(signal.SIGINT)
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=5)
                    report["cleanup"] = "owned Postgres stopped" if server.returncode == 0 else f"owned Postgres exit {server.returncode}"
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
    report["ended_at"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)
    return int(report.get("status") != "passed" or report["cleanup"] != "owned Postgres stopped")


if __name__ == "__main__":
    raise SystemExit(main())
