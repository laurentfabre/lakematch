"""Retained deployment checks reject drift without repairing or reseeding data."""
import copy
import os
from pathlib import Path
import sys

import pytest

if os.environ.get('LAKEMATCH_TEST_POSTGRES') != '1':
    pytest.skip('Explicit private PostgreSQL opt-in required', allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
from local_postgres import LocalPostgres
from workflow_bootstrap import bootstrap
from workflow_retained import verify_retained_fixture
from lakematch.mastering.access_registry import PostgresAccessRegistry


@pytest.fixture
def installed():
    with LocalPostgres() as server:
        with server.connect() as connection:
            connection.execute('CREATE ROLE retained_serving LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE')
        result = bootstrap(server.connect, 'retained_serving', 'synthetic_operator')
        yield server, result


def test_verification_survives_restart_and_preserves_receipts(installed):
    server, fixture = installed
    original = copy.deepcopy(fixture)
    before = verify_retained_fixture(server.connect, 'retained_serving', 'synthetic_operator', fixture)
    assert before['transaction_read_only'] == 'on'
    assert before['source_crosswalks'] == 2
    server.restart()
    assert verify_retained_fixture(server.connect, 'retained_serving', 'synthetic_operator', fixture) == before
    assert fixture == original


@pytest.mark.parametrize('change,match', [
    ('operator', 'operator does not match'),
    ('master', 'master identity changed'),
    ('migration', 'Recorded migrations'),
    ('role', 'no longer restricted'),
    ('revocation', 'access policy changed'),
])
def test_refuses_changed_installation(installed, change, match):
    server, fixture = installed
    principal = 'synthetic_operator'
    if change == 'operator':
        principal = 'another_operator'
    elif change == 'master':
        fixture['master_id'] = '00000000-0000-0000-0000-000000000000'
    elif change == 'migration':
        fixture['migrations'][1] = '0' * 64
    elif change == 'role':
        with server.connect() as connection:
            connection.execute('ALTER ROLE retained_serving BYPASSRLS')
    else:
        PostgresAccessRegistry(server.connect).replace(principal, 'company', [], expected_revision=1,
            actor=principal, reason='Revocation must remain effective', key='test-revocation')
    with pytest.raises(ValueError, match=match):
        verify_retained_fixture(server.connect, 'retained_serving', principal, fixture)
    with server.connect() as connection:
        assert connection.execute('SELECT count(*) FROM lm_control.master_identity').fetchone() == (1,)
        assert connection.execute('SELECT count(*) FROM lm_control.workflow_command').fetchone() == (0,)
        if change == 'revocation':
            assert connection.execute('SELECT revision FROM lm_control.access_policy').fetchone() == (2,)
