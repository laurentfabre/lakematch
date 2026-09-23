"""Portable policy envelopes and complete field/object scope semantics."""
from uuid import uuid4

import pytest

from lakematch.mastering.access_contract import AccessDenied, AccessSnapshot, grant_set
from lakematch.mastering.contracts import ContractError
from lakematch.mastering.policy import Grant

A, B = str(uuid4()), str(uuid4())


@pytest.mark.parametrize('grants', [None, [{}], [{'role': 'root', 'fields': None, 'object_ids': None}],
    [{'role': 'viewer', 'fields': [], 'object_ids': None}],
    [{'role': 'viewer', 'fields': ['city', 'city'], 'object_ids': None}],
    [{'role': 'viewer', 'fields': None, 'object_ids': ['bad']}],
    [{'role': 'viewer', 'fields': None, 'object_ids': [A, A]}],
    [{'role': 'viewer', 'fields': None, 'object_ids': None, 'principal': 'someone'}],
    [{'role': 'viewer', 'fields': None, 'object_ids': None}]*17,
])
def test_reject_unbounded_or_ambiguous_grants(grants):
    with pytest.raises(ContractError):
        grant_set('alice', 'company', grants)


def test_grants_are_canonical_detached_and_empty_revokes():
    raw = [{'role': 'viewer', 'fields': ['city', 'legal_name'], 'object_ids': [B, A]}]
    first = grant_set('alice', 'company', raw)
    raw[0]['fields'].reverse()
    raw[0]['object_ids'].reverse()
    assert grant_set('alice', 'company', raw) == first
    raw.clear()
    assert first['grants'] and grant_set('alice', 'company', [])['grants'] == []


def test_duplicate_grant_is_rejected():
    row = {'role': 'viewer', 'fields': None, 'object_ids': None}
    with pytest.raises(ContractError):
        grant_set('alice', 'company', [row, row])


def snapshot(*grants):
    return AccessSnapshot('alice', 'company', 1, 'a'*64, tuple(grants))


def test_field_grants_do_not_cross_combine_and_scopes_do_not_expand():
    partial = snapshot(Grant('alice', 'company', 'viewer', frozenset({'city'}), frozenset({A})),
                       Grant('alice', 'company', 'viewer', frozenset({'name'}), frozenset({A})))
    with pytest.raises(AccessDenied):
        partial.readable_objects(frozenset({'city', 'name'}))
    assert partial.readable_objects(frozenset({'city'})) == [A]
    assert not partial.permits('task.read', frozenset({'city'}), B)
    assert not partial.permits('task.claim', frozenset({'city'}), A)


def test_bounded_object_grants_union_only_after_complete_field_check():
    policy = snapshot(Grant('alice', 'company', 'viewer', None, frozenset({A})),
                      Grant('alice', 'company', 'viewer', None, frozenset({B})))
    assert policy.readable_objects(frozenset({'city'})) == sorted([A, B])
    unlimited = snapshot(Grant('alice', 'company', 'viewer'))
    assert unlimited.readable_objects(frozenset({'city'})) is None


@pytest.mark.parametrize('role,claim,propose,approve', [
    ('viewer', False, False, False), ('steward', True, True, False),
    ('approver', False, False, True), ('engineer', False, False, False),
    ('administrator', True, True, True),
])
def test_role_matrix_and_independence(role, claim, propose, approve):
    policy = snapshot(Grant('alice', 'company', role))
    for action, expected in [('task.claim', claim), ('decision.propose', propose), ('decision.approve', approve)]:
        assert policy.permits(action, frozenset({'city'}), A, proposed_by='bob') is expected
    assert not policy.permits('decision.approve', frozenset({'city'}), A, proposed_by='alice')
