"""Authorization and revocation over actual workflow transactions."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
import os
from pathlib import Path
import shutil
from threading import Event
from uuid import uuid4

import pytest

if os.environ.get('LAKEMATCH_TEST_POSTGRES') != '1':
    pytest.skip('Opt in with LAKEMATCH_TEST_POSTGRES=1', allow_module_level=True)

import psycopg

from lakematch.mastering.access_contract import AccessDenied, AccessUnavailable, HiddenObject
from lakematch.mastering.access_registry import PostgresAccessRegistry, grant_workflow_role
from lakematch.mastering.authorized_workflow import AuthorizedWorkflow
from lakematch.mastering.contracts import ContractError
from lakematch.mastering.workflow_contract import WorkflowConflict
from lakematch.mastering.workflow_api import WorkflowAPI
from lakematch.mastering.registry import apply_migrations

from test_workflow import postgres, fixture, options, task, proposal, counts


def grants(postgres, principal, role='steward', *, fields=None, objects=None, revision=0, rows=None):
    rows = rows if rows is not None else [{'role': role, 'fields': fields, 'object_ids': objects}]
    return PostgresAccessRegistry(postgres.connect).replace(principal, 'company', rows,
        expected_revision=revision, actor='access_operator', reason='Synthetic access fixture', key=str(uuid4()))


def service(fixture, postgres, principal='alice'):
    return AuthorizedWorkflow(postgres.connect, fixture[0].context, principal)


def test_access_registry_replay_stale_change_and_append_only(fixture, postgres):
    registry = PostgresAccessRegistry(postgres.connect)
    kwargs = dict(expected_revision=0, actor='operator', reason='fixture', key='one')
    rows = [{'role': 'viewer', 'fields': None, 'object_ids': None}]
    first = registry.replace('alice', 'company', rows, **kwargs)
    assert registry.replace('alice', 'company', rows, **kwargs) == first
    with pytest.raises(WorkflowConflict):
        registry.replace('alice', 'company', [], **kwargs)
    with pytest.raises(WorkflowConflict):
        registry.replace('alice', 'company', [], **{**kwargs, 'key': 'new'})
    for query in ('DELETE FROM lm_control.access_event', "UPDATE lm_control.access_event SET actor='rewrite'",
                  'DELETE FROM lm_control.access_policy', 'UPDATE lm_control.access_policy SET revision=revision+2'):
        with postgres.connect() as connection, pytest.raises(psycopg.Error):
            connection.execute(query)


@pytest.mark.parametrize('role,allowed', [('viewer', False), ('steward', True), ('approver', False),
                                       ('engineer', False), ('administrator', True)])
def test_claim_role_matrix(fixture, postgres, role, allowed):
    raw = task(fixture)['result']['task']
    grants(postgres, 'alice', role)
    store = service(fixture, postgres)
    assert store.get_task(raw['task_id']) == raw
    before = counts(postgres)
    if allowed:
        assert store.claim(raw['task_id'], 1, seconds=60, **options('claim', 'alice'))['actor'] == 'alice'
    else:
        with pytest.raises(AccessDenied):
            store.claim(raw['task_id'], 1, seconds=60, **options('claim', 'alice'))
        assert counts(postgres) == before


@pytest.mark.parametrize('role,allowed', [('viewer', False), ('steward', False), ('approver', True),
                                       ('engineer', False), ('administrator', True)])
def test_approval_role_matrix_and_self_approval(fixture, postgres, role, allowed):
    op = proposal(fixture)['result']['operation']
    grants(postgres, 'alice', role)
    store = service(fixture, postgres)
    if allowed:
        assert store.approve(op['operation_id'], 1, **options('approve', 'alice'))['result']['operation']['state'] == 'approved'
    else:
        with pytest.raises(AccessDenied):
            store.approve(op['operation_id'], 1, **options('approve', 'alice'))
    grants(postgres, 'steward', 'administrator')
    with pytest.raises(AccessDenied):
        service(fixture, postgres, 'steward').approve(op['operation_id'], 1, **options('self'))


def test_no_grants_no_actor_override_no_cross_domain(fixture, postgres):
    row = task(fixture)['result']['task']
    store = service(fixture, postgres)
    with pytest.raises(AccessDenied):
        store.get_task(row['task_id'])
    grants(postgres, 'alice')
    with pytest.raises(AccessDenied):
        store.claim(row['task_id'], 1, seconds=60, **options('actor-forgery', 'other'))
    other = AuthorizedWorkflow(postgres.connect, replace(store.context, domain_id='other'), 'alice')
    with pytest.raises(AccessDenied):
        other.get_task(row['task_id'])


@pytest.mark.parametrize('action', ['renew', 'release', 'cancel', 'propose'])
def test_downgrade_revokes_every_lease_mutation(fixture, postgres, action):
    row = task(fixture)['result']['task']
    grants(postgres, 'alice')
    store = service(fixture, postgres)
    lease = store.claim(row['task_id'], 1, seconds=60, **options('claim', 'alice'))['result']['task']
    grants(postgres, 'alice', 'viewer', revision=1)
    arguments = dict(task_id=row['task_id'], expected_revision=2, lease_token=lease['lease_token'], **options('changed', 'alice'))
    if action == 'renew':
        arguments['seconds'] = 60
    if action == 'propose':
        arguments.update(versions={i: 1 for i in fixture[2]}, payload={'survivor_id': fixture[2][0]}, evidence={})
    before = counts(postgres)
    with pytest.raises(AccessDenied):
        getattr(store, action)(**arguments)
    assert counts(postgres) == before


def test_all_participating_objects_required_and_filtered_before_pagination(fixture, postgres):
    raw, _, ids = fixture
    hidden = task(fixture, priority=1000)['result']['task']
    visible = [raw.create_task('override', ids[:1], evidence={'visible': True}, **options(str(n)))['result']['task'] for n in range(3)]
    grants(postgres, 'alice', objects=ids[:1])
    store = service(fixture, postgres)
    first = store.inbox(limit=2)
    second = store.inbox(limit=2, after=first['next'])
    assert {r['task_id'] for r in first['items'] + second['items']} == {r['task_id'] for r in visible}
    assert hidden['task_id'] not in str(first) and hidden['task_id'] not in str(second)
    assert second['next'] is None
    for read in (lambda: store.get_task(hidden['task_id']), lambda: store.history(task_id=hidden['task_id'])):
        with pytest.raises(HiddenObject):
            read()
    with pytest.raises(HiddenObject):
        store.claim(hidden['task_id'], 1, seconds=60, **options('partial', 'alice'))


def test_field_scope_does_not_expose_unstructured_evidence(fixture, postgres):
    row = task(fixture)['result']['task']
    grants(postgres, 'alice', fields=['city'])
    store = service(fixture, postgres)
    for read in (lambda: store.get_task(row['task_id']), lambda: store.inbox(), lambda: store.history(task_id=row['task_id'])):
        with pytest.raises(AccessDenied):
            read()
    with pytest.raises(AccessDenied):
        store.claim(row['task_id'], 1, seconds=60, **options('partial-fields', 'alice'))


def test_exact_retry_history_and_cursor_obey_revocation(fixture, postgres):
    raw, _, ids = fixture
    rows = [task(fixture, str(n))['result']['task'] for n in range(3)]
    grants(postgres, 'alice')
    store = service(fixture, postgres)
    cursor = store.inbox(limit=1)['next']
    receipt = store.claim(rows[0]['task_id'], 1, seconds=60, **options('claim', 'alice'))
    assert receipt['authorization']['revision'] == 1
    assert receipt['authorization']['principal'] == 'alice'
    grants(postgres, 'alice', revision=1, rows=[])
    for operation in (lambda: store.get_task(rows[0]['task_id']), lambda: store.inbox(),
                      lambda: store.history(task_id=rows[0]['task_id']),
                      lambda: store.claim(rows[0]['task_id'], 1, seconds=60, **options('claim', 'alice'))):
        with pytest.raises(AccessDenied):
            operation()
    grants(postgres, 'alice', revision=2)
    assert store.claim(rows[0]['task_id'], 1, seconds=60, **options('claim', 'alice')) == receipt
    with pytest.raises(ContractError, match='Cursor'):
        store.inbox(limit=1, after=cursor)
    grants(postgres, 'bob')
    with pytest.raises(ContractError, match='Cursor'):
        service(fixture, postgres, 'bob').inbox(limit=1, after=cursor)


def test_scope_reduction_blocks_old_operation_and_receipts(fixture, postgres):
    op = proposal(fixture)['result']['operation']
    grants(postgres, 'alice', 'approver')
    store = service(fixture, postgres)
    approved = store.approve(op['operation_id'], 1, **options('approve', 'alice'))
    grants(postgres, 'alice', 'approver', objects=fixture[2][:1], revision=1)
    for call in (lambda: store.get_operation(op['operation_id']), lambda: store.history(operation_id=op['operation_id']),
                 lambda: store.approve(op['operation_id'], 1, **options('approve', 'alice'))):
        with pytest.raises(HiddenObject):
            call()
    assert approved['result']['operation']['state'] == 'approved'


def test_revocation_serializes_with_inflight_command(fixture, postgres):
    row = task(fixture)['result']['task']
    grants(postgres, 'alice')
    entered, finish, revoke_started = Event(), Event(), Event()
    class PausedWorkflow(AuthorizedWorkflow):
        def _claim(self, *args):
            entered.set()
            assert finish.wait(timeout=4)
            return super()._claim(*args)
    store = PausedWorkflow(postgres.connect, fixture[0].context, 'alice')
    def revoke():
        revoke_started.set()
        return grants(postgres, 'alice', revision=1, rows=[])
    with ThreadPoolExecutor(max_workers=2) as pool:
        claim = pool.submit(store.claim, row['task_id'], 1, seconds=60, **options('claim', 'alice'))
        assert entered.wait(timeout=3)
        revoked = pool.submit(revoke)
        assert revoke_started.wait(timeout=3)
        assert not revoked.done()
        finish.set()
        assert claim.result(timeout=5)['result']['task']['state'] == 'claimed'
        assert revoked.result(timeout=5)['revision'] == 2
    with pytest.raises(AccessDenied):
        service(fixture, postgres).claim(row['task_id'], 1, seconds=60, **options('claim', 'alice'))


def test_access_grants_and_revocation_persist_after_restart(fixture, postgres):
    row = task(fixture)['result']['task']
    receipt = grants(postgres, 'alice')
    postgres.restart()
    assert service(fixture, postgres).get_task(row['task_id']) == row
    grants(postgres, 'alice', revision=1, rows=[])
    postgres.restart()
    with pytest.raises(AccessDenied):
        service(fixture, postgres).get_task(row['task_id'])


def test_missing_audit_and_corrupt_policy_fail_closed(fixture, postgres):
    row = task(fixture)['result']['task']
    grants(postgres, 'alice')
    with postgres.connect() as connection, connection.transaction():
        connection.execute('ALTER TABLE lm_control.access_event DISABLE TRIGGER immutable_access_event')
        connection.execute("UPDATE lm_control.access_event SET receipt_sha256=repeat('f',64)")
        connection.execute('ALTER TABLE lm_control.access_event ENABLE TRIGGER immutable_access_event')
    with pytest.raises(AccessUnavailable):
        service(fixture, postgres).get_task(row['task_id'])


def role_connection(postgres):
    connection = postgres.connect()
    connection.execute('SET ROLE workflow_fixture_app')
    return connection


def configure_role(postgres):
    with postgres.connect() as connection:
        if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname='workflow_fixture_app'").fetchone():
            connection.execute('CREATE ROLE workflow_fixture_app NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE')
        grant_workflow_role(connection, 'workflow_fixture_app')


def test_nonowner_database_role_runs_workflow_but_cannot_change_grants_or_masters(fixture, postgres):
    _, _, ids = fixture
    grants(postgres, 'alice')
    grants(postgres, 'bob', 'approver')
    configure_role(postgres)
    connect = lambda: role_connection(postgres)
    store = AuthorizedWorkflow(connect, fixture[0].context, 'alice')
    created = store.create_task('merge', ids, evidence={}, **options('create', 'alice'))['result']['task']
    claimed = store.claim(created['task_id'], 1, seconds=60, **options('claim', 'alice'))['result']['task']
    proposed = store.propose(created['task_id'], 2, claimed['lease_token'], {i: 1 for i in ids},
        {'survivor_id': ids[0]}, evidence={}, **options('propose', 'alice'))
    op = proposed['result']['operation']
    approval = AuthorizedWorkflow(connect, fixture[0].context, 'bob').approve(op['operation_id'], 1, **options('approve', 'bob'))
    assert approval['result']['operation']['state'] == 'approved'
    assert len(store.history(task_id=created['task_id'])['items']) == 4
    queries = ["UPDATE lm_control.access_policy SET revision=revision+1",
               "INSERT INTO lm_control.access_subject VALUES ('company','intruder')",
               'DELETE FROM lm_control.steward_task', 'TRUNCATE lm_control.workflow_command',
               'UPDATE lm_control.master_identity SET revision=revision+1',
               'UPDATE lm_control.master_identity SET domain_id=domain_id',
               'UPDATE lm_control.domain_version SET domain_id=domain_id',
               "CREATE TABLE lm_control.unexpected(id integer)"]
    for query in queries:
        with connect() as connection, pytest.raises(psycopg.Error):
            connection.execute(query)
    with connect() as connection:
        assert connection.execute('SELECT current_user').fetchone()[0] == 'workflow_fixture_app'


def test_role_installer_rejects_owner(fixture, postgres):
    with postgres.connect() as connection, pytest.raises(ContractError):
        grant_workflow_role(connection, 'lm_registry_test')


def test_role_installer_refuses_existing_broad_grants(fixture, postgres):
    configure_role(postgres)
    with postgres.connect() as connection:
        connection.execute('GRANT UPDATE ON lm_control.access_policy TO workflow_fixture_app')
        with pytest.raises(ContractError, match='broader'):
            grant_workflow_role(connection, 'workflow_fixture_app')


def test_dispatch_returns_only_generic_errors_and_rechecks_replays(fixture, postgres):
    row = task(fixture)['result']['task']
    api = WorkflowAPI(postgres.connect, [fixture[0].context])
    assert api.dispatch('alice', 'company', 'get_task', {'task_id': row['task_id']}).status == 403
    grants(postgres, 'alice')
    request = dict(task_id=row['task_id'], expected_revision=1, seconds=60, reason='Fixture')
    result = api.dispatch('alice', 'company', 'claim', request, key='claim')
    assert result.status == 200
    assert api.dispatch('alice', 'company', 'claim', request, key='claim') == result
    assert api.dispatch('alice', 'company', 'claim', {**request, 'actor': 'bob'}, key='x').status == 422
    assert api.dispatch('alice', 'other', 'get_task', {'task_id': row['task_id']}).status == 404
    grants(postgres, 'alice', revision=1, rows=[])
    denied = api.dispatch('alice', 'company', 'claim', request, key='claim')
    assert denied.status == 403 and row['task_id'] not in str(denied.body)


def test_populated_schema_five_upgrade_preserves_workflow(fixture, postgres, tmp_path):
    from lakematch.mastering.contracts import DomainContract
    from lakematch.mastering.registry import PostgresRegistry
    from lakematch.mastering.workflow import PostgresWorkflow
    import json
    root = Path(__file__).resolve().parents[2]
    migrations = root/'app/migrations/mastering'
    for path in migrations.glob('000[1-5]*.sql'):
        shutil.copy2(path, tmp_path/path.name)
    with postgres.connect() as connection:
        connection.execute('DROP SCHEMA lm_control CASCADE')
        apply_migrations(connection, tmp_path)
    domain = DomainContract.from_dict(json.loads((root/'examples/mastering/company_pilot/domain.json').read_text()))
    registry = PostgresRegistry(postgres.connect)
    registry.submit_domain(domain, actor='engineer', expected_latest=0)
    registry.transition('domain', 'company', 'company', 1, state='approved', expected_revision=1,
                        actor='approver', reason='Upgrade fixture')
    # Use the genuine pre-access worker tables with a synthetic existing identity.
    master_id = str(uuid4())
    with postgres.connect() as connection:
        connection.execute("INSERT INTO lm_control.master_identity(domain_id,master_id,state) VALUES ('company',%s,'active')", (master_id,))
    raw = PostgresWorkflow(postgres.connect, fixture[0].context)
    receipt = raw.create_task('override', [master_id], evidence={'historic': True}, **options('before-upgrade'))
    with postgres.connect() as connection:
        assert list(apply_migrations(connection, migrations)) == [1, 2, 3, 4, 5, 6]
    assert raw.create_task('override', [master_id], evidence={'historic': True}, **options('before-upgrade')) == receipt
    grants(postgres, 'alice', 'viewer')
    assert service(fixture, postgres).get_task(receipt['result']['task']['task_id']) == receipt['result']['task']
