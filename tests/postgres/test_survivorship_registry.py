"""Approved policy lifecycle and real persistent identities on owned PostgreSQL."""
from dataclasses import replace
import os
from pathlib import Path
import shutil
import sys

import pytest

if os.environ.get("LAKEMATCH_TEST_POSTGRES") != "1":
    pytest.skip("Opt in with LAKEMATCH_TEST_POSTGRES=1", allow_module_level=True)

import psycopg

from lakematch.mastering.contracts import ContractError
from lakematch.mastering.identity_contract import IdentityContext, SourceRef
from lakematch.mastering.identity_registry import PostgresIdentityRegistry
from lakematch.mastering.registry import PostgresRegistry, RegistryConflict, RegistryUnavailable, apply_migrations
from lakematch.mastering.survivorship import calculate

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from local_postgres import LocalPostgres
from lakefusion_survivorship_fixture import AS_OF, fixture, seed


@pytest.fixture(scope="module")
def postgres():
    with LocalPostgres() as instance:
        yield instance
    assert instance.cleanup == "owned Postgres stopped"


@pytest.fixture
def registry(postgres):
    with postgres.connect() as connection:
        connection.execute("DROP SCHEMA IF EXISTS lm_control CASCADE")
        apply_migrations(connection, ROOT / "app/migrations/mastering")
    return PostgresRegistry(postgres.connect)


def test_policy_has_immutable_approved_registry_history_and_exact_retry(registry):
    binding, _, _ = seed(registry)
    policy = binding.policy
    approved = registry.submit_survivorship(policy, actor="synthetic_engineer", expected_latest=0)
    assert approved["state"] == "approved"
    assert [r["action"] for r in registry.history("survivorship", "company", policy.policy_id, 1)] == ["draft", "approved"]
    with pytest.raises(RegistryConflict, match="different immutable"):
        registry.submit_survivorship(replace(policy, coherence_groups=()), actor="synthetic_engineer", expected_latest=0)
    with pytest.raises(RegistryConflict, match="stale"):
        registry.submit_survivorship(replace(policy, version=3), actor="synthetic_engineer", expected_latest=2)
    assert len(binding.approvals) == 4
    assert binding.approvals[-1]["definition_sha256"] == policy.sha256


def test_new_version_needs_independent_approval_and_all_dependencies(registry):
    binding, _, _ = seed(registry)
    policy = replace(binding.policy, version=2)
    registry.submit_survivorship(policy, actor="engineer", expected_latest=1)
    with pytest.raises(RegistryUnavailable):
        registry.resolve_survivorship("company", policy.policy_id, 2)
    with pytest.raises(RegistryConflict, match="independent"):
        registry.transition("survivorship", "company", policy.policy_id, 2, state="approved",
                            expected_revision=1, actor="engineer", reason="self review")
    registry.transition("mapping", "company", "crm_account", 1, state="retired", expected_revision=2,
                        actor="approver", reason="dependency retired")
    with pytest.raises(RegistryUnavailable):
        registry.transition("survivorship", "company", policy.policy_id, 2, state="approved",
                            expected_revision=1, actor="approver", reason="review")
    with pytest.raises(RegistryUnavailable):
        registry.resolve_survivorship("company", policy.policy_id, 1)


def test_mapping_digest_drift_and_domain_mismatch_cannot_enter_registry(registry):
    binding, _, _ = seed(registry)
    pin = replace(binding.policy.mappings[0], sha256="0" * 64)
    for policy in (replace(binding.policy, version=2, mappings=(pin, *binding.policy.mappings[1:])),
                   replace(binding.policy, version=2, domain_sha256="0" * 64)):
        with pytest.raises(ContractError):
            registry.submit_survivorship(policy, actor="engineer", expected_latest=1)


def test_policy_and_audit_cannot_be_edited_or_deleted(registry, postgres):
    seed(registry)
    statements = ["UPDATE lm_control.survivorship_version SET definition='{}'",
                  "DELETE FROM lm_control.survivorship_version",
                  "DELETE FROM lm_control.registry_event WHERE kind='survivorship'",
                  "UPDATE lm_control.survivorship_version SET approved_by='other', revision=revision+1"]
    for statement in statements:
        with postgres.connect() as connection, pytest.raises(psycopg.errors.RaiseException):
            with connection.transaction():
                connection.execute(statement)


