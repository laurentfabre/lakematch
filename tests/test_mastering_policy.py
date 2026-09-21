"""Behavioral permission matrix for the proposed application policy boundary."""
import pytest

from lakematch.mastering.policy import Grant, permits


def test_read_requires_authenticated_scoped_grant_and_explicit_projection():
    grant = Grant("alice", "company", "viewer", frozenset({"legal_name"}), frozenset({"m1"}))
    good = dict(domain_id="company", action="entity.read", fields=frozenset({"legal_name"}), object_id="m1")
    assert permits("alice", [grant], **good)
    for change in ({"domain_id": "product"}, {"fields": frozenset({"legal_name", "tax_id"})},
                   {"object_id": "m2"}, {"fields": None}, {"action": "entity.delete"}):
        assert not permits("alice", [grant], **{**good, **change})
    assert not permits("bob", [grant], **good)
    assert not permits("", [grant], **good)
    assert not permits("alice", [], **good)


@pytest.mark.parametrize("role,action,expected", [
    ("viewer", "decision.propose", False), ("steward", "decision.propose", True),
    ("steward", "decision.approve", False), ("approver", "decision.approve", True),
    ("engineer", "run.execute", True), ("steward", "run.execute", False),
    ("administrator", "access.manage", True), ("approver", "access.manage", False),
])
def test_business_role_actions(role, action, expected):
    assert permits("alice", [Grant("alice", "company", role)], domain_id="company",
                   action=action, proposed_by="bob") is expected


@pytest.mark.parametrize("role", ["approver", "administrator"])
def test_approval_requires_an_independent_known_proposer(role):
    grant = Grant("alice", "company", role)
    for proposer in (None, "", "alice"):
        assert not permits("alice", [grant], domain_id="company", action="decision.approve", proposed_by=proposer)
    assert permits("alice", [grant], domain_id="company", action="decision.approve", proposed_by="bob")


def test_revocation_is_not_cached_and_grants_do_not_cross_combine_scopes():
    grants = [Grant("alice", "company", "viewer", frozenset({"name"}), frozenset({"m1"})),
              Grant("alice", "product", "administrator")]
    request = dict(domain_id="company", action="entity.read", fields=frozenset({"name"}), object_id="m1")
    assert permits("alice", grants, **request)
    assert not permits("alice", grants, **{**request, "fields": frozenset({"secret"})})
    assert not permits("alice", grants[1:], **request)


def test_field_scoped_mutation_cannot_omit_its_projection():
    grant = Grant("alice", "product", "steward", frozenset({"description"}))
    request = dict(domain_id="product", action="product.edit")
    assert not permits("alice", [grant], **request)
    assert not permits("alice", [grant], **request, fields=frozenset({"price"}))
    assert permits("alice", [grant], **request, fields=frozenset({"description"}))
