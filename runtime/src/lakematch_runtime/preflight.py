"""Read-only checks; serving never installs schemas, grants or migrations."""
import hashlib
from importlib.resources import files

from lakematch.mastering.access_contract import AccessUnavailable
from lakematch.mastering.contracts import DomainContract


SELECT = {'schema_migration', 'domain_version', 'registry_event', 'master_identity', 'access_subject',
          'access_policy', 'access_event', 'steward_task', 'operation', 'steward_decision', 'workflow_command'}
INSERT = {'steward_task', 'operation', 'steward_decision', 'workflow_command', 'outbox_event'}
UPDATE = {'steward_task', 'operation'}
KEY_UPDATE = {'domain_version', 'master_identity', 'access_subject'}


def expected_migrations():
    paths = sorted(files('lakematch_runtime').joinpath('migrations').iterdir(), key=lambda p: p.name)
    result = {int(p.name[:4]): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in paths if p.name.endswith('.sql')}
    if sorted(result) != list(range(1, 7)):
        raise AccessUnavailable('Runtime migration package is invalid')
    return result


def verify_connection(connection, binding, user, *, migrations=None):
    """Recheck identity, permissions and schema on every new owned socket."""
    expected = expected_migrations() if migrations is None else migrations
    identity = connection.execute('SELECT session_user,current_user,current_database()').fetchone()
    if identity != (user, user, binding.database):
        raise AccessUnavailable('Database identity does not match the deployment binding')
    role = connection.execute('''SELECT r.rolsuper,r.rolbypassrls,r.rolcreaterole,r.rolcreatedb,
        EXISTS(SELECT 1 FROM pg_auth_members m WHERE m.member=r.oid),
        EXISTS(SELECT 1 FROM pg_namespace n WHERE n.nspname='lm_control' AND n.nspowner=r.oid),
        EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='lm_control' AND c.relowner=r.oid)
        FROM pg_roles r WHERE r.rolname=current_user''').fetchone()
    if role is None or any(role):
        raise AccessUnavailable('Runtime requires a dedicated nonowner database role')
    schema = connection.execute("SELECT has_schema_privilege('lm_control','USAGE'),has_schema_privilege('lm_control','CREATE')").fetchone()
    if schema != (True, False):
        raise AccessUnavailable('Unexpected runtime schema privileges')
    tables = connection.execute("""SELECT c.relname,p.privilege,
        has_table_privilege(c.oid,p.privilege),has_table_privilege(c.oid,p.privilege||' WITH GRANT OPTION')
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        CROSS JOIN (VALUES ('SELECT'),('INSERT'),('UPDATE'),('DELETE'),('TRUNCATE'),('REFERENCES'),('TRIGGER')) p(privilege)
        WHERE n.nspname='lm_control' AND c.relkind IN ('r','p') LIMIT 455""").fetchall()
    names = {row[0] for row in tables}
    if not 1 <= len(names) <= 64 or not (SELECT | INSERT | KEY_UPDATE) <= names:
        raise AccessUnavailable('Unexpected control schema size or missing tables')
    allowed = {'SELECT': SELECT, 'INSERT': INSERT, 'UPDATE': UPDATE}
    for table, privilege, actual, grantable in tables:
        if actual != (table in allowed.get(privilege, set())) or grantable:
            raise AccessUnavailable('Unexpected runtime table privileges')
    columns = connection.execute("""SELECT c.relname,a.attname,
        has_column_privilege(c.oid,a.attnum,'UPDATE'),has_column_privilege(c.oid,a.attnum,'INSERT'),
        has_column_privilege(c.oid,a.attnum,'SELECT'),has_column_privilege(c.oid,a.attnum,'REFERENCES'),
        has_column_privilege(c.oid,a.attnum,'UPDATE WITH GRANT OPTION'),
        has_column_privilege(c.oid,a.attnum,'INSERT WITH GRANT OPTION'),
        has_column_privilege(c.oid,a.attnum,'SELECT WITH GRANT OPTION'),
        has_column_privilege(c.oid,a.attnum,'REFERENCES WITH GRANT OPTION')
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_attribute a ON a.attrelid=c.oid
        WHERE n.nspname='lm_control' AND c.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped
        LIMIT 4097""").fetchall()
    if len(columns) > 4096:
        raise AccessUnavailable('Unexpected control schema column count')
    for table, column, update, insert, select, references, *grantable in columns:
        if (update != (table in UPDATE or (table in KEY_UPDATE and column == 'domain_id'))
                or insert != (table in INSERT) or select != (table in SELECT) or references or any(grantable)):
            raise AccessUnavailable('Unexpected runtime column privileges')
    sequence = connection.execute('''SELECT
        has_sequence_privilege('lm_control.workflow_command_sequence_seq','USAGE'),
        has_sequence_privilege('lm_control.workflow_command_sequence_seq','SELECT'),
        has_sequence_privilege('lm_control.workflow_command_sequence_seq','UPDATE'),
        has_sequence_privilege('lm_control.workflow_command_sequence_seq','USAGE WITH GRANT OPTION')''').fetchone()
    if sequence != (True, False, False, False):
        raise AccessUnavailable('Unexpected runtime command-sequence privileges')
    if dict(connection.execute('SELECT version,sha256 FROM lm_control.schema_migration ORDER BY version').fetchall()) != expected:
        raise AccessUnavailable('Control schema requires an explicit operator migration')
    for context in binding.contexts:
        row = connection.execute('''SELECT definition,definition_sha256,state FROM lm_control.domain_version
            WHERE domain_id=%s AND version=%s''', (context.domain_id, context.domain_version)).fetchone()
        if (row is None or row[1:] != (context.domain_sha256, 'approved')
                or DomainContract.from_dict(row[0]).sha256 != context.domain_sha256):
            raise AccessUnavailable('Pinned workflow domain is not approved and intact')
