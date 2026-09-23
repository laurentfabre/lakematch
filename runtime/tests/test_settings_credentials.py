from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lakematch.mastering.access_contract import AccessUnavailable
from lakematch.mastering.contracts import ContractError, DomainContract
from lakematch_runtime.connection import Connections, Credential, Credentials, app_credentials
from lakematch_runtime.settings import Binding

ROOT = Path(__file__).resolve().parents[2]
USER = '11111111-1111-1111-1111-111111111111'


def definition():
    domain = DomainContract.from_dict(json.loads((ROOT/'examples/mastering/company_pilot/domain.json').read_text()))
    return {'schema_version': 1, 'schema': 'lm_control', 'app_name': 'runtime-fixture',
            'workspace_host': 'https://workspace.example.invalid', 'workspace_id': '1234',
            'endpoint': 'projects/fixture/branches/test/endpoints/primary',
            'database_resource': 'projects/fixture/branches/test/databases/postgres',
            'host': 'database.example.invalid', 'database': 'postgres',
            'contexts': [{'domain_id': 'company', 'domain_version': 1, 'domain_sha256': domain.sha256}]}


def environment(binding):
    return {'DATABRICKS_APP_NAME': binding.app_name, 'DATABRICKS_HOST': binding.workspace_host,
            'DATABRICKS_WORKSPACE_ID': binding.workspace_id, 'LAKEBASE_ENDPOINT': binding.endpoint,
            'PGHOST': binding.host, 'PGPORT': '5432', 'PGDATABASE': binding.database,
            'PGUSER': USER, 'PGSSLMODE': 'require', 'DATABRICKS_CLIENT_ID': USER,
            'DATABRICKS_CLIENT_SECRET': 'synthetic-only-secret', 'DATABRICKS_APP_PORT': '8000'}


@pytest.mark.parametrize('key', ['app_name', 'workspace_host', 'workspace_id', 'endpoint', 'database_resource',
                               'host', 'database', 'contexts', 'schema', 'schema_version'])
def test_explicit_binding_fields_required(key):
    value = definition()
    del value[key]
    with pytest.raises(ContractError):
        Binding.from_dict(value)


@pytest.mark.parametrize('key,value', [('workspace_host', 'http://workspace.example.invalid'),
    ('workspace_host', 'https://user:password@workspace.example.invalid'),
    ('database_resource', 'projects/other/branches/test/databases/postgres'), ('contexts', []),
    ('schema', 'public'), ('schema_version', True), ('host', 'host password=secret')])
def test_binding_rejects_cross_resource_and_unsupported_values(key, value):
    with pytest.raises(ContractError):
        Binding.from_dict({**definition(), key: value})


def test_binding_file_bounded_unique_and_explicit(tmp_path):
    path = tmp_path/'binding.json'
    path.write_text(json.dumps(definition()))
    assert Binding.load(path) == Binding.from_dict(definition())
    path.write_text('{"schema_version":1,"schema_version":1}')
    with pytest.raises(ContractError):
        Binding.load(path)
    path.write_bytes(b' '*65537)
    with pytest.raises(ContractError):
        Binding.load(path)


@pytest.mark.parametrize('key', ['DATABRICKS_APP_NAME', 'DATABRICKS_HOST', 'DATABRICKS_WORKSPACE_ID',
    'LAKEBASE_ENDPOINT', 'PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'PGSSLMODE',
    'DATABRICKS_CLIENT_ID', 'DATABRICKS_CLIENT_SECRET'])
def test_environment_cannot_fall_back_or_mismatch_binding(key):
    binding = Binding.from_dict(definition())
    env = environment(binding)
    assert binding.validate_environment(env) == USER
    env.pop(key)
    with pytest.raises(ContractError):
        binding.validate_environment(env)


def test_profile_and_personal_token_are_not_fallbacks():
    binding = Binding.from_dict(definition())
    for key in ('DATABRICKS_TOKEN', 'DATABRICKS_CONFIG_PROFILE'):
        with pytest.raises(ContractError):
            binding.validate_environment({**environment(binding), key: 'unwanted-fallback'})


def test_credentials_renew_before_expiry_and_single_concurrent_generation():
    now = datetime(2026, 9, 23, tzinfo=timezone.utc)
    elapsed, generated = [0], []
    def generate():
        generated.append(len(generated))
        return Credential('synthetic-'+str(len(generated)), now+timedelta(seconds=elapsed[0]+3600))
    cache = Credentials(generate, now=lambda: now+timedelta(seconds=elapsed[0]), monotonic=lambda: elapsed[0])
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(lambda _: cache.current(), range(4))) == ['synthetic-1']*4
    elapsed[0] = 1799
    assert cache.current() == 'synthetic-1'
    elapsed[0] = 1800
    assert cache.current() == 'synthetic-2'
    cache.invalidate()
    assert cache.current() == 'synthetic-3'


