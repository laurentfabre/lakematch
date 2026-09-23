"""Fresh deployment bootstrap keeps serving and operator permissions separate."""
import sys
import os
import hashlib
from pathlib import Path

import pytest

if os.environ.get('LAKEMATCH_TEST_POSTGRES') != '1':
    pytest.skip('Explicit private PostgreSQL opt-in required', allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
sys.path.insert(0, str(ROOT/'runtime/src'))
from local_postgres import LocalPostgres
from workflow_bootstrap import bootstrap
from lakematch_runtime.preflight import verify_connection
from lakematch_runtime.settings import Binding


def test_bootstrap_and_redeployment_preserve_owned_schema():
    with LocalPostgres() as server:
        with server.connect() as connection:
            connection.execute('CREATE ROLE bootstrap_serving LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE')
        result = bootstrap(server.connect, 'bootstrap_serving', 'synthetic_operator')
        assert len(result['migrations']) == 6
        with server.connect() as connection:
            assert connection.execute('SELECT count(*) FROM lm_control.master_identity').fetchone() == (1,)
            assert connection.execute('SELECT count(*) FROM lm_control.source_identity').fetchone() == (2,)
        import psycopg
        with psycopg.connect(host=str(server.socket), port=server.port, dbname='postgres',
                             user='bootstrap_serving', connect_timeout=3) as connection:
            binding = Binding.load(ROOT/'runtime/binding.example.json')
            # This binding is a fixture; only its database differs locally.
            from dataclasses import replace
            binding = replace(binding, database=connection.info.dbname)
            migrations = {int(p.name[:4]): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (ROOT/'app/migrations/mastering').glob('*.sql')}
            verify_connection(connection, binding, 'bootstrap_serving', migrations=migrations)
        with pytest.raises(ValueError, match='preserve existing'):
            bootstrap(server.connect, 'bootstrap_serving', 'synthetic_operator')
