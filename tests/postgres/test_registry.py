"""Explicit optional integration suite; uses only an owned TCP-disabled database."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import sys
from threading import Barrier

import pytest

if os.environ.get("LAKEMATCH_TEST_POSTGRES") != "1":
    pytest.skip("Opt in to owned local PostgreSQL integration with LAKEMATCH_TEST_POSTGRES=1", allow_module_level=True)

import psycopg

from lakematch.mastering.contracts import ContractError, DomainContract, Field, SourceMapping
from lakematch.mastering.execution import ExecutionSpec, retrieval_digest
from lakematch.mastering.registry import PostgresRegistry, RegistryConflict, RegistryUnavailable, apply_migrations
from lakematch.mastering.retrieval import Limits

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "app/migrations/mastering"
sys.path.insert(0, str(ROOT / "tools"))
from local_postgres import LocalPostgres


def definitions():
    fixture = ROOT / "examples/mastering/company_pilot"
    domain = DomainContract.from_dict(json.loads((fixture / "domain.json").read_text()))
    left, right = (SourceMapping.from_dict(json.loads((fixture / f"{s}_mapping.json").read_text()), domain)
                   for s in ("erp_vendor", "crm_account"))
    spec = ExecutionSpec("pilot", 1, domain.domain_id, domain.version, domain.sha256,
                         left.source_id, left.version, left.sha256, right.source_id, right.version, right.sha256,
                         "identifier_name", retrieval_digest(), Limits(seconds=120))
    return domain, left, right, spec


def approve(registry, kind, object_id, version=1):
    return registry.transition(kind, "company", object_id, version, state="approved", expected_revision=1,
                               actor="independent_reviewer", reason="Reviewed typed contract and preview")


def seed(registry):
    domain, left, right, spec = definitions()
    registry.submit_domain(domain, actor="engineer", expected_latest=0)
    approve(registry, "domain", "company")
    for mapping in (left, right):
        registry.submit_mapping(mapping, actor="engineer", expected_latest=0)
        approve(registry, "mapping", mapping.source_id)
    registry.submit_execution(spec, actor="engineer", expected_latest=0)
    approve(registry, "execution", spec.execution_id)
    return domain, left, right, spec


@pytest.fixture(scope="module")
def postgres():
    with LocalPostgres() as server:
        with server.connect() as connection:
            assert connection.execute("SHOW listen_addresses").fetchone()[0] == ""
        yield server
    assert server.cleanup == "owned Postgres stopped"


@pytest.fixture
def registry(postgres):
    # This instance was created above in a private temp directory. Never use a
    # caller-supplied DSN or a locally running service for these destructive resets.
    with postgres.connect() as connection:
        connection.execute("DROP SCHEMA IF EXISTS lm_control CASCADE")
        apply_migrations(connection, MIGRATIONS)
    return PostgresRegistry(postgres.connect)


def test_migrations_are_checksumming_retry_safe_and_reject_downgrade(registry, postgres, tmp_path):
    with postgres.connect() as connection:
        assert list(apply_migrations(connection, MIGRATIONS)) == [1, 2, 3, 4, 5, 6]
        assert connection.execute("SELECT count(*) FROM lm_control.schema_migration").fetchone()[0] == 6
        for path in MIGRATIONS.glob("*.sql"):
            shutil.copy2(path, tmp_path / path.name)
        path = tmp_path / "0006_access.sql"
        path.write_text(path.read_text() + "\n-- changed")
        with pytest.raises(RegistryConflict, match="checksum"):
            apply_migrations(connection, tmp_path)
        path.unlink()
        with pytest.raises(RegistryConflict, match="downgrade"):
            apply_migrations(connection, tmp_path)


def test_unattributed_legacy_approval_fails_upgrade_atomically(registry, postgres, tmp_path):
    shutil.copy2(MIGRATIONS / "0001_control.sql", tmp_path / "0001_control.sql")
    with postgres.connect() as connection:
        connection.execute("DROP SCHEMA lm_control CASCADE")
        apply_migrations(connection, tmp_path)
        connection.execute("INSERT INTO lm_control.domain(domain_id) VALUES ('company')")
        connection.execute("INSERT INTO lm_control.domain_version VALUES ('company',1,'{}',repeat('a',64),'approved')")
        with pytest.raises(psycopg.errors.CheckViolation):
            apply_migrations(connection, MIGRATIONS)
        assert connection.execute("SELECT count(*) FROM lm_control.schema_migration").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='lm_control' AND table_name='domain_version' AND column_name='created_by'").fetchone()[0] == 0


def test_draft_unavailable_then_idempotent_independent_approval(registry):
    domain = definitions()[0]
    first = registry.submit_domain(domain, actor="engineer", expected_latest=0)
    assert first == registry.submit_domain(domain, actor="engineer", expected_latest=0)
    assert len(registry.history("domain", "company", "company", 1)) == 1
    with pytest.raises(RegistryUnavailable):
        registry.get_domain("company", 1, approved=True)
    with pytest.raises(RegistryConflict, match="independent"):
        registry.transition("domain", "company", "company", 1, state="approved", expected_revision=1,
                            actor="engineer", reason="self review")
    approved = approve(registry, "domain", "company")
    assert approved == approve(registry, "domain", "company")
    assert registry.get_domain("company", 1, approved=True)["receipt"] == approved
    assert [e["action"] for e in registry.history("domain", "company", "company", 1)] == ["draft", "approved"]


def test_reused_version_changed_payload_and_stale_latest_are_conflicts(registry):
    domain = definitions()[0]
    registry.submit_domain(domain, actor="engineer", expected_latest=0)
    changed = replace(domain, fields=domain.fields + (Field("phone", "string"),))
    with pytest.raises(RegistryConflict, match="different immutable"):
        registry.submit_domain(changed, actor="engineer", expected_latest=0)
    with pytest.raises(RegistryConflict, match="stale"):
        registry.submit_domain(replace(domain, version=3), actor="engineer", expected_latest=2)
    assert registry.get_domain("company", 1)["receipt"]["definition_sha256"] == domain.sha256


def test_mapping_domain_digest_and_parent_approval_are_checked(registry):
    domain, left, _, _ = definitions()
    registry.submit_domain(domain, actor="engineer", expected_latest=0)
    registry.submit_mapping(left, actor="engineer", expected_latest=0)
    with pytest.raises(RegistryUnavailable):
        approve(registry, "mapping", left.source_id)
    changed = replace(domain, fields=domain.fields + (Field("phone", "string"),))
    with pytest.raises(RegistryConflict, match="domain digest"):
        registry.submit_mapping(replace(left, domain=changed), actor="engineer", expected_latest=0)
    approve(registry, "domain", "company")
    approved = approve(registry, "mapping", left.source_id)
    assert registry.get_mapping("company", left.source_id, 1, approved=True)["receipt"] == approved


def test_concurrent_submissions_do_not_overwrite_definitions(registry):
    domain = definitions()[0]
    barrier = Barrier(2)
    def submit(index):
        variant = replace(domain, fields=domain.fields + (Field(f"extra_{index}", "string"),))
        barrier.wait(timeout=5)
        try:
            return registry.submit_domain(variant, actor=f"engineer_{index}", expected_latest=0)
        except RegistryConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, (1, 2)))
    assert sum(r == "conflict" for r in results) == 1
    assert len(registry.history("domain", "company", "company", 1)) == 1


def test_concurrent_approvals_have_one_winner_and_stale_actor_conflicts(registry):
    registry.submit_domain(definitions()[0], actor="engineer", expected_latest=0)
    barrier = Barrier(2)
    def transition(actor):
        barrier.wait(timeout=5)
        try:
            return registry.transition("domain", "company", "company", 1, state="approved", expected_revision=1,
                                       actor=actor, reason="concurrent independent review")
        except RegistryConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(transition, ("reviewer_a", "reviewer_b")))
    assert sum(r == "conflict" for r in results) == 1
    assert len(registry.history("domain", "company", "company", 1)) == 2


def test_draft_and_audit_rollback_together(registry, monkeypatch):
    def fail(*args):
        raise RuntimeError("simulated audit insert failure")
    monkeypatch.setattr(registry, "_event", fail)
    with pytest.raises(RuntimeError, match="simulated"):
        registry.submit_domain(definitions()[0], actor="engineer", expected_latest=0)
    with pytest.raises(RegistryUnavailable):
        registry.get_domain("company", 1)
    assert registry.history("domain", "company", "company", 1) == []


@pytest.mark.parametrize("statement", [
    "UPDATE lm_control.domain_version SET definition='{}' WHERE domain_id='company'",
    "DELETE FROM lm_control.domain_version WHERE domain_id='company'",
    "UPDATE lm_control.source_mapping_version SET definition='{}' WHERE domain_id='company'",
    "UPDATE lm_control.execution_version SET definition='{}' WHERE domain_id='company'",
    "UPDATE lm_control.registry_event SET reason='rewritten' WHERE domain_id='company'",
    "DELETE FROM lm_control.registry_event WHERE domain_id='company'",
])
def test_database_protects_definition_and_audit_immutability(registry, postgres, statement):
    seed(registry)
    with postgres.connect() as connection:
        with pytest.raises(psycopg.errors.RaiseException):
            connection.execute(statement)
    assert registry.resolve("company", "pilot", 1).spec.version == 1


def test_registry_survives_postgres_restart_with_same_approval_receipts(registry, postgres):
    seed(registry)
    before = registry.resolve("company", "pilot", 1).manifest()
    postgres.restart()
    after = PostgresRegistry(postgres.connect).resolve("company", "pilot", 1).manifest()
    assert before == after
    assert len(after["approvals"]) == 4


def test_retired_dependency_prevents_new_resolution_without_erasing_history(registry):
    seed(registry)
    retired = registry.transition("mapping", "company", "crm_account", 1, state="retired", expected_revision=2,
                                  actor="release_operator", reason="source mapping replaced")
    assert retired["approved_by"] == "independent_reviewer"
    with pytest.raises(RegistryUnavailable):
        registry.resolve("company", "pilot", 1)
    events = registry.history("mapping", "company", "crm_account", 1, after_revision=1, limit=1)
    assert len(events) == 1 and events[0]["action"] == "approved"
    assert len(registry.history("mapping", "company", "crm_account", 1)) == 3


def test_execution_cannot_mix_domains_mappings_or_retrieval_code(registry):
    _, _, _, spec = seed(registry)
    for bad in (replace(spec, version=2, left_mapping_sha256="a" * 64),
                replace(spec, version=2, retrieval_sha256="b" * 64)):
        with pytest.raises(ContractError):
            registry.submit_execution(bad, actor="engineer", expected_latest=1)
    with pytest.raises(RegistryUnavailable):
        registry.resolve("different_domain", "pilot", 1)
    assert len(registry.history("execution", "company", "pilot", 1)) == 2


def test_new_execution_version_preserves_old_binding_and_job_retry_receipt(registry):
    _, _, _, spec = seed(registry)
    second = replace(spec, version=2, retrieval_alternative="identifier_name_tokens")
    registry.submit_execution(second, actor="engineer", expected_latest=1)
    approve(registry, "execution", "pilot", 2)
    assert registry.resolve("company", "pilot", 1).spec.retrieval_alternative == "identifier_name"
    assert registry.resolve("company", "pilot", 2).spec.retrieval_alternative == "identifier_name_tokens"
    rows = json.loads((ROOT / "examples/mastering/company_pilot/fixture.json").read_text())["sources"]
    right = [r for r in rows["crm_account"] if r["account_type"] == "legal_company"]
    first = registry.run_candidates("company", "pilot", 1, rows["erp_vendor"], right)
    again = registry.run_candidates("company", "pilot", 1, rows["erp_vendor"], right)
    assert first["binding"] == again["binding"]
    assert first["candidate_rows_sha256"] == again["candidate_rows_sha256"]
