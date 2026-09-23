"""APX identity/transport tests; database behavior is covered by root PostgreSQL tests."""
from dataclasses import dataclass
import json

import pytest
from fastapi.testclient import TestClient

from lakematch_review.backend.app import create_review_app


@dataclass
class Result:
    status: int
    body: dict


class RecordingBackend:
    def __init__(self):
        self.calls = []

    def dispatch(self, principal, domain_id, action, arguments, *, key=None):
        self.calls.append((principal, domain_id, action, arguments, key))
        return Result(200, {'received_as': principal})


@pytest.fixture
def configured(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABRICKS_APP_NAME', raising=False)
    monkeypatch.delenv('DATABRICKS_WORKSPACE_ID', raising=False)
    monkeypatch.setenv('LAKEMATCH_REVIEW_STORE', 'sqlite')
    monkeypatch.setenv('LAKEMATCH_REVIEW_DATABASE', str(tmp_path/'labels.sqlite'))
    backend = RecordingBackend()
    with TestClient(create_review_app(backend)) as client:
        yield client, backend


def proxy(monkeypatch):
    # Simulates the process-side platform envelope, not live authentication proof.
    monkeypatch.setenv('DATABRICKS_APP_NAME', 'fixture-app')
    monkeypatch.setenv('DATABRICKS_WORKSPACE_ID', '1234')
    return {'X-Forwarded-User': '42'}


def test_local_identity_headers_never_enable_mastering(configured):
    client, backend = configured
    for headers in ({}, {'X-Forwarded-User': '42', 'X-Forwarded-Preferred-Username': 'admin'}):
        response = client.get('/api/v1/domains/company/tasks', headers=headers)
        assert response.status_code == 401
        assert response.headers['cache-control'] == 'no-store'
    assert not backend.calls


def test_stable_platform_id_ignores_display_name_and_roles(configured, monkeypatch):
    client, backend = configured
    headers = proxy(monkeypatch)
    for name in ('Alice', 'renamed'):
        response = client.get('/api/v1/domains/company/tasks', headers={**headers,
            'X-Forwarded-Preferred-Username': name, 'X-Roles': 'administrator'})
        assert response.json() == {'received_as': 'databricks:1234:42'}
    assert backend.calls[0] == backend.calls[1]


@pytest.mark.parametrize('headers', [{}, {'X-Forwarded-User': ' '}, {'X-Forwarded-User': '42,43'},
    [('X-Forwarded-User', '42'), ('X-Forwarded-User', '43')]])
def test_missing_or_ambiguous_identity_denied(configured, monkeypatch, headers):
    client, backend = configured
    proxy(monkeypatch)
    response = client.get('/api/v1/domains/company/tasks', headers=headers)
    assert response.status_code == 401 and not backend.calls


def test_unconfigured_backend_fails_closed(configured, monkeypatch):
    client, _ = configured
    headers = proxy(monkeypatch)
    client.app.state.mastering_api = None
    response = client.get('/api/v1/domains/company/tasks', headers=headers)
    assert response.status_code == 503 and response.headers['cache-control'] == 'no-store'


def task_body():
    return {'kind': 'override', 'entity_ids': ['00000000-0000-0000-0000-000000000001'],
            'evidence': {}, 'reason': 'Synthetic edit'}


@pytest.mark.parametrize('field', ['actor', 'principal', 'grants', 'roles', 'context', 'key'])
def test_request_cannot_supply_identity_or_policy(configured, monkeypatch, field):
    client, backend = configured
    response = client.post('/api/v1/domains/company/tasks', headers={**proxy(monkeypatch), 'Idempotency-Key': 'one'},
                           json={**task_body(), field: 'untrusted'})
    assert response.status_code == 422 and not backend.calls


def test_command_key_and_server_actor(configured, monkeypatch):
    client, backend = configured
    headers = proxy(monkeypatch)
    for key in (None, '', ' key '):
        response = client.post('/api/v1/domains/company/tasks', headers={**headers, **({'Idempotency-Key': key} if key is not None else {})}, json=task_body())
        assert response.status_code == 422
    response = client.post('/api/v1/domains/company/tasks', headers={**headers, 'Idempotency-Key': 'one'}, json=task_body())
    assert response.status_code == 200
    assert backend.calls[0][0] == 'databricks:1234:42' and backend.calls[0][-1] == 'one'


@pytest.mark.parametrize('raw,status', [
    ('{"reason":"a","reason":"b"}', 400), ('{"x":NaN}', 400),
    ('{"x":"' + 'a'*65536 + '"}', 413), ('['*1000 + '0' + ']'*1000, 400),
])
def test_body_envelope(configured, monkeypatch, raw, status):
    client, backend = configured
    response = client.post('/api/v1/domains/company/tasks', content=raw,
        headers={**proxy(monkeypatch), 'Idempotency-Key': 'one', 'Content-Type': 'application/json'})
    assert response.status_code == status and not backend.calls
    assert response.headers['cache-control'] == 'no-store'


def test_cursor_and_limit_validation(configured, monkeypatch):
    client, backend = configured
    for params in ({'limit': '101'}, {'after': '[]'}, {'after': 'invalid'}, {'state': 'unknown'}):
        response = client.get('/api/v1/domains/company/tasks', params=params, headers=proxy(monkeypatch))
        assert response.status_code == 422
    assert not backend.calls


def test_all_routes_are_in_actual_apx_openapi(configured):
    client, _ = configured
    paths = client.get('/openapi.json').json()['paths']
    assert len([p for p in paths if p.startswith('/api/v1/')]) == 11
    assert '/api/queue' in paths and '/api/reviews' in paths
