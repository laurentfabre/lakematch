"""Audited grant replacement by trusted operators and transaction-scoped reads."""
from contextlib import contextmanager
from datetime import timezone
from uuid import uuid4

from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .access_contract import AccessDenied, AccessSnapshot, AccessUnavailable, grant_set
from .contracts import ContractError, digest
from .identity_contract import text_key
from .policy import Grant
from .workflow_contract import WorkflowConflict, bounded_object


def lock_key(cursor, actor, key):
    lock = int(digest([actor, key])[:8], 16)
    cursor.execute('SELECT pg_advisory_xact_lock(127936,%s)',
                   (lock if lock < 2**31 else lock - 2**32,))


def read_access(cursor, principal, domain_id):
    """Hold the subject share lock until the business transaction completes."""
    cursor.execute('SELECT 1 FROM lm_control.access_subject WHERE domain_id=%s AND principal=%s FOR SHARE',
                   (domain_id, principal))
    if cursor.fetchone() is None:
        raise AccessDenied('Access is not granted')
    cursor.execute('''SELECT p.*,e.request,e.request_sha256,e.receipt,e.receipt_sha256
        FROM lm_control.access_policy p JOIN lm_control.access_event e ON e.event_id=p.event_id
        AND e.domain_id=p.domain_id AND e.principal=p.principal AND e.revision=p.revision
        WHERE p.domain_id=%s AND p.principal=%s''', (domain_id, principal))
    row = cursor.fetchone()
    if row is None:
        raise AccessUnavailable('An intact access policy and audit event are required')
    try:
        definition = grant_set(principal, domain_id, row['definition'].get('grants'))
    except ContractError as error:
        raise AccessUnavailable('Stored access policy is invalid') from error
    if (definition != row['definition'] or digest(definition) != row['definition_sha256']
            or digest(row['request']) != row['request_sha256']
            or digest(row['receipt']) != row['receipt_sha256']
            or row['request'].get('definition') != definition
            or row['receipt'].get('definition_sha256') != row['definition_sha256']
            or row['receipt'].get('revision') != row['revision']):
        raise AccessUnavailable('Access policy integrity check failed')
    grants = tuple(Grant(principal, domain_id, g['role'],
                        frozenset(g['fields']) if g['fields'] is not None else None,
                        frozenset(g['object_ids']) if g['object_ids'] is not None else None)
                   for g in definition['grants'])
    return AccessSnapshot(principal, domain_id, row['revision'], row['definition_sha256'], grants)


