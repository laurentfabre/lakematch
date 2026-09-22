"""Scalar business behavior, independent of Spark, PostgreSQL or wall clock."""
from copy import deepcopy
from dataclasses import asdict, replace
from itertools import permutations
from pathlib import Path
import sys

import pytest

from lakematch.mastering.contracts import ContractError, Field, digest
from lakematch.mastering.survivorship import SurvivorshipConflict, calculate
from lakematch.mastering.survivorship_contract import FieldRule, SourcePriority, SurvivorshipBinding, SurvivorshipPolicy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from lakefusion_survivorship_fixture import AS_OF, override, sample


def run(binding, identity, records, **options):
    return calculate(binding, identity, records, as_of=AS_OF, **options)


def change_rule(binding, name="legal_name", **changes):
    policy = replace(binding.policy, version=binding.policy.version + 1,
                     fields=tuple(replace(r, **changes) if r.field == name else r for r in binding.policy.fields))
    return replace(binding, policy=policy)


def test_pilot_conflicts_preserve_values_and_choose_erp_with_pinned_evidence():
    b, i, records = sample()
    result = run(b, i, records)
    assert result["status"] == "calculated"
    assert result["values"]["legal_name"] == "Cedar Components SA"
    assert result["values"]["address_line1"] == "10 Example Avenue"
    field = result["fields"]["address_line1"]
    assert field["reason"] == "source_priority" and field["conflicting_values"]
    assert {r["value"] for r in field["alternatives"]} == {"10 Example Avenue", "99 Updated Example Avenue"}
    assert field["winner"]["source_id"] == "erp_vendor" and field["winner"]["version"] == 1
    assert field["winner"]["sha256"] == digest(records[0])
    assert result["binding"]["policy_sha256"] == b.policy.sha256
    assert result["identity_revision"] == 1


def test_permutations_members_and_offset_equivalence_have_exact_same_receipt():
    b, i, records = sample()
    saved = deepcopy((i, records))
    expected = run(b, i, records)
    for perm in permutations(records):
        identity = {**i, "members": list(reversed(i["members"]))}
        values = deepcopy(list(perm))
        for record in values:
            record["updated_at"] = "2026-09-20T02:00:00+02:00"
        assert calculate(b, identity, values, as_of="2026-09-22T14:00:00+02:00") == expected
    assert (i, records) == saved


@pytest.mark.parametrize("criterion", ["verified", "source_priority", "quality", "freshness", "source_id", "source_key"])
def test_ranking_criteria_order_and_deterministic_ties(criterion):
    b, i, records = sample()
    if criterion == "verified":
        records[0]["assessments"]["legal_name"]["verified"] = False
    elif criterion != "source_priority":
        b = change_rule(b, sources=(SourcePriority("erp_vendor", 0), SourcePriority("crm_account", 0)))
        if criterion == "quality":
            records[1]["assessments"]["legal_name"]["quality"] = 95
        elif criterion == "freshness":
            records[1]["updated_at"] = "2026-09-20T00:00:00.000001+00:00"
        elif criterion == "source_key":
            records[1] = deepcopy(records[0])
            records[1]["source_key"] = "V000"
            records[1]["values"]["legal_name"] = "Earlier-key name"
            i["members"][1] = {"source_id": "erp_vendor", "source_key": "V000"}
    result = run(b, i, records)
    assert result["fields"]["legal_name"]["reason"] == criterion
    expected = records[0] if criterion == "source_priority" else records[1]
    assert result["values"]["legal_name"] == expected["values"]["legal_name"]
    assert run(b, i, list(reversed(records))) == result


def test_source_priority_precedes_quality_and_freshness():
    b, i, records = sample()
    records[0]["assessments"]["legal_name"]["quality"] = 50
    records[1]["updated_at"] = AS_OF
    assert run(b, i, records)["values"]["legal_name"] == records[0]["values"]["legal_name"]


@pytest.mark.parametrize("value,reason", [(None, "null"), ("  ", "blank"), (123, "invalid_type"),
                                         (False, "invalid_type"), (["name"], "invalid_type")])
def test_invalid_values_are_excluded_without_implicit_cast_or_loss(value, reason):
    b, i, records = sample()
    records[0]["values"]["legal_name"] = value
    result = run(b, i, records)
    assert result["values"]["legal_name"] == records[1]["values"]["legal_name"]
    alternative = result["fields"]["legal_name"]["alternatives"][1]
    assert alternative["excluded"] == reason and alternative["value"] == value