@pytest.mark.parametrize('offset', [-1, 0, 120])
def test_expired_or_nearly_expired_credentials_are_refused(offset):
    now = datetime.now(timezone.utc)
    cache = Credentials(lambda: Credential('synthetic', now+timedelta(seconds=offset)), now=lambda: now)
    with pytest.raises(AccessUnavailable):
        cache.current()


def test_refresh_failure_does_not_fall_back_to_stale_token_or_disclose_secret():
    now = datetime.now(timezone.utc)
    elapsed = [0]
    def generate():
        if elapsed[0]:
            raise RuntimeError('secret-from-provider')
        return Credential('synthetic', now+timedelta(hours=1))
    cache = Credentials(generate, now=lambda: now+timedelta(seconds=elapsed[0]), monotonic=lambda: elapsed[0])
    assert cache.current() == 'synthetic'
    elapsed[0] = 1800
    for _ in range(2):
        with pytest.raises(AccessUnavailable) as error:
            cache.current()
        assert 'secret-from-provider' not in str(error.value)
        assert error.value.__suppress_context__
    assert 'synthetic' not in repr(Credential('synthetic', now))


def test_sdk_uses_explicit_service_oauth_and_endpoint(monkeypatch):
    from databricks import sdk
    from databricks.sdk import core
    from google.protobuf.timestamp_pb2 import Timestamp
    binding = Binding.from_dict(definition())
    seen = {}
    expires = Timestamp()
    expires.FromDatetime(datetime.now(timezone.utc)+timedelta(hours=1))
    def config(**kwargs):
        seen.update(kwargs)
        return kwargs
    def generate(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(token='synthetic-credential', expire_time=expires)
    monkeypatch.setattr(core, 'Config', config)
    monkeypatch.setattr(sdk, 'WorkspaceClient', lambda **_: SimpleNamespace(postgres=SimpleNamespace(generate_database_credential=generate)))
    assert app_credentials(binding, environment(binding)).current() == 'synthetic-credential'
    assert seen['host'] == binding.workspace_host and seen['auth_type'] == 'oauth-m2m'
    assert seen['client_id'] == USER and seen['endpoint'] == binding.endpoint
    assert seen['http_timeout_seconds'] == 10 and seen['retry_timeout_seconds'] == 20


def test_connections_close_and_never_replay_business_work():
    binding = Binding.from_dict(definition())
    calls, closed, checked = [], [], []
    cache = Credentials(lambda: Credential('synthetic', datetime.now(timezone.utc)+timedelta(hours=1)))
    def connect(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(close=lambda: closed.append(True))
    connections = Connections(binding, USER, cache, lambda c: checked.append(c), connect=connect)
    with pytest.raises(RuntimeError, match='lost acknowledgement'):
        with connections.connection():
            raise RuntimeError('lost acknowledgement')
    assert len(calls) == len(closed) == len(checked) == 1
    assert calls[0]['sslmode'] == 'verify-full' and calls[0]['sslrootcert'] == 'system'
    assert calls[0]['connect_timeout'] == 10 and calls[0]['autocommit'] is True


def test_bad_connection_check_closes_socket_and_clears_credentials():
    binding = Binding.from_dict(definition())
    closed, generated = [], []
    def generate():
        generated.append(True)
        return Credential('synthetic', datetime.now(timezone.utc)+timedelta(hours=1))
    def verify(_):
        raise RuntimeError('sensitive-driver-message')
    connections = Connections(binding, USER, Credentials(generate), verify,
        connect=lambda **_: SimpleNamespace(close=lambda: closed.append(True)))
    for _ in range(2):
        with pytest.raises(AccessUnavailable) as error:
            with connections.connection():
                pytest.fail('Refused connection yielded')
        assert 'sensitive-driver-message' not in str(error.value)
    assert len(closed) == len(generated) == 2


def test_connection_capacity_is_finite_and_released_after_failure():
    from contextlib import ExitStack
    binding = Binding.from_dict(definition())
    cache = Credentials(lambda: Credential('synthetic', datetime.now(timezone.utc)+timedelta(hours=1)))
    connections = Connections(binding, USER, cache, lambda _: None,
                              connect=lambda **_: SimpleNamespace(close=lambda: None))
    with ExitStack() as stack:
        for _ in range(4):
            stack.enter_context(connections.connection())
        with pytest.raises(AccessUnavailable, match='capacity'):
            stack.enter_context(connections.connection())
    with connections.connection():
        pass
