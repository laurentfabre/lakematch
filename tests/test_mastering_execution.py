from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest

from lakematch.config import load
from lakematch.mastering.contracts import ContractError, DomainContract, SourceMapping
from lakematch.mastering.execution import (
    ExecutionBinding, ExecutionSpec, company_feature_config, execute_candidates,
    legacy_feature_rows, mapping_definition, preview_mapping, retrieval_digest,
)
from lakematch.mastering.retrieval import Limits

FIXTURE = Path(__file__).resolve().parents[1] / "examples/mastering/company_pilot"


def contracts():
    domain = DomainContract.from_dict(json.loads((FIXTURE / "domain.json").read_text()))
    left, right = (SourceMapping.from_dict(json.loads((FIXTURE / f"{s}_mapping.json").read_text()), domain)
                   for s in ("erp_vendor", "crm_account"))
    spec = ExecutionSpec("pilot", 1, domain.domain_id, domain.version, domain.sha256,
                         left.source_id, left.version, left.sha256,
                         right.source_id, right.version, right.sha256,
                         "identifier_name", retrieval_digest(), Limits(seconds=120))
    return domain, left, right, spec


def fixture_rows():
    return json.loads((FIXTURE / "fixture.json").read_text())["sources"]


def test_roundtrip_pins_definitions_and_retrieval_code():
    domain, left, right, spec = contracts()
    assert ExecutionSpec.from_dict(asdict(spec)) == spec
    assert SourceMapping.from_dict(mapping_definition(left), domain) == left
    binding = ExecutionBinding(spec, domain, left, right, ())
    assert binding.manifest()["execution_sha256"] == spec.sha256
    with pytest.raises(ContractError, match="implementation changed"):
        ExecutionBinding(replace(spec, retrieval_sha256="0" * 64), domain, left, right, ())
    with pytest.raises(ContractError, match="mapping binding"):
        ExecutionBinding(replace(spec, left_mapping_sha256="0" * 64), domain, left, right, ())


@pytest.mark.parametrize("change", [{"schema_version": True}, {"version": True}, {"retrieval_alternative": "magic"},
                                     {"domain_sha256": "bad"}, {"right_source_id": "erp_vendor"},
                                     {"unknown": 1}, {"limits": {"per_left": 51}}])
def test_execution_rejects_implicit_versions_unbounded_or_unknown_contracts(change):
    raw = asdict(contracts()[3])
    with pytest.raises((ContractError, ValueError)):
        ExecutionSpec.from_dict({**raw, **change})


def test_preview_quarantines_branch_and_reports_drift_without_partial_job():
    domain, left, right, spec = contracts()
    rows = fixture_rows()
    preview = preview_mapping(right, rows["crm_account"])
    assert len(preview["accepted"]) == 6
    assert len(preview["errors"]) == 1
    assert preview["errors"][0]["error"] == "ineligible_record_kind"
    binding = ExecutionBinding(spec, domain, left, right, ())
    with pytest.raises(ContractError, match="quarantine branches"):
        execute_candidates(binding, rows["erp_vendor"], rows["crm_account"])
    drift = {**rows["erp_vendor"][0], "unexpected": "value"}
    assert "drift" in preview_mapping(left, [drift])["errors"][0]["error"]
    with pytest.raises(ContractError, match="1000"):
        preview_mapping(left, [rows["erp_vendor"][0]] * 1001)
    duplicate = preview_mapping(left, [rows["erp_vendor"][0]] * 2)
    assert duplicate["errors"][0]["error"] == "duplicate_source_key"


def test_mapping_preview_byte_bound_and_pinned_job_source_bound():
    domain, left, right, spec = contracts()
    rows = fixture_rows()
    huge = {**rows["erp_vendor"][0], "vendor_name": "x" * (1024 * 1024)}
    with pytest.raises(ContractError, match="MiB"):
        preview_mapping(left, [huge])
    binding = ExecutionBinding(replace(spec, limits=Limits(input_rows_per_source=1)), domain, left, right, ())
    with pytest.raises(ContractError, match="bound exceeded"):
        execute_candidates(binding, rows["erp_vendor"], rows["crm_account"])


def test_candidate_receipt_is_retry_stable_and_excludes_hierarchy_features():
    domain, left, right, spec = contracts()
    rows = fixture_rows()
    right_rows = [r for r in rows["crm_account"] if r["account_type"] == "legal_company"]
    binding = ExecutionBinding(spec, domain, left, right, ())
    first = execute_candidates(binding, rows["erp_vendor"], right_rows)
    again = execute_candidates(binding, rows["erp_vendor"], right_rows)
    assert first["candidate_rows_sha256"] == again["candidate_rows_sha256"]
    assert first["input_snapshots"] == again["input_snapshots"]
    assert "parent_source_key" not in first["binding"]["feature_allowlist"]
    assert "not implemented" in first["auto_merge"]


def test_v1_projection_is_explicit_and_does_not_mutate_old_configuration():
    domain, left, right, spec = contracts()
    rows = fixture_rows()["erp_vendor"]
    legacy = load("examples/synthetic.yaml")
    before = legacy.canonical_json()
    with pytest.raises(ContractError, match="not rewritten"):
        legacy_feature_rows(left, rows, legacy)
    assert legacy.canonical_json() == before
    cfg = company_feature_config()
    projected = legacy_feature_rows(left, rows, cfg)
    assert len(projected) == len(rows)
    assert all(set(r) == {"rec_id", *cfg.fields} for r in projected)
    assert projected[0]["rec_id"] == rows[0]["vendor_id"]
    assert projected[0]["registration_id"] == rows[0]["registration_number"]
