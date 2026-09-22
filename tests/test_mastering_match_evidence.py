from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest

from lakematch.mastering.contracts import ContractError, DomainContract, SourceMapping, digest
from lakematch.mastering.match_contract import MatchBinding, MatchRuleset, PRECEDENCE
from lakematch.mastering.match_evidence import compare_pair, implementation_digest
from lakematch.mastering.survivorship_contract import MappingPin

FIXTURE = Path(__file__).resolve().parents[1] / "examples/mastering/company_pilot"


@pytest.fixture
def inputs():
    domain = DomainContract.from_dict(json.loads((FIXTURE / "domain.json").read_text()))
    mappings = tuple(SourceMapping.from_dict(json.loads((FIXTURE / f"{s}_mapping.json").read_text()), domain)
                     for s in ("erp_vendor", "crm_account"))
    rules = MatchRuleset("company_comparison", 1, domain.domain_id, domain.version, domain.sha256,
                        tuple(MappingPin(m.source_id, m.version, m.sha256) for m in mappings), implementation_digest())
    records = [{"source_id": m.source_id, "source_key": key, "version": 1, "mapping_version": m.version,
                "mapping_sha256": m.sha256, "deleted": False,
                "values": {"record_kind": "legal_company", "legal_name": "Café Cedar SAS", "country": "FR",
                           "registration_id": "001-234", "address_line1": "12 rue du Port",
                           "city": "Lyon", "postal_code": "69001"}}
               for m, key in zip(mappings, ("vendor-a", "account-a"))]
    return MatchBinding(rules, domain, mappings), records


def compare(inputs, methods=("identifier", "name")):
    binding, records = inputs
    return compare_pair(binding, *records, candidate_methods=methods)


def test_retry_swap_order_and_input_mutation_do_not_change_evidence(inputs):
    binding, records = inputs
    before = deepcopy(records)
    result = compare(inputs)
    assert result == compare(inputs)
    assert result == compare_pair(binding, *reversed(records), candidate_methods=["name", "identifier"])
    assert result["evidence_sha256"] == digest({k: v for k, v in result.items() if k != "evidence_sha256"})
    records[0]["values"]["legal_name"] = "Edited later"
    assert result["records"][1] == before[0]
    result["binding"]["ruleset"]["version"] = 900
    assert binding.ruleset.version == 1


def test_identifier_agreement_is_unqualified_and_never_a_merge(inputs):
    result = compare(inputs)
    assert result["decision"]["rule_id"] == "identifier_agreement"
    assert result["decision"]["suggestion"] == "match"
    assert result["decision"]["route"] == "review"
    assert result["decision"]["auto_merge_eligible"] is False
    assert result["model"] is result["calibration"] is result["probability"] is None
    # The provenance of retrieval cannot overrule fields or invent a probability.
    assert compare(inputs, ("tokens",))["decision"] == result["decision"]


@pytest.mark.parametrize("change,winner,route", [
    ({"record_kind": "branch"}, "ineligible_granularity", "exclude"),
    ({"record_kind": "family"}, "ineligible_granularity", "exclude"),
    ({"record_kind": "unknown"}, "incomplete_identity", "review"),
    ({"country": "DE"}, "different_jurisdictions", "review"),
    ({"registration_id": "009999"}, "identifier_conflict", "review"),
    ({"registration_id": None}, "name_agreement", "review"),
    ({"legal_name": "Another company", "registration_id": None}, "insufficient_evidence", "review"),
])
def test_precedence_over_name_and_identifier_agreements(inputs, change, winner, route):
    inputs[1][0]["values"].update(change)
    result = compare(inputs)
    assert result["decision"]["rule_id"] == winner
    assert result["decision"]["route"] == route
    assert sum(r["selected"] for r in result["rules"]) == 1
    assert result["rules"][0]["rule_id"] == winner


@pytest.mark.parametrize("value,state", [(None, "null"), ("  ", "blank"), (42, "invalid_type"),
                                         ("---", "invalid_format"), ("FRＡ12", "invalid_format")])
def test_absent_or_invalid_identifiers_never_agree(inputs, value, state):
    for record in inputs[1]:
        record["values"]["registration_id"] = value
    result = compare(inputs)
    field = result["fields"]["registration_id"]
    assert field["left"]["state"] == field["right"]["state"] == state
    assert field["comparison"] == "unavailable"
    assert field["raw_equal"] is None
    assert result["decision"]["rule_id"] == "name_agreement"


