"""Synthetic provenance fixture; explicit truth membership, no match model."""
from copy import deepcopy
from dataclasses import replace
from uuid import UUID

from lakematch.mastering.contracts import digest
from lakematch.mastering.execution import mapping_definition
from lakematch.mastering.identity_contract import IdentityContext, SourceRef
from lakematch.mastering.survivorship import calculate
from lakefusion_survivorship_fixture import AS_OF, fixture, override, seed


def dataset(connect=None):
    if connect:
        from lakematch.mastering.identity_registry import PostgresIdentityRegistry
        from lakematch.mastering.registry import PostgresRegistry
        binding, data, records = seed(PostgresRegistry(connect))
        identities = PostgresIdentityRegistry(connect, IdentityContext("company", 1, binding.domain.sha256))
    else:
        binding, data, records = fixture()
        refs = [("domain", binding.domain.domain_id, binding.domain.sha256),
                *[("mapping", m.source_id, m.sha256) for m in binding.mappings],
                ("survivorship", binding.policy.policy_id, binding.policy.sha256)]
        receipts = tuple({"kind": k, "domain_id": "company", "object_id": key, "version": 1,
                          "definition_sha256": sha, "state": "approved", "revision": 2,
                          "created_by": "synthetic_engineer", "approved_by": "synthetic_approver",
                          "approval_reason": "Portable fixture contract", "approved_at": "2026-09-22T10:00:00+00:00"}
                         for k, key, sha in refs)
        binding = replace(binding, approvals=receipts)
    first, second = [], []
    for index, company in enumerate(data["truth"], 1):
        members = [SourceRef(*m) for m in company["members"]]
        identity = {"master_id": str(UUID(int=index)), "revision": 1, "state": "active",
                    "members": [{"source_id": m.source_id, "source_key": m.source_key} for m in members]}
        if connect:
            allocated = identities.allocate(members, actor="synthetic_worker", reason="Declared integration truth", key=company["truth_id"])
            identity = identities.get(allocated["result"]["master_id"])
        identity.update(domain_id="company", domain_version=1, domain_sha256=binding.domain.sha256)
        source = [deepcopy(records[(m.source_id, m.source_key)]) for m in members]
        def entry(overrides=()):
            return {"calculation": calculate(binding, identity, source, as_of=AS_OF, overrides=overrides),
                    "mappings": [mapping_definition(m) for m in binding.mappings]}
        first.append(entry())
        if company["truth_id"] == "cedar":
            source[0]["version"] = 2
            source[0]["values"]["address_line1"] = "99 Updated Example Avenue"
            second.append(entry([override(binding, identity)]))
        elif company["truth_id"] == "atlas_fr":
            source[1].update(version=2, deleted=True, values={}, assessments={})
            second.append(entry())
        else:
            second.append(entry())
    context = {"membership_basis": "synthetic_fixture_truth", "model": None,
               "ruleset": {"id": "declared_fixture_membership", "version": 1, "sha256": digest(data["truth"])},
               "configuration": {"id": "company_provenance_fixture", "version": 1,
                                 "sha256": digest({"as_of": AS_OF, "policy": binding.policy.sha256})}}
    return {"first": first, "second": second, "context": context,
            "cedar_id": first[0]["calculation"]["master_id"], "atlas_id": first[2]["calculation"]["master_id"]}
