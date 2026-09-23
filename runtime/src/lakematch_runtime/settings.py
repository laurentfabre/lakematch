"""Explicit deployment bindings, separate from secrets injected by Apps."""
from dataclasses import dataclass
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from uuid import UUID

from lakematch.mastering.contracts import ContractError
from lakematch.mastering.workflow_contract import WorkflowContext


def require(condition, message):
    if not condition:
        raise ContractError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate binding key')
        result[key] = value
    return result


@dataclass(frozen=True)
class Binding:
    app_name: str
    workspace_host: str
    workspace_id: str
    endpoint: str
    database_resource: str
    host: str
    database: str
    contexts: tuple[WorkflowContext, ...]

    @classmethod
    def from_dict(cls, data):
        keys = {'schema_version', 'schema', 'app_name', 'workspace_host', 'workspace_id',
                'endpoint', 'database_resource', 'host', 'database', 'contexts'}
        require(isinstance(data, dict) and set(data) == keys, 'Provide exactly the versioned binding fields')
        require(type(data['schema_version']) is int and data['schema_version'] == 1
                and data['schema'] == 'lm_control', 'Unsupported runtime schema binding')
        for name in keys - {'schema_version', 'contexts'}:
            require(isinstance(data[name], str), 'Binding names must be strings')
        require(re.fullmatch(r'[a-z][a-z0-9-]{0,25}', data['app_name']), 'Invalid app name')
        host = urlsplit(data['workspace_host'])
        require(host.scheme == 'https' and host.hostname and host.netloc == host.hostname
                and not host.path and not host.query and not host.fragment, 'Use an explicit HTTPS workspace origin')
        require(re.fullmatch(r'[0-9]{1,32}', data['workspace_id']), 'Invalid workspace ID')
        resource_id = r'[a-z][a-z0-9-]{0,62}'
        branch = rf'projects/{resource_id}/branches/{resource_id}'
        require(re.fullmatch(branch + rf'/endpoints/{resource_id}', data['endpoint']), 'Invalid endpoint binding')
        require(re.fullmatch(branch + rf'/databases/{resource_id}', data['database_resource'])
                and data['endpoint'].split('/endpoints/')[0] == data['database_resource'].split('/databases/')[0],
                'Endpoint and database must belong to the selected branch')
        require(re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?', data['host'])
                and '..' not in data['host'], 'Invalid database hostname')
        require(re.fullmatch(r'[a-z][a-z0-9_]{0,62}', data['database']), 'Invalid database name')
        require(isinstance(data['contexts'], list) and 1 <= len(data['contexts']) <= 32,
                'Bind 1–32 workflow domains')
        contexts = []
        for value in data['contexts']:
            require(isinstance(value, dict) and set(value) == {'domain_id', 'domain_version', 'domain_sha256'},
                    'Explicit domain ID/version/hash required')
            contexts.append(WorkflowContext(**value))
        require(len({c.domain_id for c in contexts}) == len(contexts), 'Duplicate domain binding')
        return cls(**{k: data[k] for k in keys - {'schema_version', 'schema', 'contexts'}}, contexts=tuple(contexts))

    @classmethod
    def load(cls, path):
        with Path(path).open('rb') as handle:
            raw = handle.read(65537)
        require(len(raw) <= 65536, 'Binding exceeds 64 KiB')
        try:
            return cls.from_dict(json.loads(raw, object_pairs_hook=unique))
        except (ValueError, TypeError, RecursionError) as error:
            raise ContractError('Invalid workflow binding') from None

    def validate_environment(self, env):
        expected = {'DATABRICKS_APP_NAME': self.app_name, 'DATABRICKS_HOST': self.workspace_host,
                    'DATABRICKS_WORKSPACE_ID': self.workspace_id, 'LAKEBASE_ENDPOINT': self.endpoint,
                    'PGHOST': self.host, 'PGDATABASE': self.database, 'PGPORT': '5432'}
        require(all(env.get(k) == v for k, v in expected.items()), 'Injected resources do not match the selected binding')
        require(env.get('PGSSLMODE') in {'require', 'verify-full'}, 'TLS is required')
        user = env.get('PGUSER', '')
        try:
            valid_user = str(UUID(user)) == user
        except (ValueError, TypeError, AttributeError):
            valid_user = False
        require(valid_user and env.get('DATABRICKS_CLIENT_ID') == user,
                'PGUSER must match the injected app service principal')
        require(isinstance(env.get('DATABRICKS_CLIENT_SECRET'), str) and bool(env['DATABRICKS_CLIENT_SECRET']),
                'App OAuth credentials are required')
        require(not any(env.get(k) for k in ('DATABRICKS_TOKEN', 'DATABRICKS_CONFIG_PROFILE')),
                'Workflow deployment requires explicit app OAuth credentials')
        return user
