"""Owned PostgreSQL with packaged migrations; OAuth/Apps/TLS are simulated."""
from datetime import datetime, timedelta, timezone
from importlib.resources import files
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

if os.environ.get('LAKEMATCH_TEST_POSTGRES') != '1':
    pytest.skip('Explicit private PostgreSQL opt-in required', allow_module_level=True)

import psycopg
from psycopg import sql
from fastapi.testclient import TestClient

from lakematch.mastering.access_contract import AccessUnavailable
from lakematch.mastering.access_registry import PostgresAccessRegistry, grant_workflow_role
from lakematch.mastering.contracts import DomainContract
from lakematch.mastering.identity_contract import IdentityContext, SourceRef
from lakematch.mastering.identity_registry import PostgresIdentityRegistry
from lakematch.mastering.registry import PostgresRegistry, apply_migrations
from lakematch_runtime.app import create_deployed_app
from lakematch_runtime.connection import Connections, Credential, Credentials
from lakematch_runtime.preflight import expected_migrations, verify_connection
from lakematch_runtime.settings import Binding

from test_settings_credentials import ROOT, USER, definition, environment

sys.path.insert(0, str(ROOT/'tools'))
from local_postgres import LocalPostgres


@pytest.fixture(scope='module')
def postgres():
    with LocalPostgres() as server:
        yield server
    assert server.cleanup == 'owned Postgres stopped' and not server.base.exists()


@pytest.fixture
def fixture(postgres):
    with postgres.connect() as connection:
        connection.execute('DROP SCHEMA IF EXISTS lm_control CASCADE')
        if connection.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (USER,)).fetchone():
            connection.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(USER)))
            connection.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(USER)))
        apply_migrations(connection, files('lakematch_runtime').joinpath('migrations'))
        connection.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB').format(sql.Identifier(USER)))
        grant_workflow_role(connection, USER)
    binding = Binding.from_dict(definition())
    domain = DomainContract.from_dict(json.loads((ROOT/'examples/mastering/company_pilot/domain.json').read_text()))
    registry = PostgresRegistry(postgres.connect)
    registry.submit_domain(domain, actor='operator', expected_latest=0)
    registry.transition('domain', 'company', 'company', 1, state='approved', expected_revision=1,
                        actor='reviewer', reason='Synthetic deployment fixture')
    master = PostgresIdentityRegistry(postgres.connect, IdentityContext('company', 1, domain.sha256)).allocate(
        [SourceRef('erp_vendor', 'synthetic')], actor='operator', reason='Fixture', key='identity')['result']['master_id']
    PostgresAccessRegistry(postgres.connect).replace('databricks:1234:alice', 'company',
        [{'role': 'steward', 'fields': None, 'object_ids': [master]}], expected_revision=0,
        actor='operator', reason='Synthetic fixture', key='grant')
    def connect(**requested):
        assert requested['host'] == binding.host and requested['sslmode'] == 'verify-full'
        return psycopg.connect(host=str(postgres.socket), port=postgres.port, dbname='postgres', user=USER,
            connect_timeout=3, autocommit=True, options=requested['options'])
    cache = Credentials(lambda: Credential('synthetic-no-network', datetime.now(timezone.utc)+timedelta(hours=1)))
    connections = Connections(binding, USER, cache, lambda c: verify_connection(c, binding, USER), connect=connect)
    return binding, connections, master


def test_installed_migrations_readiness_and_schema_unchanged(fixture, postgres):
    binding, connections, _ = fixture
    before = expected_migrations()
    with connections.connection() as connection:
        assert connection.execute('SELECT current_user').fetchone()[0] == USER
        assert connection.execute('SHOW search_path').fetchone()[0] == 'pg_catalog'
        assert connection.execute('SHOW statement_timeout').fetchone()[0] == '15s'
        assert dict(connection.execute('SELECT version,sha256 FROM lm_control.schema_migration').fetchall()) == before
    with postgres.connect() as connection:
        assert dict(connection.execute('SELECT version,sha256 FROM lm_control.schema_migration').fetchall()) == before


@pytest.mark.parametrize('statement', [
    'GRANT UPDATE ON lm_control.access_policy TO {}',
    'GRANT UPDATE ON lm_control.schema_migration TO {}',
    'GRANT UPDATE(revision) ON lm_control.master_identity TO {}',
    'GRANT UPDATE(domain_id) ON lm_control.master_identity TO {} WITH GRANT OPTION',
    'GRANT SELECT ON lm_control.outbox_event TO {}',
    'GRANT SELECT ON lm_control.workflow_command TO {} WITH GRANT OPTION',
    'GRANT CREATE ON SCHEMA lm_control TO {}',
    'ALTER ROLE {} CREATEDB',
    'ALTER SCHEMA lm_control OWNER TO {}',
    'REVOKE INSERT ON lm_control.outbox_event FROM {}',
    'REVOKE USAGE ON SEQUENCE lm_control.workflow_command_sequence_seq FROM {}',
])
def test_preflight_refuses_elevated_or_missing_permissions(fixture, postgres, statement):
    _, connections, _ = fixture
    with postgres.connect() as connection:
        connection.execute(sql.SQL(statement).format(sql.Identifier(USER)))
    with pytest.raises(AccessUnavailable):
        with connections.connection():
            pytest.fail('Unqualified role admitted')


