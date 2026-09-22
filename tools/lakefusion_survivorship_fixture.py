"""Synthetic integration helpers; fixture truth supplies memberships, never scores."""
from dataclasses import asdict
import json
from pathlib import Path
from uuid import UUID

from lakematch.mastering.contracts import DomainContract, SourceMapping
from lakematch.mastering.survivorship_contract import SurvivorshipBinding, SurvivorshipPolicy

ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-09-22T12:00:00+00:00"


def fixture():
    path = ROOT / "examples/mastering/company_pilot"
    domain = DomainContract.from_dict(json.loads((path / "domain.json").read_text()))
    mappings = tuple(SourceMapping.from_dict(json.loads((path / f"{s}_mapping.json").read_text()), domain)
                     for s in ("erp_vendor", "crm_account"))
    policy = SurvivorshipPolicy.from_dict(json.loads((path / "survivorship_policy.json").read_text()))
    data = json.loads((path / "fixture.json").read_text())
    records = {}
    for mapping in mappings:
        for row in data["sources"][mapping.source_id]:
            receipt = mapping.apply(row)
            record = {"source_id": mapping.source_id, "source_key": receipt["source_key"], "version": 1,
                      "mapping_version": mapping.version, "mapping_sha256": mapping.sha256,
                      "updated_at": "2026-09-20T00:00:00+00:00", "deleted": False,
                      "values": receipt["payload"], "assessments": {
                          name: {"quality": 90, "verified": True, "reference": "synthetic-assessment-v1"}
                          for name in receipt["payload"]}}
            records[(mapping.source_id, receipt["source_key"])] = record
    return SurvivorshipBinding(policy, domain, mappings), data, records


def sample():
    binding, data, by_source = fixture()
    members = data["truth"][0]["members"]
    identity = {"master_id": str(UUID(int=1)), "revision": 1, "state": "active",
                "domain_id": binding.domain.domain_id, "domain_version": binding.domain.version,
                "domain_sha256": binding.domain.sha256,
                "members": [{"source_id": s, "source_key": k} for s, k in members]}
    return binding, identity, [by_source[tuple(m)] for m in members]


def override(binding, identity, **changes):
    return {"decision_id": "synthetic-decision-1", "master_id": identity["master_id"],
            "identity_revision": identity["revision"], "policy_sha256": binding.policy.sha256,
            "field": "legal_name", "value": "Cedar Components — reviewed name", "state": "approved",
            "proposed_by": "synthetic_steward", "approved_by": "synthetic_approver",
            "reason": "Synthetic independent review", "approved_at": "2026-09-21T12:00:00+00:00",
            "expires_at": None, **changes}


def seed(registry):
    binding, data, records = fixture()
    def approve(kind, object_id):
        return registry.transition(kind, binding.domain.domain_id, object_id, 1, state="approved",
                                   expected_revision=1, actor="synthetic_approver", reason="Reviewed pilot scalar policy")
    registry.submit_domain(binding.domain, actor="synthetic_engineer", expected_latest=0)
    approve("domain", binding.domain.domain_id)
    for mapping in binding.mappings:
        registry.submit_mapping(mapping, actor="synthetic_engineer", expected_latest=0)
        approve("mapping", mapping.source_id)
    registry.submit_survivorship(binding.policy, actor="synthetic_engineer", expected_latest=0)
    approve("survivorship", binding.policy.policy_id)
    return registry.resolve_survivorship(binding.domain.domain_id, binding.policy.policy_id, 1), data, records
