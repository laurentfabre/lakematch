from dataclasses import replace
import sys
import subprocess

import pytest

from lakematch.mastering.contracts import ContractError
from lakematch.mastering.identity_contract import (
    IdentityContext, LegacyAlias, SourceRef, command_payload, master_key, references, revisions,
)


def test_identity_contract_import_does_not_load_optional_database_or_spark():
    subprocess.run([sys.executable, "-c", """
import sys
from lakematch.mastering.identity_contract import IdentityContext, SourceRef, LegacyAlias
assert 'psycopg' not in sys.modules and 'pyspark' not in sys.modules
"""], check=True, timeout=10)


@pytest.mark.parametrize("key", ["", " leading", "trailing ", "null\x00key", "é" * 1025, 123])
def test_invalid_source_references_are_rejected_before_database_access(key):
    with pytest.raises((ContractError, TypeError)):
        SourceRef("erp_vendor", key)


def test_policy_and_alias_versions_are_explicit():
    context = IdentityContext("company", 1, "a" * 64)
    assert LegacyAlias("historical_fixture", "b" * 64).policy_version == "spark_min_member_sha256_v1"
    for changes in ({"policy_version": "future"}, {"domain_sha256": "bad"}, {"domain_version": True}):
        with pytest.raises(ContractError):
            replace(context, **changes)
    with pytest.raises(ContractError):
        LegacyAlias("fixture", "b" * 64, policy_version="unknown")


def test_typed_member_limits_and_order_invariance():
    a, b = SourceRef("erp_vendor", "0001"), SourceRef("crm_account", "0001")
    assert references([a, b], SourceRef) == references([b, a], SourceRef)
    for values in ([], [a, a], [dict(source_id="erp_vendor", source_key="0001")], [a] * 1001):
        with pytest.raises(ContractError):
            references(values, SourceRef)


def test_uuid_revisions_and_payload_size_fail_closed():
    good = "0bd92518-a830-4e77-84e6-0a03c12f852a"
    for value in (good.upper(), "a" * 64, 1):
        with pytest.raises(ContractError):
            master_key(value)
    with pytest.raises(ContractError):
        revisions({good: True})
    with pytest.raises(ContractError, match="1 MiB"):
        command_payload(IdentityContext("company", 1, "a" * 64), "allocate",
                        {"members": ["a" * 2048] * 600}, "worker", "bounded")
