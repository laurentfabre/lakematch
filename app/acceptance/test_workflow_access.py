"""Real APX HTTP -> current grants -> PostgreSQL workflow integration.

Run only in the prepared Python 3.12 app environment with explicit PostgreSQL
opt-in. The platform envelope is simulated; no live authentication is claimed.
"""
import os
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

if os.environ.get('LAKEMATCH_TEST_POSTGRES') != '1':
    pytest.skip('Opt in with LAKEMATCH_TEST_POSTGRES=1', allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tests/postgres'))
from test_workflow import postgres, fixture, task, counts
from test_access import grants, configure_role, role_connection

from lakematch.mastering.workflow_api import WorkflowAPI
from lakematch_review.backend.app import create_review_app

BASE = '/api/v1/domains/company'


def principal(user):
    return 'databricks:1234:' + user


def headers(user, key=None):
    return {'X-Forwarded-User': user, **({'Idempotency-Key': key} if key else {})}


@pytest.fixture
def http(fixture, postgres, tmp_path, monkeypatch):
    configure_role(postgres)
    api = WorkflowAPI(lambda: role_connection(postgres), [fixture[0].context])
    grants(postgres, principal('alice'))
    grants(postgres, principal('bob'), 'approver')
    grants(postgres, principal('viewer'), 'viewer')
    monkeypatch.delenv('DATABRICKS_APP_NAME', raising=False)
    monkeypatch.setenv('LAKEMATCH_REVIEW_STORE', 'sqlite')
    monkeypatch.setenv('LAKEMATCH_REVIEW_DATABASE', str(tmp_path/'labels.sqlite'))
    with TestClient(create_review_app(api)) as client:
        monkeypatch.setenv('DATABRICKS_APP_NAME', 'fixture-only')
        monkeypatch.setenv('DATABRICKS_WORKSPACE_ID', '1234')
        yield client, fixture


def post(client, path, body, user='alice', key='one', status=200):
    response = client.post(BASE+path, json=body, headers=headers(user, key))
    assert response.status_code == status, response.text
    assert response.headers['cache-control'] == 'no-store'
    return response.json()


def create(http, key='create'):
    client, fixture = http
    return post(client, '/tasks', {'kind': 'merge', 'entity_ids': fixture[2],
                                 'evidence': {'review': 'synthetic'}, 'reason': 'Review fixture'}, key=key)


def pending(http):
    client, fixture = http
    created = create(http)['result']['task']
    claimed = post(client, f"/tasks/{created['task_id']}/claim",
                   {'expected_revision': 1, 'seconds': 60, 'reason': 'Claim fixture'}, key='claim')
    lease = claimed['result']['task']
    proposal = post(client, f"/tasks/{created['task_id']}/propose", {
        'expected_revision': 2, 'lease_token': lease['lease_token'], 'versions': {i: 1 for i in fixture[2]},
        'payload': {'survivor_id': fixture[2][0]}, 'evidence': {'accepted': True}, 'reason': 'Reviewed'}, key='propose')
    return created, proposal['result']['operation']


def test_full_http_lifecycle_independent_approval_and_exact_retry(http, postgres):
    client, _ = http
    task, op = pending(http)
    assert task['definition']['actor'] == principal('alice')
    body = {'expected_revision': 1, 'reason': 'Independent review'}
    post(client, f"/operations/{op['operation_id']}/approve", body, key='self', status=403)
    approved = post(client, f"/operations/{op['operation_id']}/approve", body, user='bob', key='approve')
    assert approved['result']['operation']['approved_by'] == principal('bob')
    assert approved['authorization']['principal'] == principal('bob')
    assert approved['authorization']['revision'] == 1
    assert post(client, f"/operations/{op['operation_id']}/approve", body, user='bob', key='approve') == approved
    response = client.get(BASE+f"/tasks/{task['task_id']}/history", headers=headers('viewer'))
    assert response.status_code == 200 and len(response.json()['items']) == 4
    assert counts(postgres)['outbox_event'] == 1


def test_http_denies_revoked_retry_and_all_read_paths(http, postgres):
    client, _ = http
    task, op = pending(http)
    grants(postgres, principal('alice'), revision=1, rows=[])
    for suffix in ('/tasks', f"/tasks/{task['task_id']}", f"/tasks/{task['task_id']}/history",
                   f"/operations/{op['operation_id']}", f"/operations/{op['operation_id']}/history"):
        response = client.get(BASE+suffix, headers=headers('alice'))
        assert response.status_code == 403
        assert response.headers['cache-control'] == 'no-store'
        assert task['task_id'] not in response.text and 'synthetic' not in response.text
    post(client, f"/tasks/{task['task_id']}/claim", {'expected_revision': 1, 'seconds': 60, 'reason': 'Claim fixture'}, key='claim', status=403)


@pytest.mark.parametrize('user,status', [('viewer', 403), ('bob', 403), ('unknown', 403)])
def test_http_denied_mutations_have_no_database_effect(http, postgres, user, status):
    client, fixture = http
    before = counts(postgres)
    post(client, '/tasks', {'kind': 'merge', 'entity_ids': fixture[2], 'evidence': {}, 'reason': 'Attempt'},
         user=user, key='attempt', status=status)
    assert counts(postgres) == before


def test_http_scoped_list_and_missing_object_do_not_disclose_hidden_tasks(http, postgres):
    client, fixture = http
    created = create(http)['result']['task']
    grants(postgres, principal('limited'), 'viewer', objects=fixture[2][:1])
    assert client.get(BASE+'/tasks', headers=headers('limited')).json() == {'items': [], 'next': None}
    hidden = client.get(BASE+f"/tasks/{created['task_id']}", headers=headers('limited'))
    missing = client.get(BASE+'/tasks/00000000-0000-0000-0000-000000000000', headers=headers('limited'))
    assert hidden.status_code == missing.status_code == 404 and hidden.json() == missing.json()


def test_http_domain_field_scope_and_cursor_revision(http, postgres):
    client, _ = http
    create(http)
    create(http, 'second')
    first = client.get(BASE+'/tasks?limit=1', headers=headers('viewer')).json()
    assert first['next']
    grants(postgres, principal('viewer'), 'viewer', revision=1, fields=['city'])
    assert client.get(BASE+'/tasks', headers=headers('viewer')).status_code == 403
    grants(postgres, principal('viewer'), 'viewer', revision=2)
    import json
    assert client.get(BASE+'/tasks', params={'after': json.dumps(first['next'])}, headers=headers('viewer')).status_code == 422
    assert client.get('/api/v1/domains/other/tasks', headers=headers('viewer')).status_code == 404


def test_http_restart_retains_operation_and_revocation(http, postgres):
    client, _ = http
    task, op = pending(http)
    before = client.get(BASE+f"/operations/{op['operation_id']}", headers=headers('bob')).json()
    grants(postgres, principal('alice'), revision=1, rows=[])
    postgres.restart()
    assert client.get(BASE+f"/operations/{op['operation_id']}", headers=headers('bob')).json() == before
    assert client.get(BASE+f"/tasks/{task['task_id']}", headers=headers('alice')).status_code == 403
