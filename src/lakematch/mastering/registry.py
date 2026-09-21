"""Optional PostgreSQL registry for trusted internal callers.

Each operation owns a fresh connection/transaction. Caller authentication,
domain grants and database role/RLS deployment are application responsibilities;
this module accepts server-derived actor IDs and grants no SQL privileges.
"""
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
from pathlib import Path
from uuid import uuid4

from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from lakematch.mastering.contracts import ContractError, DomainContract, SourceMapping, identifier, positive_version
from lakematch.mastering.execution import ExecutionBinding, ExecutionSpec, mapping_definition


class RegistryConflict(ValueError):
    """A version, optimistic revision, state or idempotent payload conflicts."""


class RegistryUnavailable(ValueError):
    """A referenced object is absent, retired, unapproved or inconsistent."""


TABLES = {"domain": ("domain_version", None), "mapping": ("source_mapping_version", "source_id"),
          "execution": ("execution_version", "execution_id")}


def nonblank(value, label):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 1000:
        raise ContractError(f"{label} must be nonblank, trimmed text of at most 1000 characters")


def apply_migrations(connection, directory):
    """Apply a complete, ordered manifest atomically; fail on drift or downgrade.

    The caller must provide an idle connection. No migration is run from a read
    or an acceptance verifier, and no already-applied file is rewritten.
    """
    from psycopg.pq import TransactionStatus
    if connection.info.transaction_status != TransactionStatus.IDLE:
        raise RegistryConflict("Migrations require an idle, dedicated connection")
    paths = sorted(Path(directory).glob("[0-9][0-9][0-9][0-9]_*.sql"))
    versions = [int(p.name[:4]) for p in paths]
    if not versions or versions != list(range(1, len(versions) + 1)):
        raise RegistryConflict("Migration versions must be contiguous from 0001")
    manifest = {v: hashlib.sha256(p.read_bytes()).hexdigest() for v, p in zip(versions, paths)}
    with connection.transaction():
        connection.execute("SET LOCAL lock_timeout = '5s'")
        connection.execute("SET LOCAL statement_timeout = '15s'")
        connection.execute("SELECT pg_advisory_xact_lock(127934, 1)")
        connection.execute("CREATE SCHEMA IF NOT EXISTS lm_control")
        connection.execute("""CREATE TABLE IF NOT EXISTS lm_control.schema_migration (
            version INTEGER PRIMARY KEY, sha256 TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
        applied = dict(connection.execute("SELECT version, sha256 FROM lm_control.schema_migration ORDER BY version").fetchall())
        if any(v not in manifest or manifest[v] != h for v, h in applied.items()):
            raise RegistryConflict("Migration checksum mismatch or attempted downgrade")
        if sorted(applied) != list(range(1, len(applied) + 1)):
            raise RegistryConflict("Applied migration history has a gap")
        for version, path in zip(versions, paths):
            if version not in applied:
                connection.execute(path.read_text())
                connection.execute("INSERT INTO lm_control.schema_migration(version, sha256) VALUES (%s,%s)",
                                   (version, manifest[version]))
    return manifest


class PostgresRegistry:
    def __init__(self, connect):
        """connect returns a NEW owned psycopg connection; may refresh OAuth later."""
        self._connect = connect

    @contextmanager
    def _transaction(self, *, write=False):
        with self._connect() as connection:
            with connection.transaction():
                connection.execute("SET LOCAL lock_timeout = '5s'")
                connection.execute("SET LOCAL statement_timeout = '15s'")
                # Registry writes are infrequent configuration changes. Serialize
                # their expected-latest checks; use DB uniqueness as a backstop.
                if write:
                    connection.execute("SELECT pg_advisory_xact_lock(127934, 2)")
                with connection.cursor(row_factory=dict_row) as cursor:
                    yield cursor

    @staticmethod
    def _key(kind, domain_id, object_id, version=None):
        if kind not in TABLES:
            raise ContractError("Unknown registry object kind")
        identifier(domain_id)
        identifier(object_id)
        if kind == "domain" and object_id != domain_id:
            raise ContractError("A domain object's ID must equal its domain")
        values = {"domain_id": domain_id}
        key = TABLES[kind][1]
        if key:
            values[key] = object_id
        if version is not None:
            positive_version(version)
            values["version"] = version
        return values

    @staticmethod
    def _where(values):
        return sql.SQL(" AND ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in values)

    def _fetch(self, cursor, kind, domain_id, object_id, version, *, approved=False):
        values = self._key(kind, domain_id, object_id, version)
        cursor.execute(sql.SQL("SELECT * FROM lm_control.{} WHERE {} FOR SHARE").format(
            sql.Identifier(TABLES[kind][0]), self._where(values)), tuple(values.values()))
        row = cursor.fetchone()
        if row is None or (approved and row["state"] != "approved"):
            raise RegistryUnavailable("Requested registry version is absent or not approved")
        if approved:
            cursor.execute("""SELECT actor,reason,definition_sha256 FROM lm_control.registry_event
                WHERE kind=%s AND domain_id=%s AND object_id=%s AND version=%s
                  AND revision=%s AND action='approved'""",
                (kind, domain_id, object_id, version, row["revision"]))
            event = cursor.fetchone()
            if not event or (event["actor"], event["reason"], event["definition_sha256"]) != (
                    row["approved_by"], row["approval_reason"], row["definition_sha256"]):
                raise RegistryUnavailable("Approved version is missing its matching immutable audit event")
        return row

    @staticmethod
    def _receipt(kind, row):
        return {"kind": kind, "domain_id": row["domain_id"],
                "object_id": row.get("source_id", row.get("execution_id", row["domain_id"])),
                "version": row["version"], "definition_sha256": row["definition_sha256"],
                "state": row["state"], "revision": row["revision"], "created_by": row["created_by"],
                "approved_by": row["approved_by"], "approval_reason": row["approval_reason"],
                "approved_at": row["approved_at"].isoformat() if row["approved_at"] else None}

    def _domain(self, cursor, domain_id, version, *, approved=False):
        row = self._fetch(cursor, "domain", domain_id, domain_id, version, approved=approved)
        domain = DomainContract.from_dict(row["definition"])
        if (domain.domain_id, domain.version, domain.sha256) != (domain_id, version, row["definition_sha256"]):
            raise RegistryUnavailable("Stored domain definition integrity check failed")
        return domain, row

    def _mapping(self, cursor, domain, source_id, version, *, approved=False):
        row = self._fetch(cursor, "mapping", domain.domain_id, source_id, version, approved=approved)
        mapping = SourceMapping.from_dict(row["definition"], domain)
        if (mapping.source_id, mapping.version, mapping.sha256, row["domain_version"]) != (
                source_id, version, row["definition_sha256"], domain.version):
            raise RegistryUnavailable("Stored mapping definition integrity check failed")
        return mapping, row

    def _binding(self, cursor, spec, execution_row=None):
        domain, drow = self._domain(cursor, spec.domain_id, spec.domain_version, approved=True)
        left, lrow = self._mapping(cursor, domain, spec.left_source_id, spec.left_mapping_version, approved=True)
        right, rrow = self._mapping(cursor, domain, spec.right_source_id, spec.right_mapping_version, approved=True)
        approvals = [self._receipt(k, row) for k, row in (("domain", drow), ("mapping", lrow), ("mapping", rrow))]
        if execution_row is not None:
            approvals.append(self._receipt("execution", execution_row))
        return ExecutionBinding(spec, domain, left, right, tuple(approvals))

    def _event(self, cursor, kind, row, actor, reason):
        receipt = self._receipt(kind, row)
        cursor.execute("""INSERT INTO lm_control.registry_event
            (event_id,kind,domain_id,object_id,version,revision,action,actor,reason,definition_sha256)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (uuid4(), kind, row["domain_id"], receipt["object_id"], row["version"], row["revision"],
             row["state"], actor, reason, row["definition_sha256"]))

    def _insert(self, cursor, kind, domain_id, object_id, version, definition, checksum, actor, expected_latest, extra=None):
        nonblank(actor, "Actor")
        if type(expected_latest) is not int or expected_latest < 0 or version != expected_latest + 1:
            raise RegistryConflict("Version must follow the explicit expected latest version")
        key = self._key(kind, domain_id, object_id, version)
        table = sql.Identifier(TABLES[kind][0])
        cursor.execute(sql.SQL("SELECT * FROM lm_control.{} WHERE {}").format(table, self._where(key)), tuple(key.values()))
        existing = cursor.fetchone()
        if existing:
            if existing["definition_sha256"] != checksum:
                raise RegistryConflict("Same version has a different immutable definition")
            return self._receipt(kind, existing)
        namespace = self._key(kind, domain_id, object_id)
        cursor.execute(sql.SQL("SELECT max(version) AS latest FROM lm_control.{} WHERE {}").format(table, self._where(namespace)), tuple(namespace.values()))
        if (cursor.fetchone()["latest"] or 0) != expected_latest:
            raise RegistryConflict("Expected latest version is stale")
        values = {**key, **(extra or {}), "definition": Jsonb(definition), "definition_sha256": checksum,
                  "state": "draft", "created_by": actor}
        cursor.execute(sql.SQL("INSERT INTO lm_control.{} ({}) VALUES ({}) RETURNING *").format(
            table, sql.SQL(",").join(map(sql.Identifier, values)),
            sql.SQL(",").join(sql.Placeholder() for _ in values)), tuple(values.values()))
        row = cursor.fetchone()
        self._event(cursor, kind, row, actor, "submit immutable definition")
        return self._receipt(kind, row)

    def submit_domain(self, domain, *, actor, expected_latest):
        with self._transaction(write=True) as cursor:
            cursor.execute("INSERT INTO lm_control.domain(domain_id) VALUES (%s) ON CONFLICT DO NOTHING", (domain.domain_id,))
            return self._insert(cursor, "domain", domain.domain_id, domain.domain_id, domain.version,
                                asdict(domain), domain.sha256, actor, expected_latest)

    def submit_mapping(self, mapping, *, actor, expected_latest):
        with self._transaction(write=True) as cursor:
            domain, _ = self._domain(cursor, mapping.domain.domain_id, mapping.domain.version)
            if domain.sha256 != mapping.domain.sha256:
                raise RegistryConflict("Mapping domain digest differs from the registered version")
            return self._insert(cursor, "mapping", domain.domain_id, mapping.source_id, mapping.version,
                                mapping_definition(mapping), mapping.sha256, actor, expected_latest,
                                {"domain_version": domain.version})

    def submit_execution(self, spec, *, actor, expected_latest):
        with self._transaction(write=True) as cursor:
            self._binding(cursor, spec)
            extra = {k: getattr(spec, k) for k in ("domain_version", "left_source_id", "left_mapping_version",
                                                   "right_source_id", "right_mapping_version")}
            return self._insert(cursor, "execution", spec.domain_id, spec.execution_id, spec.version,
                                asdict(spec), spec.sha256, actor, expected_latest, extra)

    def transition(self, kind, domain_id, object_id, version, *, state, expected_revision, actor, reason):
        nonblank(actor, "Actor")
        nonblank(reason, "Reason")
        positive_version(expected_revision)
        if state not in {"approved", "retired"}:
            raise RegistryConflict("Only approval or retirement transitions are supported")
        with self._transaction(write=True) as cursor:
            row = self._fetch(cursor, kind, domain_id, object_id, version)
            if row["state"] == state and row["revision"] == expected_revision + 1:
                cursor.execute("""SELECT actor,reason FROM lm_control.registry_event
                    WHERE kind=%s AND domain_id=%s AND object_id=%s AND version=%s AND revision=%s""",
                    (kind, domain_id, object_id, version, row["revision"]))
                event = cursor.fetchone()
                if event and (event["actor"], event["reason"]) == (actor, reason):
                    return self._receipt(kind, row)
            if row["revision"] != expected_revision or row["state"] != ("draft" if state == "approved" else "approved"):
                raise RegistryConflict("Stale registry revision or invalid state transition")
            if state == "approved":
                if actor == row["created_by"]:
                    raise RegistryConflict("Approval requires an independent actor")
                if kind == "domain":
                    self._domain(cursor, domain_id, version)
                elif kind == "mapping":
                    domain, _ = self._domain(cursor, domain_id, row["domain_version"], approved=True)
                    self._mapping(cursor, domain, object_id, version)
                else:
                    self._binding(cursor, self._spec(row))
            values = self._key(kind, domain_id, object_id, version)
            changes = sql.SQL("state=%s, revision=revision+1")
            params = [state]
            if state == "approved":
                changes += sql.SQL(", approved_by=%s, approval_reason=%s, approved_at=now()")
                params += [actor, reason]
            cursor.execute(sql.SQL("UPDATE lm_control.{} SET {} WHERE {} AND revision=%s RETURNING *").format(
                sql.Identifier(TABLES[kind][0]), changes, self._where(values)), (*params, *values.values(), expected_revision))
            changed = cursor.fetchone()
            if changed is None:
                raise RegistryConflict("Stale registry revision")
            self._event(cursor, kind, changed, actor, reason)
            return self._receipt(kind, changed)

    @staticmethod
    def _spec(row):
        spec = ExecutionSpec.from_dict(row["definition"])
        names = ("domain_id", "execution_id", "version", "domain_version", "left_source_id",
                 "left_mapping_version", "right_source_id", "right_mapping_version")
        if spec.sha256 != row["definition_sha256"] or any(getattr(spec, n) != row[n] for n in names):
            raise RegistryUnavailable("Stored execution definition integrity check failed")
        return spec

    def resolve(self, domain_id, execution_id, version):
        """Resolve every currently approved dependency under shared row locks."""
        with self._transaction() as cursor:
            row = self._fetch(cursor, "execution", domain_id, execution_id, version, approved=True)
            return self._binding(cursor, self._spec(row), row)

    def run_candidates(self, domain_id, execution_id, version, left_rows, right_rows):
        from lakematch.mastering.execution import execute_candidates
        return execute_candidates(self.resolve(domain_id, execution_id, version), left_rows, right_rows)

    def get_domain(self, domain_id, version, *, approved=False):
        with self._transaction() as cursor:
            domain, row = self._domain(cursor, domain_id, version, approved=approved)
            return {"definition": asdict(domain), "receipt": self._receipt("domain", row)}

    def get_mapping(self, domain_id, source_id, version, *, approved=False):
        with self._transaction() as cursor:
            row = self._fetch(cursor, "mapping", domain_id, source_id, version, approved=approved)
            domain, _ = self._domain(cursor, domain_id, row["domain_version"], approved=approved)
            mapping, row = self._mapping(cursor, domain, source_id, version, approved=approved)
            return {"definition": mapping_definition(mapping), "receipt": self._receipt("mapping", row)}

    def history(self, kind, domain_id, object_id, version, *, after_revision=0, limit=100):
        self._key(kind, domain_id, object_id, version)
        if type(after_revision) is not int or after_revision < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ContractError("History requires a bounded revision cursor and limit in [1,100]")
        with self._transaction() as cursor:
            cursor.execute("""SELECT revision,action,actor,reason,definition_sha256 FROM lm_control.registry_event
                WHERE kind=%s AND domain_id=%s AND object_id=%s AND version=%s AND revision>%s
                ORDER BY revision LIMIT %s""", (kind, domain_id, object_id, version, after_revision, limit))
            return cursor.fetchall()
