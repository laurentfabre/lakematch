"""Current-grant workflow boundary over the trusted transactional worker."""
from dataclasses import asdict

from psycopg.types.json import Jsonb

from .access_contract import POLICY, AccessDenied, HiddenObject
from .access_registry import read_access
from .contracts import ContractError
from .identity_contract import master_key, text_key
from .registry import PostgresRegistry
from .workflow import PostgresWorkflow
from .workflow_contract import WorkflowUnavailable, revision

COMMAND_ACTIONS = {'create_task': 'decision.propose', 'claim': 'task.claim', 'renew': 'task.claim',
                   'release': 'task.claim', 'cancel': 'task.claim', 'propose': 'decision.propose',
                   'approve': 'decision.approve'}


class AuthorizedWorkflow(PostgresWorkflow):
    def __init__(self, connect, context, principal):
        super().__init__(connect, context)
        text_key(principal, 'Authenticated principal')
        self.principal = principal

    def _policy(self, cursor, action):
        access = read_access(cursor, self.principal, self.context.domain_id)
        access.require_action(action)
        domain, _ = PostgresRegistry(self._connect)._domain(cursor, self.context.domain_id,
                                                           self.context.domain_version)
        if domain.sha256 != self.context.domain_sha256:
            raise WorkflowUnavailable('Configured domain digest differs')
        fields = frozenset(f.name for f in domain.fields)
        # Workflow evidence/reasons are free-form and cannot be safely projected.
        # This v1 boundary requires all domain fields before returning raw rows.
        access.readable_objects(fields)
        return access, fields

    @staticmethod
    def _require_objects(access, fields, ids, action, *, proposed_by=None):
        for identity in ids:
            if not access.permits('task.read', fields, identity):
                raise HiddenObject('Object is unavailable')
            if not access.permits(action, fields, identity, proposed_by=proposed_by):
                raise AccessDenied('Action is not permitted on every participating object')

    def _authorize_command(self, cursor, request):
        if request['actor'] != self.principal:
            raise AccessDenied('Actor must be the authenticated principal')
        action = COMMAND_ACTIONS[request['action']]
        access, fields = self._policy(cursor, action)
        args, proposer = request['arguments'], None
        if request['action'] == 'create_task':
            ids = args['entity_ids']
        elif request['action'] == 'approve':
            row = self._operation(cursor, args['operation_id'])
            ids, proposer = list(row['expected_versions']), row['caller']
        else:
            ids = self._task(cursor, args['task_id'])['entity_ids']
        self._require_objects(access, fields, ids, action, proposed_by=proposer)

    def _command_metadata(self, cursor, request):
        # The first authorization check already holds this subject's share lock.
        # Bind the immutable receipt to the exact policy that admitted it.
        access = read_access(cursor, self.principal, self.context.domain_id)
        return {'authorization': {'policy_version': POLICY, 'principal': self.principal,
                                  'revision': access.revision, 'definition_sha256': access.definition_sha256}}

    def get_task(self, task_id):
        master_key(task_id)
        with self._transaction(write=True) as cursor:
            access, fields = self._policy(cursor, 'task.read')
            row = self._task(cursor, task_id)
            self._require_objects(access, fields, row['entity_ids'], 'task.read')
            return row

    def get_operation(self, operation_id):
        master_key(operation_id)
        with self._transaction(write=True) as cursor:
            access, fields = self._policy(cursor, 'task.read')
            row = self._operation(cursor, operation_id)
            self._require_objects(access, fields, row['expected_versions'], 'task.read')
            return row

    def _access_page(self, access, limit, after, filters):
        # Revocation or any grant replacement invalidates earlier list cursors.
        return self._page(limit, after, {**filters, 'principal': self.principal,
            'access_revision': access.revision, 'access_sha256': access.definition_sha256})

    def inbox(self, *, state='open', limit=50, after=None):
        if state not in {'open', 'claimed', 'resolved', 'canceled'}:
            raise ContractError('A supported task state is required')
        with self._transaction(write=True) as cursor:
            access, fields = self._policy(cursor, 'task.read')
            binding, position = self._access_page(access, limit, after, {'type': 'inbox', 'state': state})
            allowed = access.readable_objects(fields)
            params = [self.context.domain_id, self.context.domain_version, state]
            clause = ''
            if allowed is not None:
                # Filter BEFORE limiting/pagination. Never expose hidden IDs,
                # totals, evidence or cursors from rows the caller cannot read.
                clause += ' AND entity_ids <@ %s::jsonb'
                params.append(Jsonb(allowed))
            if position is not None:
                if (not isinstance(position, list) or len(position) != 2 or type(position[0]) is not int
                        or not -1000 <= position[0] <= 1000):
                    raise ContractError('Invalid inbox cursor position')
                master_key(position[1])
                clause += ' AND (priority<%s OR (priority=%s AND task_id>%s))'
                params.extend([position[0], position[0], position[1]])
            cursor.execute('''SELECT task_id,priority FROM lm_control.steward_task
                WHERE workflow_schema=1 AND domain_id=%s AND domain_version=%s AND state=%s'''
                + clause + ' ORDER BY priority DESC,task_id LIMIT %s', (*params, limit+1))
            rows = cursor.fetchall()
            items = [self._task(cursor, str(r['task_id'])) for r in rows[:limit]]
            for item in items:
                self._require_objects(access, fields, item['entity_ids'], 'task.read')
            last = items[-1] if items else None
            return {'items': items, 'next': {'binding': binding, 'position': [last['priority'], last['task_id']]}
                    if len(rows) > limit else None}

    def history(self, *, task_id=None, operation_id=None, limit=50, after=None):
        if (task_id is None) == (operation_id is None):
            raise ContractError('Choose exactly one task or operation history')
        identity = master_key(task_id if task_id is not None else operation_id)
        column = 'task_id' if task_id is not None else 'operation_id'
        with self._transaction(write=True) as cursor:
            access, fields = self._policy(cursor, 'task.read')
            row = (self._task if task_id is not None else self._operation)(cursor, identity)
            ids = row['entity_ids'] if task_id is not None else row['expected_versions']
            self._require_objects(access, fields, ids, 'task.read')
            binding, position = self._access_page(access, limit, after, {'type': 'history', column: identity})
            if position is not None:
                revision(position)
            cursor.execute(f'''SELECT * FROM lm_control.workflow_command
                WHERE domain_id=%s AND domain_version=%s AND {column}=%s AND sequence>%s
                ORDER BY sequence LIMIT %s''',
                (self.context.domain_id, self.context.domain_version, identity, position or 0, limit+1))
            rows = cursor.fetchall()
            items = []
            for saved in rows[:limit]:
                receipt = self._receipt(saved)
                # Defensive check of every historical projection before replay.
                result = receipt['result']
                if receipt['context'] != asdict(self.context):
                    raise WorkflowUnavailable('History context differs')
                self._require_objects(access, fields, result['task']['entity_ids'], 'task.read')
                if result.get('operation'):
                    self._require_objects(access, fields, result['operation']['expected_versions'], 'task.read')
                items.append(receipt)
            return {'items': items, 'next': {'binding': binding, 'position': rows[limit-1]['sequence']}
                    if len(rows) > limit else None}
