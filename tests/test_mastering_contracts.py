"""Input compatibility and data-integrity invariants for the LF-A prototype."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from lakematch.mastering.contracts import ContractError, DomainContract, Field, FieldMapping, SourceMapping


def contract():
    return DomainContract("company", 1, "legal_company", (
        Field("legal_name", "string", True), Field("country", "string", True),
        Field("registration_id", "string"), Field("employees", "integer")))


def mapping():
    return SourceMapping("erp", 1, contract(), "vendor_id",
                         ("vendor_id", "name", "country", "registration", "employees"), (
                             FieldMapping("legal_name", "name", ("strip", "collapse_whitespace")),
                             FieldMapping("country", "country", ("strip", "upper")),
                             FieldMapping("registration_id", "registration"),
                             FieldMapping("employees", "employees")))


def record():
    return {"vendor_id": "0001", "name": "  Example   Company  ", "country": "fr",
            "registration": "0000123", "employees": 42}


def test_mapping_preserves_identifiers_and_provenance():
    result = mapping().apply(record())
    assert result["source_key"] == "0001"
    assert result["payload"] == {"legal_name": "Example Company", "country": "FR",
                                  "registration_id": "0000123", "employees": 42}
    assert result["domain_sha256"] == contract().sha256
    assert result == mapping().apply(record())
    assert result["payload_sha256"] != mapping().apply({**record(), "name": "Changed"})["payload_sha256"]


@pytest.mark.parametrize("change", [
    {"employees": True}, {"employees": "42"}, {"name": "  "}, {"country": None},
    {"vendor_id": 1}, {"vendor_id": ""}, {"name": 42}, {"unknown": "extra"},
])
def test_mapping_rejects_unsafe_casts_missing_identity_and_drift(change):
    with pytest.raises(ContractError):
        mapping().apply({**record(), **change})


def test_dropped_optional_column_is_schema_drift_but_null_is_allowed():
    row = record()
    row.pop("registration")
    with pytest.raises(ContractError, match="drift"):
        mapping().apply(row)
    assert mapping().apply({**record(), "registration": None})["payload"]["registration_id"] is None


def test_contract_and_mapping_versions_cannot_silently_change():
    domain = contract()
    changed = replace(domain, fields=domain.fields + (Field("phone", "string"),))
    assert domain.sha256 != changed.sha256
    raw = {"schema_version": 1, "source_id": "crm", "version": 1, "domain_id": "company",
           "domain_version": 1, "domain_sha256": domain.sha256, "source_key": "id",
           "source_columns": ["id", "name", "country"], "fields": [
               {"source": "name", "target": "legal_name"},
               {"source": "country", "target": "country"}]}
    assert SourceMapping.from_dict(raw, domain).apply({"id": "x", "name": "Acme", "country": "FR"})["source_id"] == "crm"
    with pytest.raises(ContractError, match="different domain"):
        SourceMapping.from_dict(raw, changed)


@pytest.mark.parametrize("kind,value", [
    ("number", float("nan")), ("number", float("inf")), ("boolean", "true"),
    ("date", "2026-02-30"), ("timestamp", "2026-09-21T12:00:00"),
    ("string_array", ["ok", None]), ("string", ["unexpected"]),
])
def test_invalid_scalar_values_are_rejected(kind, value):
    with pytest.raises(ContractError):
        Field("value", kind).validate(value)


def test_dates_and_timestamps_are_strict_and_timezone_aware():
    Field("date", "date").validate("2026-09-21")
    Field("at", "timestamp").validate("2026-09-21T12:00:00Z")
    Field("at", "timestamp").validate("2026-09-21T14:00:00+02:00")


def test_no_implicit_mapping_code_or_ambiguous_targets():
    with pytest.raises(ContractError, match="Unknown transformation"):
        FieldMapping("name", "name", ("eval",))
    with pytest.raises(ContractError, match="only one"):
        replace(mapping(), fields=mapping().fields + (FieldMapping("legal_name", "country"),))
    with pytest.raises(ContractError, match="Required target"):
        replace(mapping(), fields=())


def test_unknown_schema_keys_and_boolean_versions_are_rejected():
    with pytest.raises(ContractError):
        DomainContract.from_dict({"domain_id": "company", "version": 1,
                                  "identity_granularity": "legal_company", "fields": [], "typo": 1})
    with pytest.raises(ContractError):
        replace(contract(), version=True)
    with pytest.raises(ContractError):
        replace(contract(), fields=contract().fields + (Field("country", "string"),))


def test_proposed_two_source_fixture_maps_without_accessing_truth():
    root = Path(__file__).resolve().parents[1] / "examples/mastering/company_pilot"
    domain = DomainContract.from_dict(json.loads((root / "domain.json").read_text()))
    fixture = json.loads((root / "fixture.json").read_text())
    receipts = []
    for source, records in fixture["sources"].items():
        source_mapping = SourceMapping.from_dict(json.loads((root / f"{source}_mapping.json").read_text()), domain)
        receipts.extend(source_mapping.apply(row) for row in records)
    assert len(receipts) == 13
    assert len({(r["source_id"], r["source_key"]) for r in receipts}) == 13
    assert {r["payload"]["country"] for r in receipts} == {"FR", "BE", "GB"}
    assert sum(r["payload"]["record_kind"] == "branch" for r in receipts) == 1
    assert all("truth_id" not in r["payload"] for r in receipts)