def test_retirement_blocks_new_binding_but_preserves_pinned_history(registry):
    binding, _, _ = seed(registry)
    registry.transition("survivorship", "company", binding.policy.policy_id, 1, state="retired",
                        expected_revision=2, actor="operator", reason="new policy rollout")
    with pytest.raises(RegistryUnavailable):
        registry.resolve_survivorship("company", binding.policy.policy_id, 1)
    assert binding.policy.version == 1 and binding.approvals[-1]["state"] == "approved"


def test_approved_audit_event_required(registry, postgres):
    seed(registry)
    # Simulate missing audit state in the owned database, not a normal API path.
    with postgres.connect() as connection:
        connection.execute("ALTER TABLE lm_control.registry_event DISABLE TRIGGER immutable_registry_event")
        connection.execute("DELETE FROM lm_control.registry_event WHERE kind='survivorship' AND action='approved'")
        connection.execute("ALTER TABLE lm_control.registry_event ENABLE TRIGGER immutable_registry_event")
    with pytest.raises(RegistryUnavailable, match="audit"):
        registry.resolve_survivorship("company", "company_scalar", 1)


def test_populated_upgrade_preserves_identity_and_registry_with_restart(registry, postgres, tmp_path):
    migrations = ROOT / "app/migrations/mastering"
    for name in ("0001_control.sql", "0002_registry.sql", "0003_identity.sql"):
        shutil.copy2(migrations / name, tmp_path / name)
    with postgres.connect() as connection:
        connection.execute("DROP SCHEMA lm_control CASCADE")
        apply_migrations(connection, tmp_path)
    b, data, records = fixture()
    registry.submit_domain(b.domain, actor="engineer", expected_latest=0)
    registry.transition("domain", "company", "company", 1, state="approved", expected_revision=1,
                        actor="approver", reason="Approved domain before upgrade")
    identities = PostgresIdentityRegistry(postgres.connect, IdentityContext("company", 1, b.domain.sha256))
    members = [SourceRef(*m) for m in data["truth"][0]["members"]]
    receipt = identities.allocate(members, actor="worker", reason="Fixture before upgrade", key="before-upgrade")
    master_id = receipt["result"]["master_id"]
    before = identities.get(master_id)
    domain_before = registry.get_domain("company", 1, approved=True)
    with postgres.connect() as connection:
        assert list(apply_migrations(connection, migrations)) == [1, 2, 3, 4]
    for mapping in b.mappings:
        registry.submit_mapping(mapping, actor="engineer", expected_latest=0)
        registry.transition("mapping", "company", mapping.source_id, 1, state="approved", expected_revision=1,
                            actor="approver", reason="Mapping review")
    registry.submit_survivorship(b.policy, actor="engineer", expected_latest=0)
    registry.transition("survivorship", "company", b.policy.policy_id, 1, state="approved", expected_revision=1,
                        actor="approver", reason="Policy review")
    binding = registry.resolve_survivorship("company", b.policy.policy_id, 1)
    snapshot = {**before, "domain_id": "company", "domain_version": 1, "domain_sha256": b.domain.sha256}
    source = [records[(s.source_id, s.source_key)] for s in members]
    calculated = calculate(binding, snapshot, source, as_of=AS_OF)
    postgres.restart()
    assert identities.get(master_id) == before
    assert registry.get_domain("company", 1, approved=True) == domain_before
    assert calculate(registry.resolve_survivorship("company", b.policy.policy_id, 1), snapshot, source, as_of=AS_OF) == calculated
    def timezone_connection():
        connection = postgres.connect()
        connection.execute("SET TIME ZONE 'Pacific/Auckland'")
        return connection
    assert PostgresRegistry(timezone_connection).resolve_survivorship("company", b.policy.policy_id, 1).manifest() == binding.manifest()
