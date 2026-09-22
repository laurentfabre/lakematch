"""Transactional stewardship for trusted workers, independent of HTTP and Spark.

Callers supply authenticated actor IDs after authorization. This adapter does
not grant permissions or apply business changes; approved intents await a worker
that must recheck current entity revisions and business policy before applying.
"""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .contracts import ContractError, digest
from .identity_contract import master_key
from .registry import PostgresRegistry, RegistryConflict, RegistryUnavailable
from .workflow_contract import (
    MAX_PAGE, WorkflowConflict, WorkflowContext, WorkflowUnavailable,
    bounded_object, command, entities, expected_versions, intent_payload,
    lease_seconds, revision,
)


def _json(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json(v) for v in value]
    return value


class PostgresWorkflow:
    def __init__(self, connect, context):
        if not isinstance(context, WorkflowContext):
            raise ContractError('An explicit workflow context is required')
        self._connect, self.context = connect, context

    @contextmanager
    def _transaction(self, *, write=False):
        with self._connect() as connection:
            with connection.transaction():
                if not write:
                    connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                connection.execute("SET LOCAL lock_timeout = '5s'")
                connection.execute("SET LOCAL statement_timeout = '15s'")
                with connection.cursor(row_factory=dict_row) as cursor:
                    yield cursor

    def _domain(self, cursor):
        try:
            domain, _ = PostgresRegistry(self._connect)._domain(
                cursor, self.context.domain_id, self.context.domain_version, approved=True)
        except (RegistryUnavailable, RegistryConflict) as error:
            raise WorkflowUnavailable('An approved domain with intact history is required') from error
        if domain.sha256 != self.context.domain_sha256:
            raise WorkflowUnavailable('Workflow domain digest differs from the approved version')
        return domain

    @staticmethod
    def _now(cursor):
        cursor.execute('SELECT clock_timestamp() AS at')
        return cursor.fetchone()['at']

    def _task(self, cursor, task_id, *, lock=False):
        cursor.execute('SELECT * FROM lm_control.steward_task WHERE domain_id=%s AND task_id=%s'
                       + (' FOR UPDATE' if lock else ''), (self.context.domain_id, task_id))
        row = cursor.fetchone()
        if row is None or row['workflow_schema'] != 1 or row['domain_version'] != self.context.domain_version:
            raise WorkflowUnavailable('Task is absent or outside this workflow version')
        definition = row['definition']
        if digest(definition) != row['definition_sha256'] or definition['context'] != asdict(self.context):
            raise WorkflowUnavailable('Task definition or context differs')
        args = definition['arguments']
        if any(row[k] != args[k] for k in ('kind', 'entity_ids', 'priority')):
            raise WorkflowUnavailable('Task columns differ from immutable definition')
        return _json(row)

    def _operation(self, cursor, operation_id, *, lock=False):
        cursor.execute('SELECT * FROM lm_control.operation WHERE domain_id=%s AND operation_id=%s'
                       + (' FOR UPDATE' if lock else ''), (self.context.domain_id, operation_id))
        row = cursor.fetchone()
        if row is None or row['workflow_schema'] != 1 or row['domain_version'] != self.context.domain_version:
            raise WorkflowUnavailable('Operation is absent or outside this workflow version')
        if digest(row['payload']) != row['payload_sha256'] or row['payload']['context'] != asdict(self.context):
            raise WorkflowUnavailable('Operation intent or context differs')
        if row['payload']['kind'] != row['kind'] or row['payload']['versions'] != row['expected_versions']:
            raise WorkflowUnavailable('Operation columns differ from immutable intent')
        return _json(row)

    @staticmethod
    def _expected(row, value):
        if row['revision'] != value:
            raise WorkflowConflict('Stale revision')

    def _leased(self, cursor, row, args, actor):
        self._expected(row, args['expected_revision'])
        at = self._now(cursor)  # Evaluate after obtaining the row lock, not transaction start.
        if (row['state'] != 'claimed' or row['assignee'] != actor or
                row['lease_token'] != args['lease_token'] or
                datetime.fromisoformat(row['lease_until']) <= at):
            raise WorkflowConflict('A live owned lease and its current token are required')
        return at

    def _masters(self, cursor, ids, versions=None, *, restoring=False):
        # Stable lock order also coordinates with identity updates. Applying an
        # approved operation must recheck these versions again in LM-009/011.
        rows = {}
        for identity in sorted(ids):
            cursor.execute('SELECT revision,state FROM lm_control.master_identity '
                           'WHERE domain_id=%s AND master_id=%s FOR SHARE',
                           (self.context.domain_id, identity))
            row = cursor.fetchone()
            if row is None:
                raise WorkflowConflict('Referenced master is absent from this domain')
            if row['state'] not in ({'active', 'merged'} if restoring else {'active'}):
                raise WorkflowConflict('Referenced master has an incompatible state')
            if versions is not None and row['revision'] != versions[identity]:
                raise WorkflowConflict('Referenced master revision changed')
            rows[identity] = row['revision']
        return rows

    def _save_command(self, cursor, request, key, result):
        at, command_id = self._now(cursor), str(uuid4())
        receipt = {'command_id': command_id, 'context': asdict(self.context),
                   'action': request['action'], 'actor': request['actor'], 'reason': request['reason'],
                   'idempotency_key': key, 'request_sha256': digest(request),
                   'recorded_at': _json(at), 'result': result}
        cursor.execute('''INSERT INTO lm_control.workflow_command
            (command_id,domain_id,domain_version,task_id,operation_id,actor,idempotency_key,
             action,request_sha256,request,receipt_sha256,receipt,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (command_id, self.context.domain_id, self.context.domain_version,
             result.get('task', {}).get('task_id'), result.get('operation', {}).get('operation_id'),
             request['actor'], key, request['action'], digest(request), Jsonb(request),
             digest(receipt), Jsonb(receipt), at))
        return receipt

    @staticmethod
    def _receipt(row):
        if digest(row['request']) != row['request_sha256'] or digest(row['receipt']) != row['receipt_sha256']:
            raise WorkflowUnavailable('Stored command or receipt digest differs')
        return row['receipt']

    def _execute(self, action, args, *, actor, reason, key):
        request = command(self.context, action, args, actor, reason, key)
        # Hash collisions only serialize unrelated requests; the full key is
        # checked below and the unique constraint remains the durable backstop.
        lock = int(digest([actor, key])[:8], 16)
        if lock >= 2**31:
            lock -= 2**32
        with self._transaction(write=True) as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(127935,%s)', (lock,))
            cursor.execute('SELECT * FROM lm_control.workflow_command WHERE actor=%s AND idempotency_key=%s',
                           (actor, key))
            prior = cursor.fetchone()
            if prior:
                receipt = self._receipt(prior)
                if prior['request_sha256'] != digest(request):
                    raise WorkflowConflict('Idempotency key was used for a different command')
                return receipt
            domain = self._domain(cursor)
            result = getattr(self, '_' + action)(cursor, request, key, domain)
            return self._save_command(cursor, request, key, result)

    def create_task(self, kind, entity_ids, *, priority=0, evidence, actor, reason, key):
        if type(priority) is not int or not -1000 <= priority <= 1000:
            raise ContractError('Priority must be an integer in [-1000,1000]')
        args = {'kind': kind, 'entity_ids': entities(kind, entity_ids), 'priority': priority,
                'evidence': bounded_object(evidence)}
        return self._execute('create_task', args, actor=actor, reason=reason, key=key)

    def _create_task(self, cursor, request, key, domain):
        args, task_id = request['arguments'], str(uuid4())
        self._masters(cursor, args['entity_ids'], restoring=args['kind'] == 'restore_merge')
        cursor.execute('''INSERT INTO lm_control.steward_task
            (domain_id,task_id,kind,entity_ids,state,priority,workflow_schema,domain_version,
             definition,definition_sha256,created_at)
            VALUES (%s,%s,%s,%s,'open',%s,1,%s,%s,%s,%s)''',
            (self.context.domain_id, task_id, args['kind'], Jsonb(args['entity_ids']), args['priority'],
             self.context.domain_version, Jsonb(request), digest(request), self._now(cursor)))
        return {'task': self._task(cursor, task_id)}

    def claim(self, task_id, expected_revision, *, seconds, actor, reason, key):
        return self._execute('claim', {'task_id': master_key(task_id),
            'expected_revision': revision(expected_revision), 'seconds': lease_seconds(seconds)},
            actor=actor, reason=reason, key=key)

    def _claim(self, cursor, request, key, domain):
        args = request['arguments']
        row = self._task(cursor, args['task_id'], lock=True)
        self._expected(row, args['expected_revision'])
        at = self._now(cursor)
        if row['state'] != 'open' and not (row['state'] == 'claimed' and
                datetime.fromisoformat(row['lease_until']) <= at):
            raise WorkflowConflict('Task is not open or its lease is still live')
        return self._set_lease(cursor, row, request['actor'], at, args['seconds'])

    def _set_lease(self, cursor, row, actor, at, seconds):
        cursor.execute('''UPDATE lm_control.steward_task SET state='claimed',assignee=%s,
            lease_until=%s,lease_token=%s,revision=revision+1 WHERE domain_id=%s AND task_id=%s''',
            (actor, at + timedelta(seconds=seconds), str(uuid4()), self.context.domain_id, row['task_id']))
        return {'task': self._task(cursor, row['task_id'])}

    def renew(self, task_id, expected_revision, lease_token, *, seconds, actor, reason, key):
        return self._execute('renew', {'task_id': master_key(task_id),
            'expected_revision': revision(expected_revision), 'lease_token': master_key(lease_token),
            'seconds': lease_seconds(seconds)}, actor=actor, reason=reason, key=key)

    def _renew(self, cursor, request, key, domain):
        args = request['arguments']
        row = self._task(cursor, args['task_id'], lock=True)
        at = self._leased(cursor, row, args, request['actor'])
        return self._set_lease(cursor, row, request['actor'], at, args['seconds'])

    def release(self, task_id, expected_revision, lease_token, *, actor, reason, key):
        return self._execute('release', {'task_id': master_key(task_id),
            'expected_revision': revision(expected_revision), 'lease_token': master_key(lease_token)},
            actor=actor, reason=reason, key=key)

    def cancel(self, task_id, expected_revision, *, lease_token=None, actor, reason, key):
        return self._execute('cancel', {'task_id': master_key(task_id),
            'expected_revision': revision(expected_revision),
            'lease_token': master_key(lease_token) if lease_token is not None else None},
            actor=actor, reason=reason, key=key)

    def _clear_lease(self, cursor, task_id, state):
        cursor.execute('''UPDATE lm_control.steward_task SET state=%s,assignee=NULL,
            lease_until=NULL,lease_token=NULL,revision=revision+1 WHERE domain_id=%s AND task_id=%s''',
            (state, self.context.domain_id, task_id))
        return {'task': self._task(cursor, task_id)}

    def _release(self, cursor, request, key, domain):
        args = request['arguments']
        row = self._task(cursor, args['task_id'], lock=True)
        self._leased(cursor, row, args, request['actor'])
        return self._clear_lease(cursor, row['task_id'], 'open')

    def _cancel(self, cursor, request, key, domain):
        args = request['arguments']
        row = self._task(cursor, args['task_id'], lock=True)
        self._expected(row, args['expected_revision'])
        if row['state'] != 'open':
            self._leased(cursor, row, args, request['actor'])
        elif args['lease_token'] is not None:
            raise WorkflowConflict('An open task has no lease token')
        return self._clear_lease(cursor, row['task_id'], 'canceled')

    def propose(self, task_id, expected_revision, lease_token, versions, payload, *, evidence, actor, reason, key):
        if not isinstance(versions, dict) or not 1 <= len(versions) <= 32:
            raise ContractError('An expected-version map with 1–32 entities is required')
        versions = {master_key(k): revision(v) for k, v in versions.items()}
        args = {'task_id': master_key(task_id), 'expected_revision': revision(expected_revision),
                'lease_token': master_key(lease_token),
                'versions': dict(sorted(versions.items())),
                'payload': bounded_object(payload), 'evidence': bounded_object(evidence)}
        return self._execute('propose', args, actor=actor, reason=reason, key=key)

    def _propose(self, cursor, request, key, domain):
        args = request['arguments']
        row = self._task(cursor, args['task_id'], lock=True)
        self._leased(cursor, row, args, request['actor'])
        versions = expected_versions(row['kind'], args['versions'])
        if list(versions) != row['entity_ids']:
            raise WorkflowConflict('Proposal entities differ from the task')
        payload = intent_payload(row['kind'], args['payload'], versions)
        if row['kind'] == 'override':
            fields = {f.name: f for f in domain.fields}
            if payload['field'] not in fields:
                raise ContractError('Override field is outside the approved domain')
            fields[payload['field']].validate(payload['value'])
        self._masters(cursor, row['entity_ids'], versions, restoring=row['kind'] == 'restore_merge')
        # Entity locks can wait: the lease must still be live after that wait.
        self._leased(cursor, row, args, request['actor'])
        cursor.execute('SELECT 1 FROM lm_control.operation WHERE caller=%s AND idempotency_key=%s',
                       (request['actor'], key))
        if cursor.fetchone():
            raise WorkflowConflict('Operation key is already used by another workflow adapter')
        operation_id = str(uuid4())
        intent = {'context': asdict(self.context), 'kind': row['kind'],
                  'versions': versions, 'intent': payload, 'evidence': args['evidence']}
        cursor.execute('''INSERT INTO lm_control.operation
            (operation_id,domain_id,caller,idempotency_key,payload_sha256,expected_versions,
             payload,state,workflow_schema,domain_version,kind,task_id,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'pending_approval',1,%s,%s,%s,%s)''',
            (operation_id, self.context.domain_id, request['actor'], key, digest(intent), Jsonb(versions),
             Jsonb(intent), self.context.domain_version, row['kind'], row['task_id'], self._now(cursor)))
        result = self._clear_lease(cursor, row['task_id'], 'resolved')
        result['decision_id'] = self._decision(cursor, request, row['task_id'], operation_id, 'propose', args['evidence'])
        result['operation'] = self._operation(cursor, operation_id)
        return result

    def _decision(self, cursor, request, task_id, operation_id, action, evidence):
        decision_id = str(uuid4())
        cursor.execute('''INSERT INTO lm_control.steward_decision
            (decision_id,domain_id,task_id,operation_id,actor,action,reason,expected_revision,evidence,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (decision_id, self.context.domain_id, task_id, operation_id, request['actor'], action,
             request['reason'], request['arguments']['expected_revision'], Jsonb(evidence), self._now(cursor)))
        return decision_id

    def approve(self, operation_id, expected_revision, *, actor, reason, key):
        return self._execute('approve', {'operation_id': master_key(operation_id),
            'expected_revision': revision(expected_revision)}, actor=actor, reason=reason, key=key)

    def _approve(self, cursor, request, key, domain):
        args = request['arguments']
        row = self._operation(cursor, args['operation_id'], lock=True)
        self._expected(row, args['expected_revision'])
        if row['state'] != 'pending_approval' or row['caller'] == request['actor']:
            raise WorkflowConflict('A pending proposal requires an independent approver')
        conflict = None
        try:
            self._masters(cursor, row['expected_versions'], row['expected_versions'],
                          restoring=row['kind'] == 'restore_merge')
        except WorkflowConflict as error:
            conflict = str(error)
        state = 'conflict' if conflict else 'approved'
        cursor.execute('''UPDATE lm_control.operation SET state=%s,revision=revision+1,
            approved_by=%s,approval_reason=%s,approved_at=%s WHERE operation_id=%s''',
            (state, None if conflict else request['actor'], None if conflict else request['reason'],
             None if conflict else self._now(cursor), row['operation_id']))
        evidence = {'intent_sha256': row['payload_sha256'], 'conflict': conflict}
        decision_id = self._decision(cursor, request, row['task_id'], row['operation_id'],
                                     'approval_conflict' if conflict else 'approve', evidence)
        event_id = None
        if not conflict:
            event_id = str(uuid4())
            event = {'context': asdict(self.context), 'operation_id': row['operation_id'],
                     'operation_revision': row['revision'] + 1, 'intent_sha256': row['payload_sha256'],
                     'approval_decision_id': decision_id}
            cursor.execute('''INSERT INTO lm_control.outbox_event
                (event_id,operation_id,kind,payload,state,created_at)
                VALUES (%s,%s,'workflow.approved.v1',%s,'pending',%s)''',
                (event_id, row['operation_id'], Jsonb(event), self._now(cursor)))
        return {'task': self._task(cursor, row['task_id']), 'operation': self._operation(cursor, row['operation_id']),
                'decision_id': decision_id, 'outbox_event_id': event_id, 'conflict': conflict}

    def get_task(self, task_id):
        master_key(task_id)
        with self._transaction() as cursor:
            return self._task(cursor, task_id)

    def get_operation(self, operation_id):
        master_key(operation_id)
        with self._transaction() as cursor:
            return self._operation(cursor, operation_id)

    def _page(self, limit, after, filters):
        if type(limit) is not int or not 1 <= limit <= MAX_PAGE:
            raise ContractError('Page size must be 1–100')
        binding = digest({'context': asdict(self.context), 'filters': filters})
        if after is None:
            return binding, None
        after = bounded_object(after, maximum=2048)
        if set(after) != {'binding', 'position'} or after['binding'] != binding:
            raise ContractError('Cursor does not belong to this context/query')
        return binding, after['position']

    def inbox(self, *, state='open', limit=50, after=None):
        if state not in {'open', 'claimed', 'resolved', 'canceled'}:
            raise ContractError('A supported task state is required')
        binding, position = self._page(limit, after, {'type': 'inbox', 'state': state})
        params = [self.context.domain_id, self.context.domain_version, state]
        clause = ''
        if position is not None:
            if (not isinstance(position, list) or len(position) != 2 or type(position[0]) is not int
                    or not -1000 <= position[0] <= 1000):
                raise ContractError('Invalid inbox cursor position')
            master_key(position[1])
            clause = ' AND (priority<%s OR (priority=%s AND task_id>%s))'
            params.extend([position[0], position[0], position[1]])
        with self._transaction() as cursor:
            cursor.execute('''SELECT task_id,priority FROM lm_control.steward_task
                WHERE workflow_schema=1 AND domain_id=%s AND domain_version=%s AND state=%s'''
                + clause + ' ORDER BY priority DESC,task_id LIMIT %s', (*params, limit + 1))
            rows = cursor.fetchall()
            items = [self._task(cursor, str(r['task_id'])) for r in rows[:limit]]
        last = items[-1] if items else None
        return {'items': items, 'next': {'binding': binding, 'position': [last['priority'], last['task_id']]}
                if len(rows) > limit else None}

    def history(self, *, task_id=None, operation_id=None, limit=50, after=None):
        if (task_id is None) == (operation_id is None):
            raise ContractError('Choose exactly one task or operation history')
        identity = master_key(task_id if task_id is not None else operation_id)
        column = 'task_id' if task_id is not None else 'operation_id'
        binding, position = self._page(limit, after, {'type': 'history', column: identity})
        if position is not None:
            revision(position)
        with self._transaction() as cursor:
            (self._task if task_id is not None else self._operation)(cursor, identity)
            cursor.execute(f'''SELECT * FROM lm_control.workflow_command
                WHERE domain_id=%s AND domain_version=%s AND {column}=%s AND sequence>%s
                ORDER BY sequence LIMIT %s''',
                (self.context.domain_id, self.context.domain_version, identity, position or 0, limit + 1))
            rows = cursor.fetchall()
        return {'items': [self._receipt(r) for r in rows[:limit]],
                'next': {'binding': binding, 'position': rows[limit - 1]['sequence']} if len(rows) > limit else None}
