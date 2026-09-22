"""Opt-in bridge checks the actual unchanged Spark ID policy against PostgreSQL."""
import json
import os
from pathlib import Path
import sys

import pytest

if os.environ.get("LAKEMATCH_TEST_POSTGRES") != "1":
    pytest.skip("Opt in to the local PostgreSQL/Spark bridge", allow_module_level=True)

from lakematch.identity import assign
from lakematch.mastering.contracts import DomainContract
from lakematch.mastering.identity_contract import IdentityContext, LegacyAlias, SourceRef
from lakematch.mastering.identity_registry import PostgresIdentityRegistry
from lakematch.mastering.registry import PostgresRegistry, apply_migrations

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from local_postgres import LocalPostgres


def test_original_spark_ids_remain_resolvable_after_persistent_key_expansion(spark):
    old_members = [("m1", "group", "raw-one"), ("m2", "group", "raw-two")]
    schema = "rec_id string, cluster string, record_digest string"
    old = assign(spark.createDataFrame(old_members, schema), "identity_fixture").collect()
    legacy_ids = {r.mdm_id for r in old}
    assert len(legacy_ids) == 1
    legacy_id = next(iter(legacy_ids))
    # Existing behavior remains explicit: an earlier key changes the old policy's ID.
    expanded = assign(spark.createDataFrame([*old_members, ("a0", "group", "raw-new")], schema),
                      "identity_fixture").collect()
    assert {r.mdm_id for r in expanded} != legacy_ids
    domain = DomainContract.from_dict(json.loads((ROOT / "examples/mastering/company_pilot/domain.json").read_text()))
    with LocalPostgres() as postgres:
        with postgres.connect() as connection:
            apply_migrations(connection, ROOT / "app/migrations/mastering")
        registry = PostgresRegistry(postgres.connect)
        registry.submit_domain(domain, actor="engineer", expected_latest=0)
        registry.transition("domain", "company", "company", 1, state="approved", expected_revision=1,
                            actor="approver", reason="identity compatibility fixture")
        identities = PostgresIdentityRegistry(postgres.connect, IdentityContext("company", 1, domain.sha256))
        alias = LegacyAlias("identity_fixture", legacy_id)
        allocated = identities.allocate([SourceRef("old_snapshot", r.rec_id) for r in old], aliases=[alias],
                                        actor="worker", reason="import original snapshot identity", key="import")
        master = allocated["result"]["master_id"]
        identities.attach(master, 1, members=[SourceRef("old_snapshot", "a0")],
                          actor="worker", reason="add earlier key without rekey", key="expand")
        assert identities.resolve_alias(alias)["master_id"] == master
        assert identities.resolve_source(SourceRef("old_snapshot", "a0"))["master_id"] == master
        assert {r.mdm_id for r in assign(spark.createDataFrame(old_members, schema), "identity_fixture").collect()} == legacy_ids
    assert postgres.cleanup == "owned Postgres stopped"
