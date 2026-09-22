"""Identity behavior against a real, private, disposable PostgreSQL process."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Barrier

import pytest

if os.environ.get("LAKEMATCH_TEST_POSTGRES") != "1":
    pytest.skip("Opt in with LAKEMATCH_TEST_POSTGRES=1", allow_module_level=True)

import psycopg

from lakematch.mastering.contracts import ContractError, DomainContract
from lakematch.mastering.identity_contract import IdentityConflict, IdentityContext, IdentityUnavailable, LegacyAlias, SourceRef
from lakematch.mastering.identity_registry import PostgresIdentityRegistry
from lakematch.mastering.registry import PostgresRegistry, apply_migrations

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from local_postgres import LocalPostgres


def options(key):
    return {"actor": "trusted_fixture_worker", "reason": "Synthetic identity lifecycle", "key": key}


def create(store, key, *source_keys, aliases=()):
    return store.allocate([SourceRef("erp_vendor", s) for s in source_keys], aliases=aliases, **options(key))


def master(receipt):
    return receipt["result"]["master_id"]


def versions(store, *ids):
    return {i: store.get(i)["requested_revision"] for i in ids}


@pytest.fixture(scope="module")
def postgres():
    with LocalPostgres() as instance:
        yield instance
    assert instance.cleanup == "owned Postgres stopped"


@pytest.fixture
def store(postgres):
    with postgres.connect() as connection:
        connection.execute("DROP SCHEMA IF EXISTS lm_control CASCADE")
        apply_migrations(connection, ROOT / "app/migrations/mastering")
    domain = DomainContract.from_dict(json.loads((ROOT / "examples/mastering/company_pilot/domain.json").read_text()))
    registry = PostgresRegistry(postgres.connect)
    registry.submit_domain(domain, actor="engineer", expected_latest=0)
    registry.transition("domain", "company", "company", 1, state="approved", expected_revision=1,
                        actor="approver", reason="Approved synthetic identity contract")
    return PostgresIdentityRegistry(postgres.connect, IdentityContext("company", 1, domain.sha256))


def test_earlier_source_key_does_not_rekey_and_old_receipts_replay(store):
    old = LegacyAlias("old_benchmark", "a" * 64)
    original = create(store, "allocate", "z99", "z98", aliases=[old])
    identity = master(original)
    attached = store.attach(identity, 1, members=[SourceRef("erp_vendor", "a00")], **options("attach"))
    assert store.get(identity)["revision"] == 2
    assert store.resolve_alias(old)["master_id"] == identity
    assert store.resolve_source(SourceRef("erp_vendor", "a00"))["master_id"] == identity
    assert create(store, "allocate", "z98", "z99", aliases=[old]) == original
    assert store.attach(identity, 1, members=[SourceRef("erp_vendor", "a00")], **options("attach")) == attached
    assert len(store.get(identity)["members"]) == 3
    assert len(store.history()) == 2
    with pytest.raises(IdentityConflict, match="different command"):
        create(store, "allocate", "other")


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_reservations_allocate_one_master(store, postgres, same_key):
    barrier = Barrier(4)
    def submit(index):
        barrier.wait(timeout=5)
        return create(store, "same" if same_key else str(index), "one")
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(submit, range(4)))
    assert len({master(r) for r in receipts}) == 1
    if same_key:
        assert all(r == receipts[0] for r in receipts)
    with postgres.connect() as connection:
        assert connection.execute("SELECT count(*) FROM lm_control.master_identity").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM lm_control.source_identity").fetchone()[0] == 1
    assert len(store.history()) == (1 if same_key else 4)


def test_overlapping_partial_allocation_requires_explicit_attach(store):
    first = master(create(store, "first", "a"))
    with pytest.raises(IdentityConflict, match="Partially bound"):
        create(store, "partial", "a", "b")
    assert len(store.get(first)["members"]) == 1
    with pytest.raises(IdentityUnavailable):
        store.resolve_source(SourceRef("erp_vendor", "b"))


def test_concurrent_attachment_has_one_revision_winner(store):
    identity = master(create(store, "first", "a"))
    barrier = Barrier(2)
    def attach(index):
        barrier.wait(timeout=5)
        try:
            return store.attach(identity, 1, members=[SourceRef("crm_account", str(index))], **options(f"attach-{index}"))
        except IdentityConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(attach, (1, 2)))
    assert result.count("conflict") == 1
    assert len(store.get(identity)["members"]) == 2
    assert len(store.history()) == 2


def test_merge_explicit_survivor_legacy_alias_and_exact_restoration(store):
    left_alias, right_alias = LegacyAlias("old", "a" * 64), LegacyAlias("old", "b" * 64)
    left = master(create(store, "left", "a", "b", aliases=[left_alias]))
    right = master(create(store, "right", "c", aliases=[right_alias]))
    merged = store.merge(right, {left: 1, right: 1}, **options("merge"))
    assert store.get(left)["master_id"] == right
    assert store.resolve_alias(left_alias)["master_id"] == right
    assert len(store.get(right)["members"]) == 3
    restored = store.restore_merge(merged["event_id"], {left: 2, right: 2}, **options("restore"))
    assert restored["result"]["split_policy"] == "restore_prior_identities"
    assert store.resolve_alias(left_alias)["master_id"] == left
    assert store.resolve_alias(right_alias)["master_id"] == right
    assert store.get(left)["revision"] == 3
    assert len(store.get(left)["members"]) == 2
    assert store.merge(right, {left: 1, right: 1}, **options("merge")) == merged
    assert store.restore_merge(merged["event_id"], {left: 2, right: 2}, **options("restore")) == restored
    rematch = store.merge(right, versions(store, left, right), **options("second-merge"))
    with pytest.raises(IdentityConflict, match="already been restored"):
        store.restore_merge(merged["event_id"], versions(store, left, right), **options("wrong-restoration"))
    assert store.get(left)["master_id"] == right and rematch["state"] == "identity_applied"


def test_nested_merges_restore_in_reverse_order_without_alias_cycles(store):
    a, b, c = (master(create(store, key, key, aliases=[LegacyAlias("old", key * 64)])) for key in ("a", "b", "c"))
    first = store.merge(b, versions(store, a, b), **options("merge-ab"))
    second = store.merge(c, versions(store, b, c), **options("merge-bc"))
    assert store.get(a)["redirect_chain"] == [a, b, c]
    with pytest.raises(IdentityConflict, match="participant changed"):
        store.restore_merge(first["event_id"], versions(store, a, b), **options("wrong-order"))
    store.restore_merge(second["event_id"], versions(store, b, c), **options("restore-bc"))
    store.restore_merge(first["event_id"], versions(store, a, b), **options("restore-ab"))
    for key, identity in (("a", a), ("b", b), ("c", c)):
        assert store.resolve_alias(LegacyAlias("old", key * 64))["master_id"] == identity


def test_new_identity_split_retries_and_keeps_original_alias(store):
    alias = LegacyAlias("old", "c" * 64)
    original = master(create(store, "original", "a", "b", "c", aliases=[alias]))
    split = store.split_new(original, 1, [SourceRef("erp_vendor", "b")], **options("split"))
    new = split["result"]["new_master_id"]
    assert new != original
    assert store.resolve_source(SourceRef("erp_vendor", "b"))["master_id"] == new
    assert store.resolve_alias(alias)["master_id"] == original
    assert store.split_new(original, 1, [SourceRef("erp_vendor", "b")], **options("split")) == split
    with pytest.raises(IdentityConflict, match="proper subset"):
        store.split_new(new, 1, [SourceRef("erp_vendor", "b")], **options("empty-original"))


def test_restore_refuses_new_members_and_stale_expected_revisions(store):
    a, b = (master(create(store, k, k)) for k in ("a", "b"))
    merge = store.merge(a, {a: 1, b: 1}, **options("merge"))
    with pytest.raises(IdentityConflict):
        store.restore_merge(merge["event_id"], {a: 1, b: 2}, **options("stale"))
    store.attach(a, 2, members=[SourceRef("erp_vendor", "new")], **options("attach"))
    with pytest.raises(IdentityConflict, match="participant changed"):
        store.restore_merge(merge["event_id"], versions(store, a, b), **options("restore"))
    assert len(store.get(a)["members"]) == 3


def test_competing_merges_have_one_winner(store):
    a, b, c = (master(create(store, k, k)) for k in ("a", "b", "c"))
    barrier = Barrier(2)
    def merge(survivor):
        barrier.wait(timeout=5)
        try:
            return store.merge(survivor, {a: 1, survivor: 1}, **options(survivor))
        except IdentityConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(merge, (b, c)))
    assert results.count("conflict") == 1
    winner = master(next(r for r in results if r != "conflict"))
    assert store.get(a)["master_id"] == winner


def test_lost_acknowledgement_returns_original_committed_receipt(store, postgres):
    @contextmanager
    def lost_response():
        with postgres.connect() as connection:
            yield connection
        raise TimeoutError("response lost after transaction commit")
    uncertain = PostgresIdentityRegistry(lost_response, store.context)
    with pytest.raises(TimeoutError):
        create(uncertain, "uncertain", "a")
    committed = store.history()[0]["receipt"]
    assert create(store, "uncertain", "a") == committed
    assert len(store.history()) == 1


def test_audit_failure_rolls_back_members_identity_and_revisions(store, monkeypatch):
    existing = master(create(store, "first", "a"))
    before = store.get(existing)
    def fail(*args):
        raise RuntimeError("simulated event failure")
    monkeypatch.setattr(store, "_record_event", fail)
    with pytest.raises(RuntimeError):
        store.attach(existing, 1, members=[SourceRef("erp_vendor", "b")], **options("attach"))
    assert store.get(existing) == before
    with pytest.raises(IdentityUnavailable):
        store.resolve_source(SourceRef("erp_vendor", "b"))
    with pytest.raises(RuntimeError):
        create(store, "new", "c")
    assert len(store.history()) == 1


def test_domain_approval_digest_and_actor_key_isolation(store, postgres):
    first = create(store, "first", "same")
    bad = PostgresIdentityRegistry(postgres.connect, replace(store.context, domain_sha256="0" * 64))
    with pytest.raises(IdentityUnavailable, match="digest"):
        create(bad, "bad", "other")
    domain = DomainContract.from_dict(json.loads((ROOT / "examples/mastering/company_pilot/domain.json").read_text()))
    other_domain = replace(domain, domain_id="other_company")
    registry = PostgresRegistry(postgres.connect)
    registry.submit_domain(other_domain, actor="engineer", expected_latest=0)
    other = PostgresIdentityRegistry(postgres.connect, IdentityContext(other_domain.domain_id, 1, other_domain.sha256))
    with pytest.raises(IdentityUnavailable, match="approved"):
        create(other, "draft", "same")
    registry.transition("domain", other_domain.domain_id, other_domain.domain_id, 1, state="approved", expected_revision=1,
                        actor="approver", reason="approve other domain")
    second = create(other, "other", "same")
    assert master(first) != master(second)
    with pytest.raises(IdentityUnavailable):
        other.get(master(first))
    with pytest.raises(IdentityConflict, match="different command"):
        create(other, "first", "same")
    registry.transition("domain", "company", "company", 1, state="retired", expected_revision=2,
                        actor="operator", reason="retire contract")
    assert create(store, "first", "same") == first
    with pytest.raises(IdentityUnavailable):
        create(store, "new-after-retirement", "new")


def test_source_keys_are_scoped_by_source_even_inside_one_domain(store):
    erp = master(store.allocate([SourceRef("erp_vendor", "same")], **options("erp")))
    crm = master(store.allocate([SourceRef("crm_account", "same")], **options("crm")))
    assert erp != crm
    assert store.resolve_source(SourceRef("erp_vendor", "same"))["master_id"] == erp
    assert store.resolve_source(SourceRef("crm_account", "same"))["master_id"] == crm


def test_timestamp_receipts_and_restoration_are_independent_of_session_timezone(store, postgres):
    def other_zone():
        connection = postgres.connect()
        connection.execute("SET TIME ZONE 'Pacific/Auckland'")
        return connection
    other = PostgresIdentityRegistry(other_zone, store.context)
    a, b = (master(create(store, k, k)) for k in ("a", "b"))
    assert store.get(a) == other.get(a)
    merged = store.merge(a, {a: 1, b: 1}, **options("merge"))
    restored = other.restore_merge(merged["event_id"], {a: 2, b: 2}, **options("restore"))
    assert restored["applied_at"].endswith("+00:00")
    assert store.restore_merge(merged["event_id"], {a: 2, b: 2}, **options("restore")) == restored
    assert store.get(b) == other.get(b)


def previous_schema(postgres, directory, state):
    migrations = ROOT / "app/migrations/mastering"
    for name in ("0001_control.sql", "0002_registry.sql"):
        shutil.copy2(migrations / name, directory / name)
    master_id = "a4c134a7-628a-4ca4-a2f5-bbf2f953da87"
    with postgres.connect() as connection:
        connection.execute("DROP SCHEMA lm_control CASCADE")
        apply_migrations(connection, directory)
        connection.execute("INSERT INTO lm_control.domain(domain_id) VALUES ('company')")
        connection.execute("INSERT INTO lm_control.master_identity(domain_id,master_id,state) VALUES ('company',%s,%s)",
                           (master_id, state))
        return connection.execute("SELECT master_id,revision,state,created_at FROM lm_control.master_identity").fetchone()


def test_additive_identity_upgrade_preserves_existing_prototype_ids(store, postgres, tmp_path):
    before = previous_schema(postgres, tmp_path, "active")
    with postgres.connect() as connection:
        assert list(apply_migrations(connection, ROOT / "app/migrations/mastering")) == [1, 2, 3, 4, 5]
        after = connection.execute("SELECT master_id,revision,state,created_at FROM lm_control.master_identity").fetchone()
        assert after == before
        assert connection.execute("SELECT redirect_to FROM lm_control.master_identity").fetchone()[0] is None


def test_unattributed_merged_prototype_row_refuses_upgrade_atomically(store, postgres, tmp_path):
    before = previous_schema(postgres, tmp_path, "merged")
    with postgres.connect() as connection:
        with pytest.raises(psycopg.errors.CheckViolation):
            apply_migrations(connection, ROOT / "app/migrations/mastering")
        assert connection.execute("SELECT master_id,revision,state,created_at FROM lm_control.master_identity").fetchone() == before
        assert connection.execute("SELECT count(*) FROM lm_control.schema_migration").fetchone()[0] == 2
        assert connection.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='lm_control' AND table_name='master_identity' AND column_name='redirect_to'").fetchone()[0] == 0


def test_alias_and_source_conflicts_roll_back_the_whole_command(store):
    alias = LegacyAlias("old", "d" * 64)
    a = master(create(store, "a", "a", aliases=[alias]))
    b = master(create(store, "b", "b"))
    with pytest.raises(IdentityConflict, match="alias"):
        store.attach(b, 1, members=[SourceRef("erp_vendor", "new")], aliases=[alias], **options("bad-alias"))
    with pytest.raises(IdentityUnavailable):
        store.resolve_source(SourceRef("erp_vendor", "new"))
    with pytest.raises(IdentityConflict, match="source reference"):
        store.attach(a, 1, members=[SourceRef("erp_vendor", "b")], **options("bad-source"))
    assert store.get(b)["revision"] == 1


def test_restart_preserves_master_alias_and_exact_command_receipts(store, postgres):
    alias = LegacyAlias("old", "e" * 64)
    receipt = create(store, "first", "a", aliases=[alias])
    before = store.resolve_alias(alias)
    postgres.restart()
    assert store.resolve_alias(alias) == before
    assert create(store, "first", "a", aliases=[alias]) == receipt


def test_process_death_before_commit_leaves_no_partial_identity(store, postgres):
    child = subprocess.run([sys.executable, "-c", '''
import os, sys
import psycopg
from lakematch.mastering.identity_contract import IdentityContext, SourceRef
from lakematch.mastering.identity_registry import PostgresIdentityRegistry
def connect():
    return psycopg.connect(host=sys.argv[1], port=int(sys.argv[2]), user='lm_registry_test',
                           dbname='postgres', autocommit=True, connect_timeout=3)
store = PostgresIdentityRegistry(connect, IdentityContext('company', 1, sys.argv[3]))
def die_before_receipt(*args):
    os._exit(73)
store._record_event = die_before_receipt
store.allocate([SourceRef('erp_vendor', 'crash')], actor='child', reason='crash fixture', key='crash')
''', str(postgres.socket), str(postgres.port), store.context.domain_sha256], timeout=15)
    assert child.returncode == 73
    with postgres.connect() as connection:
        # The independent connection observes no uncommitted/partially committed state.
        assert connection.execute("SELECT count(*) FROM lm_control.master_identity").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM lm_control.source_identity").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM lm_control.identity_event").fetchone()[0] == 0
    recovered = store.allocate([SourceRef("erp_vendor", "crash")], actor="child", reason="crash fixture", key="crash")
    assert recovered["result"]["outcome"] == "allocated"


def test_redirect_budget_is_enforced_before_any_old_id_becomes_unresolvable(store):
    first = current = master(create(store, "root", "root"))
    for i in range(64):
        new = master(create(store, f"next-{i}", f"next-{i}"))
        store.merge(new, versions(store, current, new), **options(f"merge-{i}"))
        current = new
    assert len(store.get(first)["redirect_chain"]) == 65
    final = master(create(store, "overflow", "overflow"))
    with pytest.raises(IdentityConflict, match="redirect"):
        store.merge(final, versions(store, current, final), **options("too-deep"))
    assert store.get(first)["master_id"] == current
    assert len(store.get(final)["members"]) == 1


@pytest.mark.parametrize("sql", [
    "UPDATE lm_control.identity_event SET receipt='{}'",
    "DELETE FROM lm_control.identity_event",
    "UPDATE lm_control.identity_alias SET namespace='rewritten'",
    "DELETE FROM lm_control.identity_alias",
    "DELETE FROM lm_control.master_identity",
    "UPDATE lm_control.master_identity SET revision=revision+2",
    "UPDATE lm_control.source_identity SET source_key='rewritten'",
    "DELETE FROM lm_control.source_identity",
])
def test_database_guards_identity_and_immutable_history(store, postgres, sql):
    create(store, "a", "a", aliases=[LegacyAlias("old", "a" * 64)])
    with postgres.connect() as connection:
        with pytest.raises(psycopg.errors.RaiseException):
            connection.execute(sql)
    assert len(store.history()) == 1


def test_bounded_membership_and_history_do_not_silently_truncate(store):
    receipt = store.allocate([SourceRef("erp_vendor", str(i)) for i in range(1000)], **options("large"))
    identity = master(receipt)
    with pytest.raises(IdentityConflict, match="exceeds"):
        store.attach(identity, 1, members=[SourceRef("erp_vendor", "extra")], **options("too-large"))
    assert store.get(identity)["revision"] == 1
    assert len(store.get(identity)["members"]) == 1000
    for i in range(3):
        create(store, f"more-{i}", f"new-{i}")
    first = store.history(limit=2)
    second = store.history(after_sequence=first[-1]["sequence"], limit=2)
    assert len(first + second) == 4 and first[-1]["sequence"] < second[0]["sequence"]
    with pytest.raises(ContractError):
        store.history(limit=101)