def test_missing_optional_null_and_required_unavailability_are_distinct():
    b, i, records = sample()
    for record in records:
        del record["values"]["legal_name"], record["assessments"]["legal_name"]
    result = run(b, i, records)
    assert result["status"] == "needs_review" and result["values"]["legal_name"] is None
    assert {r["excluded"] for r in result["fields"]["legal_name"]["alternatives"]} == {"missing"}
    assert result["values"]["parent_source_key"] is None
    assert {r["excluded"] for r in result["fields"]["parent_source_key"]["alternatives"]} == {"null"}


def test_quality_age_and_allowed_values_filter_before_ranking():
    b, i, records = sample()
    b = change_rule(b, maximum_age_seconds=60)
    records[1]["updated_at"] = AS_OF
    result = run(b, i, records)
    assert result["fields"]["legal_name"]["alternatives"][1]["excluded"] == "stale"
    records[1]["assessments"]["legal_name"]["quality"] = 49
    result = run(b, i, records)
    assert result["values"]["legal_name"] is None
    assert result["fields"]["legal_name"]["alternatives"][0]["excluded"] == "below_minimum_quality"
    records[0]["values"]["country"] = "XX"
    result = run(b, i, records)
    assert result["fields"]["country"]["alternatives"][1]["excluded"] == "disallowed_value"


def test_branch_values_cannot_supply_any_field_of_company():
    b, i, records = sample()
    records[0]["values"]["record_kind"] = "branch"
    result = run(b, i, records)
    assert result["values"]["legal_name"] == records[1]["values"]["legal_name"]
    assert all(v["alternatives"][1]["excluded"] == "ineligible_record_kind" for v in result["fields"].values())


def test_source_update_delete_and_all_deleted_never_carry_forward_winner():
    b, i, records = sample()
    before = run(b, i, records)
    records[0]["version"] = 2
    records[0]["values"]["legal_name"] = "Changed legal name"
    after = run(b, i, records)
    assert after["values"]["legal_name"] == "Changed legal name"
    assert after["fields"]["legal_name"]["winner"]["version"] == 2
    records[0].update(version=3, deleted=True, values={}, assessments={})
    deleted = run(b, i, records)
    assert deleted["values"]["legal_name"] == records[1]["values"]["legal_name"]
    records[1].update(version=2, deleted=True, values={}, assessments={})
    empty = run(b, i, records)
    assert all(v is None for v in empty["values"].values()) and empty["status"] == "needs_review"
    assert {"reason": "no_live_sources"} in empty["issues"]
    assert before["values"]["legal_name"] == "Cedar Components SA"
    assert len({r["input_sha256"] for r in (before, after, deleted, empty)}) == 4


def test_approved_override_and_optional_clear_with_source_deletion():
    b, i, records = sample()
    decisions = [override(b, i), override(b, i, decision_id="clear", field="registration_id", value=None)]
    records[0].update(version=2, deleted=True, values={}, assessments={})
    result = run(b, i, records, overrides=decisions)
    assert result["values"]["legal_name"] == decisions[0]["value"]
    assert result["values"]["registration_id"] is None
    assert result["fields"]["legal_name"]["reason"] == "approved_override"
    assert result["fields"]["registration_id"]["winner"]["decision_id"] == "clear"
    assert run(b, i, records, overrides=list(reversed(decisions))) == result


@pytest.mark.parametrize("changes,reason", [({"state": "pending", "approved_by": None, "approved_at": None}, "pending"),
                                           ({"state": "revoked"}, "revoked"),
                                           ({"expires_at": AS_OF}, "expired")])
def test_pending_revoked_expired_override_cannot_win(changes, reason):
    b, i, records = sample()
    result = run(b, i, records, overrides=[override(b, i, **changes)])
    assert result["values"]["legal_name"] == records[0]["values"]["legal_name"]
    assert result["inputs"]["overrides"][0]["excluded"] == reason


@pytest.mark.parametrize("changes", [{"approved_by": "synthetic_steward"}, {"identity_revision": 2},
                                      {"policy_sha256": "0" * 64}, {"approved_at": "2027-01-01T00:00:00Z"},
                                      {"master_id": "foreign"}])
