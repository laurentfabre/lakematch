"""Portable command validation; PostgreSQL behavior lives in tests/postgres."""
from dataclasses import replace
from uuid import uuid4

import pytest

from lakematch.mastering.contracts import ContractError
from lakematch.mastering.workflow_contract import (
    WorkflowContext, bounded_object, command, entities, expected_versions,
    intent_payload, lease_seconds, revision,
)

CONTEXT = WorkflowContext('company', 1, 'a' * 64)
A, B = str(uuid4()), str(uuid4())


@pytest.mark.parametrize('value', [0, -1, True, 1.0, '1', 2**63 - 1])
def test_revision_bounds(value):
    with pytest.raises(ContractError):
        revision(value)


@pytest.mark.parametrize('value', [0, -1, True, 901, 1.0, '60'])
def test_lease_bounds(value):
    with pytest.raises(ContractError):
        lease_seconds(value)


@pytest.mark.parametrize('value', [{1: 'key'}, {'a': float('inf')}, {'a': float('nan')},
                                  {'a': object()}, {'a': '\x00'}, {'\x00': 1},
                                  {'a': 'x' * 32768}, {'a': list(range(4096))}, []])
def test_json_envelope(value):
    with pytest.raises(ContractError):
        bounded_object(value)


def test_json_depth_cycles_and_detachment():
    value = {}
    value['self'] = value
    with pytest.raises(ContractError):
        bounded_object(value)
    source = {'nested': [True, None, {'ok': 1}]}
    detached = bounded_object(source)
    source['nested'].clear()
    assert detached == {'nested': [True, None, {'ok': 1}]}


@pytest.mark.parametrize('changes', [{'domain_version': 2**31}, {'domain_version': True},
                                    {'domain_id': 'Company'}, {'domain_sha256': 'A' * 64},
                                    {'policy_version': 'guess'}])
def test_context(changes):
    with pytest.raises(ContractError):
        replace(CONTEXT, **changes)


@pytest.mark.parametrize('kind,ids', [('merge', [A]), ('override', [A, B]), ('merge', [A, A]),
                                    ('unknown', [A]), ('split_new', []), ('merge', ['bad', B])])
def test_entity_envelope(kind, ids):
    with pytest.raises(ContractError):
        entities(kind, ids)


def test_supported_intents():
    assert expected_versions('merge', {B: 2, A: 1}) == dict(sorted({A: 1, B: 2}.items()))
    assert intent_payload('merge', {'survivor_id': A}, {A: 1, B: 1}) == {'survivor_id': A}
    assert intent_payload('override', {'field': 'city', 'value': None}, {A: 1})['value'] is None
    assert intent_payload('restore_merge', {'event_id': B}, {A: 1, B: 2}) == {'event_id': B}
    assert intent_payload('split_new', {'members': [{'source_id': 'erp', 'source_key': 'b'},
                         {'source_id': 'erp', 'source_key': 'a'}]}, {A: 1})['members'][0]['source_key'] == 'a'


@pytest.mark.parametrize('kind,payload', [
    ('merge', {'survivor_id': str(uuid4())}), ('merge', {'survivor_id': A, 'extra': 1}),
    ('override', {'field': 'record_kind', 'value': 'company'}),
    ('override', {'field': 'city', 'value': []}), ('restore_merge', {'event_id': 'bad'}),
    ('split_new', {'members': []}), ('split_new', {'members': [{'bad': 1}]}),
])
def test_intent_shape(kind, payload):
    with pytest.raises(ContractError):
        intent_payload(kind, payload, {A: 1, B: 1})


@pytest.mark.parametrize('actor,reason,key', [(' ', 'why', 'key'), ('a', '', 'key'),
                                           ('a', 'why', ' key'), ('a', 'x' * 4097, 'key')])
def test_required_audit_fields(actor, reason, key):
    with pytest.raises(ContractError):
        command(CONTEXT, 'claim', {}, actor, reason, key)


def test_canonical_command_is_detached_and_binds_context_reason():
    args = {'a': [1]}
    request = command(CONTEXT, 'claim', args, 'actor', 'why', 'key')
    args['a'].append(2)
    assert request['arguments']['a'] == [1]
    assert request != command(CONTEXT, 'claim', {'a': [1]}, 'actor', 'changed', 'key')
