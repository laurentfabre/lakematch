"""Real PostgreSQL lease, command and approval invariants on an owned database."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Barrier, Event
import time
from uuid import uuid4

import pytest

if os.environ.get('LAKEMATCH_TEST_POSTGRES') != '1':
    pytest.skip('Opt in with LAKEMATCH_TEST_POSTGRES=1', allow_module_level=True)

import psycopg

from lakematch.mastering.contracts import ContractError, DomainContract
from lakematch.mastering.identity_contract import IdentityContext, SourceRef
from lakematch.mastering.identity_registry import PostgresIdentityRegistry
from lakematch.mastering.registry import PostgresRegistry, apply_migrations
from lakematch.mastering.workflow import PostgresWorkflow
from lakematch.mastering.workflow_contract import WorkflowConflict, WorkflowContext, WorkflowUnavailable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from local_postgres import LocalPostgres


def options(key, actor='steward'):
    return {'actor': actor, 'reason': 'Synthetic stewardship fixture', 'key': key}


@pytest.fixture(scope='module')
def postgres():
    with LocalPostgres() as server:
        yield server
    assert server.cleanup == 'owned Postgres stopped'


@pytest.fixture
def fixture(postgres):
    with postgres.connect() as connection:
        connection.execute('DROP SCHEMA IF EXISTS lm_control CASCADE')
        apply_migrations(connection, ROOT / 'app/migrations/mastering')
    domain = DomainContract.from_dict(json.loads((ROOT / 'examples/mastering/company_pilot/domain.json').read_text()))
    registry = PostgresRegistry(postgres.connect)
    registry.submit_domain(domain, actor='engineer', expected_latest=0)
    registry.transition('domain', 'company', 'company', 1, state='approved', expected_revision=1,
                        actor='approver', reason='Approved synthetic contract')
    identities = PostgresIdentityRegistry(postgres.connect, IdentityContext('company', 1, domain.sha256))
    ids = [identities.allocate([SourceRef('erp_vendor', str(n))], **options('identity-' + str(n)))
           ['result']['master_id'] for n in range(2)]
    return PostgresWorkflow(postgres.connect, WorkflowContext('company', 1, domain.sha256)), identities, ids


def task(fixture, key='create', *, kind='merge', priority=0):
    store, _, ids = fixture
    return store.create_task(kind, ids if kind in {'merge', 'restore_merge'} else ids[:1],
                             priority=priority, evidence={'source': 'synthetic'}, **options(key))


def claim(store, row, key='claim', actor='steward', seconds=60):
    return store.claim(row['task_id'], row['revision'], seconds=seconds, **options(key, actor))


def proposal(fixture, *, kind='merge'):
    store, _, ids = fixture
    created = task(fixture, kind=kind)
    leased = claim(store, created['result']['task'])['result']['task']
    payloads = {'merge': {'survivor_id': ids[0]}, 'override': {'field': 'city', 'value': 'Paris'},
                'split_new': {'members': [{'source_id': 'erp_vendor', 'source_key': '0'}]}}
    return store.propose(leased['task_id'], leased['revision'], leased['lease_token'],
                         {i: 1 for i in leased['entity_ids']}, payloads[kind], evidence={'reviewed': True},
                         **options('propose'))


def counts(postgres):
    with postgres.connect() as connection:
        return {table: connection.execute('SELECT count(*) FROM lm_control.' + table).fetchone()[0]
                for table in ('steward_task', 'operation', 'steward_decision', 'outbox_event', 'workflow_command')}


def test_exact_replay_changed_key_request_and_retired_domain(fixture, postgres):
    store, _, _ = fixture
    created = task(fixture)
    row = created['result']['task']
    leased = claim(store, row)
    assert task(fixture) == created
    assert claim(store, row) == leased
    with pytest.raises(WorkflowConflict, match='different command'):
        task(fixture, priority=3)
    with pytest.raises(WorkflowConflict, match='different command'):
        store.claim(row['task_id'], 1, seconds=60, actor='steward', key='claim', reason='Changed reason')
    other = PostgresWorkflow(postgres.connect, replace(store.context, domain_sha256='f' * 64))
    with pytest.raises(WorkflowConflict, match='different command'):
        claim(other, row)
    PostgresRegistry(postgres.connect).transition('domain', 'company', 'company', 1, state='retired',
        expected_revision=2, actor='approver', reason='Retired fixture')
    assert claim(store, row) == leased
    with pytest.raises(WorkflowUnavailable):
        task(fixture, 'new')


@pytest.mark.parametrize('same_key', [True, False])
def test_concurrent_claims(fixture, same_key):
    store, _, _ = fixture
    row = task(fixture)['result']['task']
    barrier = Barrier(4)
    def submit(n):
        barrier.wait(timeout=5)
        try:
            return claim(store, row, 'same' if same_key else str(n), 'steward' if same_key else str(n))
        except WorkflowConflict:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(submit, range(4)))
    successes = [r for r in results if r]
    assert len(successes) == (4 if same_key else 1)
    assert all(r == successes[0] for r in successes)
    assert store.get_task(row['task_id'])['revision'] == 2
    assert len(store.history(task_id=row['task_id'])['items']) == 2


def test_concurrent_same_key_creates_one_task(fixture, postgres):
    barrier = Barrier(4)
    def submit(n):
        barrier.wait(timeout=5)
        return task(fixture)
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(submit, range(4)))
    assert all(r == receipts[0] for r in receipts)
    assert counts(postgres)['steward_task'] == 1


def test_proposal_retry_returns_original_receipt_after_approval(fixture):
    store, _, ids = fixture
    row = claim(store, task(fixture)['result']['task'])['result']['task']
    def propose():
        return store.propose(row['task_id'], 2, row['lease_token'], {i: 1 for i in ids},
                             {'survivor_id': ids[0]}, evidence={}, **options('propose'))
    original = propose()
    store.approve(original['result']['operation']['operation_id'], 1, **options('approve', 'approver'))
    assert propose() == original
    assert original['result']['operation']['state'] == 'pending_approval'
    with pytest.raises(WorkflowConflict, match='different command'):
        store.propose(row['task_id'], 2, row['lease_token'], {i: 1 for i in ids},
                      {'survivor_id': ids[1]}, evidence={}, **options('propose'))


def test_lease_expiring_while_entity_lock_waits_cannot_propose(fixture, postgres):
    store, _, ids = fixture
    row = claim(store, task(fixture)['result']['task'], seconds=1)['result']['task']
    entered = Event()
    class ObservedWorkflow(PostgresWorkflow):
        def _masters(self, *args, **kwargs):
            entered.set()
            return super()._masters(*args, **kwargs)
    waiter = ObservedWorkflow(postgres.connect, store.context)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with postgres.connect() as connection, connection.transaction():
            connection.execute('SELECT 1 FROM lm_control.master_identity WHERE master_id=%s FOR UPDATE', (ids[0],))
            future = pool.submit(waiter.propose, row['task_id'], 2, row['lease_token'], {i: 1 for i in ids},
                                 {'survivor_id': ids[0]}, evidence={}, **options('slow-propose'))
            assert entered.wait(timeout=2)
            time.sleep(1.1)
        with pytest.raises(WorkflowConflict, match='live owned lease'):
            future.result(timeout=5)
    assert store.get_task(row['task_id']) == row
    assert counts(postgres)['operation'] == 0


def test_renewal_rotates_token_release_and_replay(fixture):
    store, _, _ = fixture
    original = task(fixture)['result']['task']
    leased = claim(store, original)['result']['task']
    renewed = store.renew(leased['task_id'], 2, leased['lease_token'], seconds=90, **options('renew'))
    current = renewed['result']['task']
    assert current['lease_token'] != leased['lease_token']
    assert store.renew(leased['task_id'], 2, leased['lease_token'], seconds=90, **options('renew')) == renewed
    for token, actor, rev in [(leased['lease_token'], 'steward', 3), (current['lease_token'], 'other', 3),
                              (current['lease_token'], 'steward', 2)]:
        with pytest.raises(WorkflowConflict):
            store.release(leased['task_id'], rev, token, **options('invalid', actor))
    released = store.release(leased['task_id'], 3, current['lease_token'], **options('release'))
    assert released['result']['task']['state'] == 'open'
    assert released['result']['task']['lease_token'] is None
    assert claim(store, original)['result']['task'] == leased  # Historical receipt, not a new lease.


def test_expiry_reclaim_and_fencing(fixture):
    store, _, ids = fixture
    leased = claim(store, task(fixture)['result']['task'], seconds=1)['result']['task']
    time.sleep(1.05)
    with pytest.raises(WorkflowConflict, match='live owned lease'):
        store.renew(leased['task_id'], 2, leased['lease_token'], seconds=60, **options('expired-renew'))
    with pytest.raises(WorkflowConflict):
        store.propose(leased['task_id'], 2, leased['lease_token'], {i: 1 for i in ids},
                      {'survivor_id': ids[0]}, evidence={}, **options('expired-propose'))
    reclaimed = claim(store, leased, 'reclaim', 'other')['result']['task']
    assert reclaimed['lease_token'] != leased['lease_token']
    with pytest.raises(WorkflowConflict):
        store.release(leased['task_id'], 3, leased['lease_token'], **options('fenced'))


def test_clock_is_read_after_waiting_for_task_lock(fixture, postgres):
    store, _, _ = fixture
    leased = claim(store, task(fixture)['result']['task'], seconds=1)['result']['task']
    started = Event()
    @contextmanager
    def observed_connection():
        with postgres.connect() as connection:
            started.set()
            yield connection
    waiter = PostgresWorkflow(observed_connection, store.context)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with postgres.connect() as connection, connection.transaction():
            connection.execute('SELECT 1 FROM lm_control.steward_task WHERE task_id=%s FOR UPDATE', (leased['task_id'],))
            future = pool.submit(claim, waiter, leased, 'reclaim', 'other')
            assert started.wait(timeout=2)
            time.sleep(1.1)
        assert future.result(timeout=5)['result']['task']['assignee'] == 'other'


@pytest.mark.parametrize('claimed', [False, True])
def test_cancel_terminal_and_immutable_receipt(fixture, claimed):
    store, _, _ = fixture
    row = task(fixture)['result']['task']
    if claimed:
        row = claim(store, row)['result']['task']
    canceled = store.cancel(row['task_id'], row['revision'], lease_token=row['lease_token'], **options('cancel'))
    assert canceled['result']['task']['state'] == 'canceled'
    assert store.cancel(row['task_id'], row['revision'], lease_token=row['lease_token'], **options('cancel')) == canceled
    with pytest.raises(WorkflowConflict):
        claim(store, canceled['result']['task'], 'claim-after-cancel')


@pytest.mark.parametrize('kind', ['merge', 'override', 'split_new'])
def test_proposal_approval_outbox_no_business_mutation(fixture, postgres, kind):
    store, identities, ids = fixture
    before = [identities.get(i) for i in ids]
    proposed = proposal(fixture, kind=kind)
    op = proposed['result']['operation']
    assert op['state'] == 'pending_approval'
    assert proposed['result']['task']['state'] == 'resolved'
    with pytest.raises(WorkflowConflict, match='independent'):
        store.approve(op['operation_id'], 1, **options('self-approval'))
    approved = store.approve(op['operation_id'], 1, **options('approve', 'approver'))
    assert approved['result']['operation']['state'] == 'approved'
    assert approved['result']['outbox_event_id']
    assert store.approve(op['operation_id'], 1, **options('approve', 'approver')) == approved
    assert counts(postgres) == dict(steward_task=1, operation=1, steward_decision=2, outbox_event=1, workflow_command=4)
    assert [identities.get(i) for i in ids] == before


def test_restore_intent_allows_merged_participant(fixture):
    store, identities, ids = fixture
    merged = identities.merge(ids[0], {i: 1 for i in ids}, **options('merge-identity'))
    row = claim(store, task(fixture, kind='restore_merge')['result']['task'])['result']['task']
    proposed = store.propose(row['task_id'], row['revision'], row['lease_token'], {i: 2 for i in ids},
        {'event_id': merged['event_id']}, evidence={}, **options('restore-intent'))
    assert proposed['result']['operation']['kind'] == 'restore_merge'


@pytest.mark.parametrize('same_key', [True, False])
def test_concurrent_approval(fixture, postgres, same_key):
    store, _, _ = fixture
    op = proposal(fixture)['result']['operation']
    barrier = Barrier(4)
    def submit(n):
        barrier.wait(timeout=5)
        try:
            return store.approve(op['operation_id'], 1, **options('same' if same_key else str(n), 'approver'))
        except WorkflowConflict:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(submit, range(4)))
    success = [r for r in receipts if r]
    assert len(success) == (4 if same_key else 1)
    assert all(r == success[0] for r in success)
    assert counts(postgres)['outbox_event'] == 1
    assert counts(postgres)['steward_decision'] == 2


def test_entity_revision_conflict_is_durable_without_outbox(fixture, postgres):
    store, identities, ids = fixture
    op = proposal(fixture)['result']['operation']
    identities.attach(ids[0], 1, members=[SourceRef('crm_account', 'late')], **options('change'))
    result = store.approve(op['operation_id'], 1, **options('approve', 'approver'))
    assert result['result']['operation']['state'] == 'conflict'
    assert result['result']['operation']['approved_by'] is None
    assert result['result']['outbox_event_id'] is None
    assert result['result']['conflict'] == 'Referenced master revision changed'
    assert store.approve(op['operation_id'], 1, **options('approve', 'approver')) == result
    assert counts(postgres)['outbox_event'] == 0
    assert counts(postgres)['steward_decision'] == 2


@pytest.mark.parametrize('field,value', [('nonexistent', 'x'), ('record_kind', 'company'), ('legal_name', None), ('city', 5)])
def test_override_domain_validation(fixture, postgres, field, value):
    store, _, ids = fixture
    row = claim(store, task(fixture, kind='override')['result']['task'])['result']['task']
    before = counts(postgres)
    with pytest.raises(ContractError):
        store.propose(row['task_id'], 2, row['lease_token'], {ids[0]: 1}, {'field': field, 'value': value},
                      evidence={}, **options('invalid'))
    assert counts(postgres) == before
    assert store.get_task(row['task_id']) == row


def test_proposal_entity_and_revision_validation(fixture, postgres):
    store, _, ids = fixture
    row = claim(store, task(fixture)['result']['task'])['result']['task']
    before = counts(postgres)
    for versions in [{ids[0]: 2, ids[1]: 1}, {ids[0]: 1, str(uuid4()): 1}]:
        with pytest.raises(WorkflowConflict):
            store.propose(row['task_id'], 2, row['lease_token'], versions, {'survivor_id': ids[0]},
                          evidence={}, **options('invalid'))
    assert counts(postgres) == before


@pytest.mark.parametrize('failure', ['receipt', 'outbox'])
def test_approval_failure_rolls_back_whole_transaction(fixture, postgres, failure, monkeypatch):
    store, _, _ = fixture
    op = proposal(fixture)['result']['operation']
    before = counts(postgres)
    if failure == 'receipt':
        def fail(*args):
            raise RuntimeError('Injected receipt failure')
        monkeypatch.setattr(store, '_save_command', fail)
    else:
        with postgres.connect() as connection:
            connection.execute('''CREATE TRIGGER reject_fixture_outbox BEFORE INSERT ON lm_control.outbox_event
                FOR EACH ROW EXECUTE FUNCTION lm_control.immutable_decision()''')
    with pytest.raises((RuntimeError, psycopg.errors.RaiseException)):
        store.approve(op['operation_id'], 1, **options('approve', 'approver'))
    assert counts(postgres) == before
    assert store.get_operation(op['operation_id']) == op


def test_proposal_receipt_failure_rolls_back(fixture, postgres, monkeypatch):
    store, _, ids = fixture
    row = claim(store, task(fixture)['result']['task'])['result']['task']
    before = counts(postgres)
    def fail(*args):
        raise RuntimeError('Injected receipt failure')
    monkeypatch.setattr(store, '_save_command', fail)
    with pytest.raises(RuntimeError):
        store.propose(row['task_id'], 2, row['lease_token'], {i: 1 for i in ids},
                      {'survivor_id': ids[0]}, evidence={}, **options('propose'))
    assert counts(postgres) == before
    assert store.get_task(row['task_id']) == row


def test_lost_ack_and_actual_restart(fixture, postgres):
    store, _, _ = fixture
    op = proposal(fixture)['result']['operation']
    @contextmanager
    def lose_response():
        with postgres.connect() as connection:
            yield connection
        raise TimeoutError('Acknowledgement lost after commit')
    uncertain = PostgresWorkflow(lose_response, store.context)
    with pytest.raises(TimeoutError):
        uncertain.approve(op['operation_id'], 1, **options('approve', 'approver'))
    receipt = store.approve(op['operation_id'], 1, **options('approve', 'approver'))
    before = store.history(task_id=op['task_id'])
    postgres.restart()
    assert store.history(task_id=op['task_id']) == before
    assert store.approve(op['operation_id'], 1, **options('approve', 'approver')) == receipt
    assert store.get_operation(op['operation_id']) == receipt['result']['operation']


def test_child_process_death_before_commit_rolls_back(fixture, postgres):
    store, _, _ = fixture
    row = task(fixture)['result']['task']
    child_code = '''
import json, os, sys, psycopg
from lakematch.mastering.workflow import PostgresWorkflow
from lakematch.mastering.workflow_contract import WorkflowContext
args=json.loads(sys.argv[1])
def connect():
    return psycopg.connect(host=args['socket'],port=55437,user='lm_registry_test',dbname='postgres',autocommit=True)
class DyingWorkflow(PostgresWorkflow):
    def _save_command(self,*a):
        super()._save_command(*a)
        os._exit(29)
store=DyingWorkflow(connect,WorkflowContext(**args['context']))
store.claim(args['task'],1,seconds=60,actor='steward',reason='Synthetic stewardship fixture',key='claim')
'''
    from dataclasses import asdict
    result = subprocess.run([sys.executable, '-c', child_code, json.dumps({
        'socket': str(postgres.socket), 'context': asdict(store.context), 'task': row['task_id']})],
        capture_output=True, text=True, timeout=15)
    assert result.returncode == 29, result.stderr
    assert store.get_task(row['task_id']) == row
    assert counts(postgres)['workflow_command'] == 1
    assert claim(store, row)['result']['task']['revision'] == 2


@pytest.mark.parametrize('sql', [
    'DELETE FROM lm_control.workflow_command',
    "UPDATE lm_control.workflow_command SET action='cancel'",
    'DELETE FROM lm_control.steward_decision',
    "UPDATE lm_control.steward_decision SET reason='rewrite'",
    'DELETE FROM lm_control.steward_task',
    "UPDATE lm_control.steward_task SET kind='override',revision=revision+1",
    "UPDATE lm_control.steward_task SET state='open',revision=revision+1",
    'UPDATE lm_control.steward_task SET workflow_schema=0',
    'DELETE FROM lm_control.operation',
    "UPDATE lm_control.operation SET payload='{}',revision=revision+1",
    "UPDATE lm_control.operation SET state='published',revision=revision+1",
])
def test_sql_immutability_and_transition_guards(fixture, postgres, sql):
    proposal(fixture)
    with postgres.connect() as connection, pytest.raises(psycopg.Error):
        connection.execute(sql)


def test_approved_metadata_cannot_be_rewritten(fixture, postgres):
    store, _, _ = fixture
    op = proposal(fixture)['result']['operation']
    store.approve(op['operation_id'], 1, **options('approve', 'approver'))
    with postgres.connect() as connection, pytest.raises(psycopg.errors.RaiseException):
        connection.execute("UPDATE lm_control.operation SET approved_by='someone',revision=revision+1,state='applying'")


def test_context_isolation_and_legacy_refusal(fixture, postgres):
    store, _, ids = fixture
    created = task(fixture)['result']['task']
    for context in [replace(store.context, domain_id='another'), replace(store.context, domain_version=2),
                    replace(store.context, domain_sha256='f' * 64)]:
        other = PostgresWorkflow(postgres.connect, context)
        with pytest.raises(WorkflowUnavailable):
            other.get_task(created['task_id'])
    legacy = str(uuid4())
    with postgres.connect() as connection:
        connection.execute("INSERT INTO lm_control.steward_task(domain_id,task_id,kind,entity_ids,state) "
                           "VALUES ('company',%s,'review','[]','open')", (legacy,))
    with pytest.raises(WorkflowUnavailable):
        store.get_task(legacy)
    assert len(store.inbox()['items']) == 1


def test_bounded_inbox_history_and_cursor_binding(fixture):
    store, _, _ = fixture
    tasks = [task(fixture, str(n), priority=n % 3)['result']['task'] for n in range(7)]
    expected = sorted(tasks, key=lambda r: (-r['priority'], r['task_id']))
    first = store.inbox(limit=2)
    rows, page = first['items'], first
    while page['next']:
        page = store.inbox(limit=2, after=page['next'])
        rows += page['items']
    assert rows == expected
    with pytest.raises(ContractError):
        store.inbox(state='claimed', after=first['next'])
    for limit in [0, 101, True]:
        with pytest.raises(ContractError):
            store.inbox(limit=limit)
    row = tasks[0]
    claim(store, row)
    history = store.history(task_id=row['task_id'], limit=1)
    assert history['items'][0]['action'] == 'create_task'
    assert store.history(task_id=row['task_id'], after=history['next'])['items'][0]['action'] == 'claim'
    with pytest.raises(ContractError):
        store.history(task_id=tasks[1]['task_id'], after=history['next'])


def test_receipts_are_utc_and_hash_corruption_is_refused(fixture, postgres):
    store, _, _ = fixture
    @contextmanager
    def timezone_connection():
        with postgres.connect() as connection:
            connection.execute("SET TIME ZONE 'Pacific/Auckland'")
            yield connection
    zoned = PostgresWorkflow(timezone_connection, store.context)
    created = task(fixture)
    leased = claim(zoned, created['result']['task'])
    assert leased['recorded_at'].endswith('+00:00')
    assert leased['result']['task']['lease_until'].endswith('+00:00')
    assert claim(store, created['result']['task']) == leased
    # A database owner can disable triggers. Digest validation must still detect damage.
    with postgres.connect() as connection, connection.transaction():
        connection.execute('ALTER TABLE lm_control.workflow_command DISABLE TRIGGER immutable_workflow_command')
        connection.execute("UPDATE lm_control.workflow_command SET receipt_sha256=repeat('0',64)")
        connection.execute('ALTER TABLE lm_control.workflow_command ENABLE TRIGGER immutable_workflow_command')
    with pytest.raises(WorkflowUnavailable, match='digest'):
        claim(store, created['result']['task'])


def test_upgrade_preserves_populated_version_zero_rows(fixture, postgres, tmp_path):
    store, _, _ = fixture
    for path in sorted((ROOT / 'app/migrations/mastering').glob('000[1-4]*.sql')):
        shutil.copy2(path, tmp_path / path.name)
    task_id, operation_id = str(uuid4()), str(uuid4())
    with postgres.connect() as connection:
        connection.execute('DROP SCHEMA lm_control CASCADE')
        apply_migrations(connection, tmp_path)
        connection.execute("INSERT INTO lm_control.domain(domain_id) VALUES ('company')")
        connection.execute("INSERT INTO lm_control.steward_task(domain_id,task_id,kind,entity_ids,state) "
                           "VALUES ('company',%s,'legacy_review','[]','open')", (task_id,))
        connection.execute("INSERT INTO lm_control.operation(operation_id,domain_id,caller,idempotency_key,"
                           "payload_sha256,expected_versions,payload,state) "
                           "VALUES (%s,'company','old','old',repeat('a',64),'{}','{}','draft')", (operation_id,))
        before = connection.execute('SELECT task_id,state,revision FROM lm_control.steward_task').fetchall()
        apply_migrations(connection, ROOT / 'app/migrations/mastering')
        assert connection.execute('SELECT task_id,state,revision FROM lm_control.steward_task').fetchall() == before
        assert connection.execute('SELECT workflow_schema FROM lm_control.operation').fetchone()[0] == 0
        connection.execute("UPDATE lm_control.steward_task SET state='canceled'")
    with pytest.raises(WorkflowUnavailable):
        store.get_task(task_id)
    with pytest.raises(WorkflowUnavailable):
        store.get_operation(operation_id)
