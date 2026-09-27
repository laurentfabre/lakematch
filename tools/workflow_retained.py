"""Read-only verification of the installed, otherwise unused deployment fixture."""
import hashlib
from pathlib import Path

from lakematch.mastering.access_contract import grant_set
from lakematch.mastering.contracts import DomainContract, digest

ROOT = Path(__file__).resolve().parents[1]


class RetainedStateError(ValueError):
    """Credential-free diagnostic constructed by this verifier or its caller."""


def require(condition, message):
    if not condition:
        raise RetainedStateError(message)


def verify_retained_fixture(connect, serving_role, principal, fixture):
    """Refuse drift or previous workflow use; never migrate, reseed or repair."""
    require(principal == fixture['principal'], 'Retained operator does not match')
    expected_migrations = {int(p.name[:4]): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in (ROOT/'app/migrations/mastering').glob('*.sql')}
    require(expected_migrations == {int(k): v for k, v in fixture['migrations'].items()},
            'Recorded migrations do not match source')
    with connect() as connection, connection.transaction():
        connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        connection.execute("SET LOCAL statement_timeout='15s'")
        connection.execute("SET LOCAL lock_timeout='5s'")
        migrations = dict(connection.execute(
            'SELECT version,sha256 FROM lm_control.schema_migration ORDER BY version LIMIT 7').fetchall())
        require(migrations == expected_migrations, 'Installed migrations changed')
        role = connection.execute('''SELECT r.rolsuper,r.rolbypassrls,r.rolcreaterole,r.rolcreatedb,
            EXISTS(SELECT 1 FROM pg_auth_members m WHERE m.member=r.oid),
            EXISTS(SELECT 1 FROM pg_namespace n WHERE n.nspname='lm_control' AND n.nspowner=r.oid),
            EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                   WHERE n.nspname='lm_control' AND c.relowner=r.oid)
            FROM pg_roles r WHERE r.rolname=%s''', (serving_role,)).fetchone()
        require(role is not None and not any(role), 'Serving role is no longer restricted')
        require(connection.execute('''SELECT has_schema_privilege(%s,'lm_control','USAGE'),
            has_schema_privilege(%s,'lm_control','CREATE')''', (serving_role, serving_role)).fetchone()
                == (True, False), 'Serving schema grants changed')
        domains = connection.execute('''SELECT domain_id,version,definition,definition_sha256,state,
            created_by,approved_by FROM lm_control.domain_version LIMIT 2''').fetchall()
        require(len(domains) == 1, 'Expected exactly one retained domain')
        row = domains[0]
        require(row[:2] == ('company', 1) and row[3:]
                == (fixture['domain_sha256'], 'approved', 'synthetic:company-pilot-fixture-v1', principal)
                and DomainContract.from_dict(row[2]).sha256 == fixture['domain_sha256'],
                'Approved fixture domain changed')
        masters = connection.execute('''SELECT domain_id,master_id::text,revision,state,redirect_to
            FROM lm_control.master_identity LIMIT 2''').fetchall()
        require(masters == [('company', fixture['master_id'], 1, 'active', None)],
                'Retained master identity changed')
        sources = connection.execute('''SELECT domain_id,source_id,source_key,master_id::text
            FROM lm_control.source_identity ORDER BY source_id LIMIT 3''').fetchall()
        require(sources == [('company', source, 'deployment-fixture-001', fixture['master_id'])
                            for source in ('crm_account', 'erp_vendor')], 'Retained crosswalk changed')
        identity = connection.execute('''SELECT actor,idempotency_key,request,payload_sha256,receipt
            FROM lm_control.identity_event LIMIT 2''').fetchall()
        require(len(identity) == 1 and identity[0][:2] == (principal, 'deployment-identity-v1')
                and digest(identity[0][2]) == identity[0][3]
                and identity[0][4]['result']['master_id'] == fixture['master_id'],
                'Retained identity receipt changed')
        policy = connection.execute('''SELECT principal,domain_id,revision,definition,definition_sha256
            FROM lm_control.access_policy LIMIT 2''').fetchall()
        definition = grant_set(principal, 'company', fixture['grants'])
        require(policy == [(principal, 'company', 1, definition, digest(definition))],
                'Retained fixture access policy changed')
        event = connection.execute('''SELECT request,request_sha256,receipt,receipt_sha256
            FROM lm_control.access_event LIMIT 2''').fetchall()
        require(len(event) == 1 and event[0][2] == fixture['grant']
                and digest(event[0][0]) == event[0][1] and digest(event[0][2]) == event[0][3]
                and event[0][0]['definition'] == definition, 'Retained access receipt changed')
        counts = connection.execute('''SELECT
            (SELECT count(*) FROM lm_control.steward_task),
            (SELECT count(*) FROM lm_control.workflow_command),
            (SELECT count(*) FROM lm_control.operation),
            (SELECT count(*) FROM lm_control.steward_decision),
            (SELECT count(*) FROM lm_control.outbox_event)''').fetchone()
        require(counts == (0, 0, 0, 0, 0), 'Retained workflow has already been used')
        return {'migrations': migrations, 'master_id': fixture['master_id'],
                'source_crosswalks': len(sources), 'access_revision': 1,
                'access_receipt_sha256': digest(event[0][2]), 'workflow_counts': list(counts),
                'transaction_read_only': connection.execute('SHOW transaction_read_only').fetchone()[0]}
