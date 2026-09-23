"""Bounded owned connections with early OAuth renewal and no command replay."""
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import BoundedSemaphore, Lock
import time

import psycopg
import certifi

from lakematch.mastering.access_contract import AccessUnavailable


@dataclass(frozen=True)
class Credential:
    token: str = field(repr=False)
    expires_at: datetime


class Credentials:
    def __init__(self, generate, *, now=lambda: datetime.now(timezone.utc), monotonic=time.monotonic):
        self._generate, self._now, self._monotonic = generate, now, monotonic
        self._lock, self._token, self._deadline = Lock(), None, 0.0

    def current(self):
        if not self._lock.acquire(timeout=2):
            raise AccessUnavailable('Workflow credential service is busy')
        try:
            if self._token is not None and self._monotonic() < self._deadline:
                return self._token
            self._token = None
            try:
                started = self._monotonic()
                credential = self._generate()
                if (not isinstance(credential, Credential) or not isinstance(credential.token, str)
                        or not 1 <= len(credential.token) <= 16384
                        or not isinstance(credential.expires_at, datetime)
                        or credential.expires_at.utcoffset() is None):
                    raise ValueError('Invalid credential')
                remaining = (credential.expires_at - self._now()).total_seconds()
                if remaining <= 120:
                    raise ValueError('Credential too close to expiry')
                self._deadline = started + min(1800, remaining - 120)
                self._token = credential.token
                return self._token
            except Exception:
                raise AccessUnavailable('Workflow credentials are unavailable') from None
        finally:
            self._lock.release()

    def invalidate(self):
        with self._lock:
            self._token, self._deadline = None, 0.0


def app_credentials(binding, env):
    """Only explicit Apps service-principal OAuth; no profile or user-token fallback."""
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config
    user = binding.validate_environment(env)
    try:
        client = WorkspaceClient(config=Config(host=binding.workspace_host, client_id=user,
            client_secret=env['DATABRICKS_CLIENT_SECRET'], auth_type='oauth-m2m',
            http_timeout_seconds=10, retry_timeout_seconds=20))
    except Exception:
        raise AccessUnavailable('App OAuth configuration is unavailable') from None

    def generate():
        value = client.postgres.generate_database_credential(endpoint=binding.endpoint)
        return Credential(value.token, value.expire_time.ToDatetime(tzinfo=timezone.utc))
    return Credentials(generate)


class Connections:
    """At most four live sockets; each request closes its own connection.

    This preserves the worker's owned-connection contract. Pooling/latency are
    later qualification work. The service never retries a business transaction.
    """
    def __init__(self, binding, user, credentials, verify, *, connect=psycopg.connect):
        self._binding, self._user, self._credentials = binding, user, credentials
        self._verify, self._connect, self._slots = verify, connect, BoundedSemaphore(4)

    @contextmanager
    def connection(self):
        if not self._slots.acquire(timeout=2):
            raise AccessUnavailable('Workflow connection capacity reached')
        connection = None
        try:
            try:
                connection = self._connect(host=self._binding.host, port=5432,
                    dbname=self._binding.database, user=self._user, password=self._credentials.current(),
                    sslmode='verify-full', sslrootcert=certifi.where(), connect_timeout=10, autocommit=True,
                    application_name='lakematch-workflow',
                    options='-c search_path=pg_catalog -c statement_timeout=15000 -c lock_timeout=5000 '
                            '-c idle_in_transaction_session_timeout=20000 -c timezone=UTC')
                self._verify(connection)
            except Exception:
                self._credentials.invalidate()
                raise AccessUnavailable('Workflow connection is unavailable') from None
            yield connection
        finally:
            try:
                if connection is not None:
                    connection.close()
            finally:
                self._slots.release()