class PostgresAccessRegistry:
    """Operator-only interface. No HTTP grant-management endpoint is exposed."""
    def __init__(self, connect):
        self._connect = connect

    @contextmanager
    def _transaction(self):
        with self._connect() as connection, connection.transaction():
            connection.execute("SET LOCAL lock_timeout='5s'")
            connection.execute("SET LOCAL statement_timeout='15s'")
            with connection.cursor(row_factory=dict_row) as cursor:
                yield cursor

    def replace(self, principal, domain_id, grants, *, expected_revision, actor, reason, key):
        definition = grant_set(principal, domain_id, grants)
        if type(expected_revision) is not int or not 0 <= expected_revision < 2**63 - 1:
            raise ContractError('Expected access revision must be a bounded nonnegative integer')
        text_key(actor, 'Operator')
        text_key(reason, 'Reason', 4096)
        text_key(key, 'Idempotency key')
        request = bounded_object({'definition': definition, 'expected_revision': expected_revision,
                                  'actor': actor, 'reason': reason}, maximum=300000)
        with self._transaction() as cursor:
            lock_key(cursor, actor, key)
            cursor.execute('SELECT * FROM lm_control.access_event WHERE actor=%s AND idempotency_key=%s', (actor, key))
            prior = cursor.fetchone()
            if prior:
                if digest(prior['request']) != prior['request_sha256'] or digest(prior['receipt']) != prior['receipt_sha256']:
                    raise AccessUnavailable('Access audit integrity check failed')
                if prior['request_sha256'] != digest(request):
                    raise WorkflowConflict('Access command key already used')
                return prior['receipt']
            cursor.execute('INSERT INTO lm_control.access_subject(domain_id,principal) VALUES (%s,%s) ON CONFLICT DO NOTHING',
                           (domain_id, principal))
            cursor.execute('SELECT 1 FROM lm_control.access_subject WHERE domain_id=%s AND principal=%s FOR UPDATE',
                           (domain_id, principal))
            cursor.execute('SELECT revision FROM lm_control.access_policy WHERE domain_id=%s AND principal=%s',
                           (domain_id, principal))
            prior = cursor.fetchone()
            if (prior['revision'] if prior else 0) != expected_revision:
                raise WorkflowConflict('Stale access policy revision')
            event_id = str(uuid4())
            cursor.execute('SELECT clock_timestamp() AS at')
            at = cursor.fetchone()['at'].astimezone(timezone.utc)
            receipt = {'event_id': event_id, 'principal': principal, 'domain_id': domain_id,
                       'revision': expected_revision + 1, 'definition_sha256': digest(definition),
                       'actor': actor, 'reason': reason, 'recorded_at': at.isoformat(), 'idempotency_key': key}
            cursor.execute('''INSERT INTO lm_control.access_event
                (event_id,domain_id,principal,revision,actor,idempotency_key,request_sha256,request,
                 receipt_sha256,receipt,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (event_id, domain_id, principal, expected_revision+1, actor, key, digest(request), Jsonb(request),
                 digest(receipt), Jsonb(receipt), at))
            cursor.execute('''INSERT INTO lm_control.access_policy
                (domain_id,principal,revision,definition,definition_sha256,event_id) VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (domain_id,principal) DO UPDATE SET revision=EXCLUDED.revision,
                definition=EXCLUDED.definition,definition_sha256=EXCLUDED.definition_sha256,event_id=EXCLUDED.event_id''',
                (domain_id, principal, expected_revision+1, Jsonb(definition), digest(definition), event_id))
            return receipt


def grant_workflow_role(connection, role):
    """Explicit operator installation on a pre-created dedicated nonowner role.

    This restricts SQL capabilities, not individual users/rows. Per-user RLS and
    Lakebase/OAuth deployment are separate qualification gates.
    """
    text_key(role, 'Database role', 63)
    with connection.transaction():
        row = connection.execute('''SELECT r.rolsuper,r.rolbypassrls,r.rolcreaterole,r.rolcreatedb,
            EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                   WHERE n.nspname='lm_control' AND c.relowner=r.oid),
            EXISTS(SELECT 1 FROM pg_namespace n WHERE n.nspname='lm_control' AND n.nspowner=r.oid),
            EXISTS(SELECT 1 FROM pg_auth_members m WHERE m.member=r.oid)
            FROM pg_roles r WHERE r.rolname=%s''', (role,)).fetchone()
        if row is None or any(row):
            raise ContractError('Use a dedicated nonowner role without elevated flags or memberships')
        # Do not label a pre-existing broad role as restricted merely because
        # this installer only adds narrow privileges. PUBLIC grants count too.
        for table in ('access_policy', 'access_event', 'access_subject', 'master_identity',
                      'domain_version', 'identity_event', 'source_identity', 'identity_alias'):
            privileges = 'INSERT,DELETE,TRUNCATE'
            if table in {'access_policy', 'access_event'}:
                privileges += ',UPDATE'
            if connection.execute('SELECT has_table_privilege(%s,%s,%s)',
                                  (role, 'lm_control.'+table, privileges)).fetchone()[0]:
                raise ContractError('Role already has broader control-store privileges')
        if connection.execute("SELECT has_schema_privilege(%s,'lm_control','CREATE')", (role,)).fetchone()[0]:
            raise ContractError('Role must not create control-store objects')
        for table in ('master_identity', 'domain_version'):
            if connection.execute('SELECT has_column_privilege(%s,%s,%s,%s)',
                                  (role, 'lm_control.'+table, 'revision', 'UPDATE')).fetchone()[0]:
                raise ContractError('Role must not update identity or domain revisions')
        target = sql.Identifier(role)
        connection.execute(sql.SQL('GRANT USAGE ON SCHEMA lm_control TO {}').format(target))
        for table in ('domain_version', 'registry_event', 'master_identity', 'access_subject', 'access_policy',
                      'access_event', 'steward_task', 'operation', 'steward_decision', 'workflow_command'):
            connection.execute(sql.SQL('GRANT SELECT ON lm_control.{} TO {}').format(sql.Identifier(table), target))
        # The immutable key cannot actually be updated; PostgreSQL nevertheless
        # requires UPDATE privilege on at least one column for a row share lock.
        for table in ('domain_version', 'master_identity', 'access_subject'):
            connection.execute(sql.SQL('GRANT UPDATE (domain_id) ON lm_control.{} TO {}').format(sql.Identifier(table), target))
        for table in ('steward_task', 'operation'):
            connection.execute(sql.SQL('GRANT INSERT,UPDATE ON lm_control.{} TO {}').format(sql.Identifier(table), target))
        for table in ('steward_decision', 'workflow_command', 'outbox_event'):
            connection.execute(sql.SQL('GRANT INSERT ON lm_control.{} TO {}').format(sql.Identifier(table), target))
        connection.execute(sql.SQL('GRANT USAGE ON SEQUENCE lm_control.workflow_command_sequence_seq TO {}').format(target))