def test_missing_different_from_null_and_empty_normalized_name(inputs):
    del inputs[1][0]["values"]["registration_id"]
    inputs[1][1]["values"]["registration_id"] = None
    inputs[1][0]["values"]["legal_name"] = "SAS"
    result = compare(inputs)
    assert result["fields"]["registration_id"]["right"]["state"] == "missing"
    assert result["fields"]["registration_id"]["left"]["state"] == "null"
    assert result["decision"]["rule_id"] == "incomplete_identity"


def test_unicode_and_actual_values_are_preserved(inputs):
    inputs[1][0]["values"]["legal_name"] = "Café 上海 SAS"
    inputs[1][1]["values"]["legal_name"] = "Cafe 上海 Ltd"
    result = compare(inputs)
    field = result["fields"]["legal_name"]
    assert field["comparison"] == "agree"
    assert not field["raw_equal"]
    assert field["left"]["normalized"] == "cafe 上海"
    assert field["right"]["value"] == "Café 上海 SAS"
    inputs[1][1]["values"]["legal_name"] = "Cafe 北京 Ltd"
    assert compare(inputs)["fields"]["legal_name"]["comparison"] == "differ"


def test_self_comparisons_tombstones_and_same_source_duplicates(inputs):
    binding, (a, _) = inputs
    result = compare_pair(binding, a, a, candidate_methods=["name"])
    assert result["decision"]["rule_id"] == "same_source_record"
    newer = deepcopy(a)
    newer["version"] = 2
    newer["values"]["legal_name"] = "A new name"
    assert compare_pair(binding, a, newer, candidate_methods=["name"])["decision"]["route"] == "exclude"
    newer["version"] = 1
    with pytest.raises(ContractError, match="Changed content"):
        compare_pair(binding, a, newer, candidate_methods=["name"])
    newer["source_key"] = "another-key"
    assert compare_pair(binding, a, newer, candidate_methods=["name"])["decision"]["rule_id"] == "same_source_duplicate"
    newer.update(deleted=True, values={})
    assert compare_pair(binding, a, newer, candidate_methods=["name"])["decision"]["rule_id"] == "deleted_source"


def test_ruleset_roundtrip_and_drift(inputs, monkeypatch):
    binding, _ = inputs
    assert MatchRuleset.from_dict(asdict(binding.ruleset)) == binding.ruleset
    with pytest.raises(ContractError, match="implementation changed"):
        replace(binding, ruleset=replace(binding.ruleset, implementation_sha256="0" * 64))
    with pytest.raises(ContractError, match="domain binding"):
        replace(binding, ruleset=replace(binding.ruleset, domain_sha256="0" * 64))
    monkeypatch.setattr("lakematch.mastering.match_evidence.implementation_digest", lambda: "0" * 64)
    with pytest.raises(ContractError, match="implementation changed"):
        compare(inputs)


@pytest.mark.parametrize("change", [{"schema_version": True}, {"version": True}, {"unknown": 1},
    {"precedence": list(reversed(PRECEDENCE))}, {"normalization": "silent_new_default"}, {"mappings": []}])
def test_invalid_contracts_rejected(inputs, change):
    with pytest.raises(ContractError):
        MatchRuleset.from_dict({**asdict(inputs[0].ruleset), **change})


@pytest.mark.parametrize("change", [{"mapping_sha256": "0" * 64}, {"mapping_version": True},
    {"version": 0}, {"deleted": 1}, {"source_id": "other"}, {"truth_id": "forbidden"}])
def test_source_drift_and_undeclared_inputs_rejected(inputs, change):
    inputs[1][0].update(change)
    with pytest.raises(ContractError):
        compare(inputs)


def test_fields_and_byte_bounds(inputs):
    values = inputs[1][0]["values"]
    values["truth_id"] = "forbidden"
    with pytest.raises(ContractError, match="declared mapping"):
        compare(inputs)
    del values["truth_id"]
    values["legal_name"] = "x" * 2049
    with pytest.raises(ContractError, match="2048"):
        compare(inputs)
    values["legal_name"] = "x" * (64 * 1024)
    with pytest.raises(ContractError, match="64 KiB"):
        compare(inputs)
    values["legal_name"] = float("nan")
    with pytest.raises(ContractError, match="JSON"):
        compare(inputs)


@pytest.mark.parametrize("methods", [[], ["identifier", "identifier"], ["model_score"], [None], "name"])
def test_candidate_provenance_is_explicit(inputs, methods):
    with pytest.raises(ContractError, match="candidate methods"):
        compare(inputs, methods)