def test_stale_or_unapproved_active_decision_fails_instead_of_silent_fallback(changes):
    b, i, records = sample()
    with pytest.raises(SurvivorshipConflict):
        run(b, i, records, overrides=[override(b, i, **changes)])


@pytest.mark.parametrize("value", [None, " ", 123])
def test_invalid_required_override_is_refused(value):
    b, i, records = sample()
    with pytest.raises(ContractError, match="Invalid approved override"):
        run(b, i, records, overrides=[override(b, i, value=value)])


def test_conflicting_approvals_and_duplicates_fail():
    b, i, records = sample()
    for second in (override(b, i), override(b, i, decision_id="second")):
        with pytest.raises(SurvivorshipConflict):
            run(b, i, records, overrides=[override(b, i), second])


def test_mixed_address_winners_require_review():
    b, i, records = sample()
    records[0]["values"]["address_line1"] = None
    result = run(b, i, records)
    assert result["status"] == "needs_review"
    assert any(issue["reason"] == "mixed_scalar_sources" for issue in result["issues"])


@pytest.mark.parametrize("mutation", ["missing_member", "foreign_member", "duplicate_version", "mapping_drift",
                                      "future_source", "naive_time", "domain_drift", "inactive", "tombstone_values",
                                      "assessment_missing", "invalid_quality", "unknown_field"])
def test_invalid_snapshot_fails_closed(mutation):
    b, i, records = sample()
    if mutation == "missing_member":
        records.pop()
    elif mutation == "foreign_member":
        records[0]["source_key"] = "foreign"
    elif mutation == "duplicate_version":
        records.append({**records[0], "version": 2})
    elif mutation == "mapping_drift":
        records[0]["mapping_sha256"] = "0" * 64
    elif mutation == "future_source":
        records[0]["updated_at"] = "2027-01-01T00:00:00Z"
    elif mutation == "naive_time":
        records[0]["updated_at"] = "2026-09-20T00:00:00"
    elif mutation == "domain_drift":
        i["domain_version"] = 2
    elif mutation == "inactive":
        i["state"] = "merged"
    elif mutation == "tombstone_values":
        records[0]["deleted"] = True
    elif mutation == "assessment_missing":
        del records[0]["assessments"]["legal_name"]
    elif mutation == "invalid_quality":
        records[0]["assessments"]["legal_name"]["quality"] = True
    elif mutation == "unknown_field":
        records[0]["values"]["unknown"] = "x"
    with pytest.raises((ContractError, SurvivorshipConflict)):
        run(b, i, records)


@pytest.mark.parametrize("limit", ["records", "decisions", "bytes"])
def test_finite_request_bounds(limit):
    b, i, records = sample()
    with pytest.raises(ContractError):
        if limit == "records":
            run(b, i, records * 501)
        elif limit == "decisions":
            run(b, i, records, overrides=[override(b, i)] * 201)
        else:
            records[0]["values"]["legal_name"] = "x" * (4 * 1024 * 1024)
            run(b, i, records)


def test_policy_roundtrip_and_strict_domain_mapping_rule_bindings():
    b, _, _ = sample()
    assert SurvivorshipPolicy.from_dict(asdict(b.policy)) == b.policy
    with pytest.raises(ContractError):
        replace(b, policy=replace(b.policy, domain_sha256="0" * 64))
    with pytest.raises(ContractError):
        replace(b, policy=replace(b.policy, fields=b.policy.fields[:-1]))
    with pytest.raises(ContractError):
        replace(b, mappings=b.mappings[:1])
    with pytest.raises(ContractError):
        change_rule(b, name="record_kind", allowed_values=())
    with pytest.raises(ContractError):
        replace(b.policy, algorithm="unknown")


@pytest.mark.parametrize("kind,good,bad", [("integer", 1, True), ("number", 1.2, "1.2"),
                                         ("boolean", False, 0), ("date", "2026-09-22", "2026-02-30"),
                                         ("timestamp", AS_OF, "2026-09-22")])
def test_other_scalar_types_use_frozen_contract_validation(kind, good, bad):
    from lakematch.mastering.survivorship import value_error
    rule = FieldRule("value", (SourcePriority("source", 0),))
    assert value_error(Field("value", kind), rule, good) is None
    assert value_error(Field("value", kind), rule, bad) == "invalid_type"