@pytest.mark.parametrize('statement', [
    "UPDATE lm_control.schema_migration SET sha256=repeat('0',64) WHERE version=6",
    'DELETE FROM lm_control.schema_migration WHERE version=6',
    "INSERT INTO lm_control.schema_migration(version,sha256) VALUES (7,repeat('0',64))",
])
def test_preflight_refuses_migration_drift_without_repair(fixture, postgres, statement):
    _, connections, _ = fixture
    with postgres.connect() as connection:
        connection.execute(statement)
        before = connection.execute('SELECT version,sha256 FROM lm_control.schema_migration ORDER BY version').fetchall()
    with pytest.raises(AccessUnavailable):
        with connections.connection():
            pytest.fail('Unqualified migrations admitted')
    with postgres.connect() as connection:
        assert connection.execute('SELECT version,sha256 FROM lm_control.schema_migration ORDER BY version').fetchall() == before


def test_domain_retirement_and_owner_identity_are_refused(fixture, postgres):
    binding, connections, _ = fixture
    with postgres.connect() as connection, pytest.raises(AccessUnavailable):
        verify_connection(connection, binding, USER)
    PostgresRegistry(postgres.connect).transition('domain', 'company', 'company', 1, state='retired',
        expected_revision=2, actor='operator', reason='Retire fixture')
    with pytest.raises(AccessUnavailable):
        with connections.connection():
            pytest.fail('Retired domain admitted')


@pytest.fixture
def http(fixture, monkeypatch):
    binding, connections, master = fixture
    from lakematch_review.backend.core import _defaults
    # Existing Delta review dependency has no live calls in this local check.
    monkeypatch.setattr(_defaults, 'WorkspaceClient', lambda **_: SimpleNamespace())
    monkeypatch.setattr(_defaults, 'DatabricksConfig', lambda **kwargs: kwargs)
    env = environment(binding)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv('DATABRICKS_TOKEN', raising=False)
    monkeypatch.delenv('DATABRICKS_CONFIG_PROFILE', raising=False)
    monkeypatch.setenv('LAKEMATCH_REVIEW_STORE', 'delta')
    monkeypatch.setenv('LAKEMATCH_REVIEW_WAREHOUSE_ID', 'synthetic-warehouse')
    monkeypatch.setenv('LAKEMATCH_REVIEW_SCHEMA_NAME', 'synthetic_catalog.fixture')
    with TestClient(create_deployed_app(binding=binding, connections=connections, env=env)) as client:
        yield client, master


def test_packaged_app_startup_http_restart_and_revocation(http, postgres):
    client, master = http
    headers = {'X-Forwarded-User': 'alice', 'Idempotency-Key': 'create'}
    body = {'kind': 'override', 'entity_ids': [master], 'evidence': {}, 'reason': 'Synthetic'}
    response = client.post('/api/v1/domains/company/tasks', json=body, headers=headers)
    assert response.status_code == 200, response.text
    first = response.json()
    postgres.restart()
    assert client.post('/api/v1/domains/company/tasks', json=body, headers=headers).json() == first
    PostgresAccessRegistry(postgres.connect).replace('databricks:1234:alice', 'company', [], expected_revision=1,
        actor='operator', reason='Revoke fixture', key='revoke')
    assert client.post('/api/v1/domains/company/tasks', json=body, headers=headers).status_code == 403
    assert client.get('/api/v1/domains/company/tasks').status_code == 401


def test_permission_drift_after_startup_refuses_next_request(http, postgres):
    client, _ = http
    with postgres.connect() as connection:
        connection.execute(sql.SQL('GRANT UPDATE ON lm_control.access_policy TO {}').format(sql.Identifier(USER)))
    response = client.get('/api/v1/domains/company/tasks', headers={'X-Forwarded-User': 'alice'})
    assert response.status_code == 503 and response.json() == {'detail': 'Workflow service is temporarily unavailable'}


def test_mixed_engine_installation_is_refused(monkeypatch):
    from lakematch_runtime import app
    monkeypatch.setattr(app, 'version', lambda _: '0.1.0')
    with pytest.raises(AccessUnavailable, match='isolated'):
        app.create_deployed_app(env={})
