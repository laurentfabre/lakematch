"""Optional PostgreSQL persistent identities for trusted internal workers.

These methods apply identity state, not business approval or Delta publication.
Every connection is owned by the call; no HTTP identity or database grants are
derived here. The existing Spark minimum-member policy remains independent.
"""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import timezone
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .contracts import ContractError, DomainContract, digest, positive_version
from .identity_contract import (
    IdentityConflict, IdentityContext, IdentityUnavailable, LegacyAlias, SourceRef,
    MAX_ALIASES, MAX_MEMBERS, MAX_REDIRECTS, command_payload, master_key,
    references, revisions, text_key,
)


class PostgresIdentityRegistry:
    def __init__(self, connect, context):
        if not isinstance(context, IdentityContext):
            raise ContractError("An explicit versioned identity context is required")
        self._connect, self.context = connect, context

    @contextmanager
    def _transaction(self, *, write=False):
        with self._connect() as connection:
            with connection.transaction():
                if not write:
                    connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                connection.execute("SET LOCAL lock_timeout = '5s'")
                connection.execute("SET LOCAL statement_timeout = '15s'")
                if write:
                    # First policy serializes identity commands, including receipt
                    # keys across domains. Constraints remain the durable backstop.
                    connection.execute("SELECT pg_advisory_xact_lock(127934, 3)")
                with connection.cursor(row_factory=dict_row) as cursor:
                    yield cursor

    @property
    def domain_id(self):
        return self.context.domain_id

    def _require_approved_domain(self, cursor):
        cursor.execute("""SELECT v.* FROM lm_control.domain_version v
            JOIN lm_control.registry_event e ON e.kind='domain' AND e.action='approved'
             AND e.domain_id=v.domain_id AND e.object_id=v.domain_id AND e.version=v.version
             AND e.revision=v.revision AND e.definition_sha256=v.definition_sha256
             AND e.actor=v.approved_by AND e.reason=v.approval_reason
            WHERE v.domain_id=%s AND v.version=%s AND v.state='approved' FOR SHARE OF v""",
            (self.domain_id, self.context.domain_version))
        row = cursor.fetchone()
        if row is None:
            raise IdentityUnavailable("An approved domain with its immutable approval event is required")
        domain = DomainContract.from_dict(row["definition"])
        if domain.sha256 != row["definition_sha256"] or domain.sha256 != self.context.domain_sha256:
            raise IdentityUnavailable("Identity domain definition digest differs from the approved version")

    def _snapshot(self, cursor, master_id):
        cursor.execute("""SELECT master_id,revision,state,redirect_to,created_at
            FROM lm_control.master_identity WHERE domain_id=%s AND master_id=%s""",
            (self.domain_id, master_id))
        row = cursor.fetchone()
        if row is None:
            raise IdentityUnavailable("Master does not exist in this domain")
        cursor.execute("""SELECT source_id,source_key FROM lm_control.source_identity
            WHERE domain_id=%s AND master_id=%s ORDER BY source_id,source_key LIMIT %s""",
            (self.domain_id, master_id, MAX_MEMBERS + 1))
        members = cursor.fetchall()
        cursor.execute("""SELECT namespace,old_id,policy_version FROM lm_control.identity_alias
            WHERE domain_id=%s AND master_id=%s ORDER BY namespace,old_id,policy_version LIMIT %s""",
            (self.domain_id, master_id, MAX_ALIASES + 1))
        aliases = cursor.fetchall()
        if len(members) > MAX_MEMBERS or len(aliases) > MAX_ALIASES:
            raise IdentityConflict("Stored identity exceeds the bounded worker policy")
        return {"master_id": str(row["master_id"]), "revision": row["revision"], "state": row["state"],
                "redirect_to": str(row["redirect_to"]) if row["redirect_to"] else None,
                "created_at": row["created_at"].astimezone(timezone.utc).isoformat(), "members": members, "aliases": aliases}

    def _active(self, cursor, master_id, expected_revision):
        row = self._snapshot(cursor, master_id)
        if row["state"] != "active" or row["revision"] != expected_revision:
            raise IdentityConflict("Master must be active at the expected revision")
        return row

    def _resolve(self, cursor, master_id):
        chain = []
        for _ in range(MAX_REDIRECTS + 1):
            if master_id in chain:
                raise IdentityConflict("Identity redirect cycle")
            chain.append(master_id)
            cursor.execute("""SELECT state,redirect_to FROM lm_control.master_identity
                WHERE domain_id=%s AND master_id=%s""", (self.domain_id, master_id))
            row = cursor.fetchone()
            if row is None or row["state"] == "retired":
                raise IdentityUnavailable("Identity is absent or retired")
            if row["state"] == "active" and row["redirect_to"] is None:
                return master_id, chain
            if row["state"] != "merged" or row["redirect_to"] is None:
                raise IdentityConflict("Inconsistent identity redirect")
            master_id = str(row["redirect_to"])
        raise IdentityConflict("Identity redirect hop budget exceeded")

    def _bindings(self, cursor, members):
        # Request size is bounded before JSON expands into rows in PostgreSQL.
        cursor.execute("""SELECT s.source_id,s.source_key,s.master_id
            FROM jsonb_to_recordset(%s) AS r(source_id text,source_key text)
            JOIN lm_control.source_identity s ON s.domain_id=%s
             AND s.source_id=r.source_id AND s.source_key=r.source_key""", (Jsonb(members), self.domain_id))
        return {(r["source_id"], r["source_key"]): str(r["master_id"]) for r in cursor.fetchall()}

    def _add_members(self, cursor, master_id, members):
        bindings = self._bindings(cursor, members)
        if any(owner != master_id for owner in bindings.values()):
            raise IdentityConflict("A source reference belongs to another master; use an explicit merge")
        fresh = [m for m in members if (m["source_id"], m["source_key"]) not in bindings]
        cursor.executemany("""INSERT INTO lm_control.source_identity(domain_id,source_id,source_key,master_id)
            VALUES (%s,%s,%s,%s)""",
            [(self.domain_id, m["source_id"], m["source_key"], master_id) for m in fresh])

    def _add_aliases(self, cursor, master_id, aliases, *, require_existing=False):
        for alias in aliases:
            key = (self.domain_id, alias["policy_version"], alias["namespace"], alias["old_id"])
            cursor.execute("""SELECT master_id FROM lm_control.identity_alias
                WHERE domain_id=%s AND policy_version=%s AND namespace=%s AND old_id=%s""", key)
            row = cursor.fetchone()
            if row:
                if str(row["master_id"]) != master_id:
                    raise IdentityConflict("Legacy alias is already bound to another original identity")
            elif require_existing:
                raise IdentityConflict("Use attach to add aliases to an already allocated identity")
            else:
                cursor.execute("""INSERT INTO lm_control.identity_alias
                    (domain_id,policy_version,namespace,old_id,master_id) VALUES (%s,%s,%s,%s,%s)""",
                    (*key, master_id))

    def _new_master(self, cursor):
        master_id = str(uuid4())
        cursor.execute("INSERT INTO lm_control.master_identity(domain_id,master_id,state) VALUES (%s,%s,'active')",
                       (self.domain_id, master_id))
        return master_id

    def _advance(self, cursor, master_id, *, state="active", redirect_to=None):
        cursor.execute("""UPDATE lm_control.master_identity SET revision=revision+1,state=%s,redirect_to=%s
            WHERE domain_id=%s AND master_id=%s""", (state, redirect_to, self.domain_id, master_id))

    def _record_event(self, cursor, request, key, before, after, result):
        event_id = str(uuid4())
        cursor.execute("SELECT now() AS at")
        at = cursor.fetchone()["at"].astimezone(timezone.utc)
        receipt = {"event_id": event_id, "domain_id": self.domain_id, "context": asdict(self.context),
                   "kind": request["kind"], "actor": request["actor"], "reason": request["reason"],
                   "idempotency_key": key, "payload_sha256": digest(request), "applied_at": at.isoformat(),
                   "state": "identity_applied", "before": before, "after": after, "result": result}
        cursor.execute("""INSERT INTO lm_control.identity_event
            (event_id,domain_id,domain_version,policy_version,kind,actor,idempotency_key,
             payload_sha256,request,receipt,created_at,reverses_event_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (event_id, self.domain_id, self.context.domain_version, self.context.policy_version,
             request["kind"], request["actor"], key, digest(request), Jsonb(request), Jsonb(receipt), at,
             request["payload"]["merge_event_id"] if request["kind"] == "restore_merge" else None))
        return receipt

    def _execute(self, kind, payload, *, actor, reason, key):
        text_key(key, "Idempotency key")
        request = command_payload(self.context, kind, payload, actor, reason)
        with self._transaction(write=True) as cursor:
            cursor.execute("SELECT payload_sha256,receipt FROM lm_control.identity_event WHERE actor=%s AND idempotency_key=%s",
                           (actor, key))
            prior = cursor.fetchone()
            if prior:
                if prior["payload_sha256"] != digest(request):
                    raise IdentityConflict("Idempotency key was already used for a different command")
                return prior["receipt"]
            self._require_approved_domain(cursor)
            before, after, result = getattr(self, "_" + kind)(cursor, payload)
            return self._record_event(cursor, request, key, before, after, result)

    def allocate(self, members, *, aliases=(), actor, reason, key):
        payload = {"members": references(members, SourceRef),
                   "aliases": references(aliases, LegacyAlias, allow_empty=True)}
        return self._execute("allocate", payload, actor=actor, reason=reason, key=key)

    def _allocate(self, cursor, payload):
        bindings = self._bindings(cursor, payload["members"])
        if bindings:
            canonical = {self._resolve(cursor, m)[0] for m in set(bindings.values())}
            if len(bindings) != len(payload["members"]) or len(canonical) != 1:
                raise IdentityConflict("Partially bound or mixed groups require explicit attach/merge")
            master_id = canonical.pop()
            self._add_aliases(cursor, master_id, payload["aliases"], require_existing=True)
            existing = self._snapshot(cursor, master_id)
            return [existing], [existing], {"master_id": master_id, "outcome": "reused_master"}
        master_id = self._new_master(cursor)
        self._add_members(cursor, master_id, payload["members"])
        self._add_aliases(cursor, master_id, payload["aliases"])
        return [], [self._snapshot(cursor, master_id)], {"master_id": master_id, "outcome": "allocated"}

    def attach(self, master_id, expected_revision, *, members=(), aliases=(), actor, reason, key):
        master_key(master_id)
        positive_version(expected_revision)
        payload = {"master_id": master_id, "expected_revision": expected_revision,
                   "members": references(members, SourceRef, allow_empty=True),
                   "aliases": references(aliases, LegacyAlias, allow_empty=True)}
        if not payload["members"] and not payload["aliases"]:
            raise ContractError("An attachment requires at least one source reference or alias")
        return self._execute("attach", payload, actor=actor, reason=reason, key=key)

    def _attach(self, cursor, payload):
        master_id = payload["master_id"]
        before = self._active(cursor, master_id, payload["expected_revision"])
        self._add_members(cursor, master_id, payload["members"])
        self._add_aliases(cursor, master_id, payload["aliases"])
        self._advance(cursor, master_id)
        return [before], [self._snapshot(cursor, master_id)], {"master_id": master_id}

    def merge(self, survivor_id, expected_revisions, *, actor, reason, key):
        master_key(survivor_id)
        expected = revisions(expected_revisions, minimum=2)
        if survivor_id not in expected:
            raise ContractError("The explicit survivor must be included in expected revisions")
        return self._execute("merge", {"survivor_id": survivor_id, "expected_revisions": expected},
                             actor=actor, reason=reason, key=key)

    def _merge(self, cursor, payload):
        before = [self._active(cursor, key, version) for key, version in payload["expected_revisions"].items()]
        if sum(len(s["members"]) for s in before) > MAX_MEMBERS or sum(len(s["aliases"]) for s in before) > MAX_ALIASES:
            raise IdentityConflict("Combined merge exceeds the bounded member/alias policy")
        survivor = payload["survivor_id"]
        losers = [s["master_id"] for s in before if s["master_id"] != survivor]
        # Bound incoming redirect exploration as well as outgoing resolution.
        cursor.execute("""WITH RECURSIVE ancestors AS (
            SELECT master_id,0 AS depth FROM lm_control.master_identity
             WHERE domain_id=%s AND master_id=ANY(%s::uuid[])
            UNION ALL
            SELECT m.master_id,a.depth+1 FROM lm_control.master_identity m
             JOIN ancestors a ON m.redirect_to=a.master_id WHERE m.domain_id=%s AND a.depth<%s
            ) SELECT depth FROM ancestors LIMIT %s""",
            (self.domain_id, losers, self.domain_id, MAX_REDIRECTS, MAX_MEMBERS + 1))
        ancestors = cursor.fetchall()
        if len(ancestors) > MAX_MEMBERS or any(a["depth"] >= MAX_REDIRECTS for a in ancestors):
            raise IdentityConflict("Merge would exceed redirect hop or ancestor budget")
        cursor.execute("""UPDATE lm_control.source_identity SET master_id=%s
            WHERE domain_id=%s AND master_id=ANY(%s::uuid[])""", (survivor, self.domain_id, losers))
        for row in before:
            key = row["master_id"]
            self._advance(cursor, key, state="active" if key == survivor else "merged",
                          redirect_to=None if key == survivor else survivor)
        after = [self._snapshot(cursor, s["master_id"]) for s in before]
        return before, after, {"master_id": survivor, "redirected_ids": losers}

    def split_new(self, master_id, expected_revision, members, *, actor, reason, key):
        master_key(master_id)
        positive_version(expected_revision)
        return self._execute("split_new", {"master_id": master_id, "expected_revision": expected_revision,
                                          "members": references(members, SourceRef)}, actor=actor, reason=reason, key=key)

    def _split_new(self, cursor, payload):
        master_id = payload["master_id"]
        before = self._active(cursor, master_id, payload["expected_revision"])
        selected = {(m["source_id"], m["source_key"]) for m in payload["members"]}
        available = {(m["source_id"], m["source_key"]) for m in before["members"]}
        if not selected < available:
            raise IdentityConflict("A new-ID split requires a nonempty proper subset of current membership")
        new_id = self._new_master(cursor)
        cursor.executemany("""UPDATE lm_control.source_identity SET master_id=%s
            WHERE domain_id=%s AND source_id=%s AND source_key=%s""",
            [(new_id, self.domain_id, m["source_id"], m["source_key"]) for m in payload["members"]])
        self._advance(cursor, master_id)
        return [before], [self._snapshot(cursor, master_id), self._snapshot(cursor, new_id)], {
            "master_id": master_id, "new_master_id": new_id, "split_policy": "new_identity"}

    def restore_merge(self, merge_event_id, expected_revisions, *, actor, reason, key):
        master_key(merge_event_id)
        expected = revisions(expected_revisions, minimum=2)
        return self._execute("restore_merge", {"merge_event_id": merge_event_id, "expected_revisions": expected},
                             actor=actor, reason=reason, key=key)

    def _restore_merge(self, cursor, payload):
        cursor.execute("SELECT receipt FROM lm_control.identity_event WHERE domain_id=%s AND event_id=%s AND kind='merge'",
                       (self.domain_id, payload["merge_event_id"]))
        event = cursor.fetchone()
        if event is None or event["receipt"]["context"] != asdict(self.context):
            raise IdentityUnavailable("A merge event from the same identity context is required")
        merge = event["receipt"]
        expected = payload["expected_revisions"]
        if set(expected) != {s["master_id"] for s in merge["after"]}:
            raise IdentityConflict("Restoration must name every merge participant")
        cursor.execute("SELECT 1 FROM lm_control.identity_event WHERE reverses_event_id=%s",
                       (payload["merge_event_id"],))
        if cursor.fetchone():
            raise IdentityConflict("This merge has already been restored")
        before = [self._snapshot(cursor, s["master_id"]) for s in merge["after"]]
        def state(row):
            return {k: v for k, v in row.items() if k != "revision"}
        if (any(s["revision"] != expected[s["master_id"]] for s in before)
                or list(map(state, before)) != list(map(state, merge["after"]))):
            raise IdentityConflict("A merge participant changed; restore intervening changes first")
        for prior in merge["before"]:
            master_id = prior["master_id"]
            self._advance(cursor, master_id)
            cursor.executemany("""UPDATE lm_control.source_identity SET master_id=%s
                WHERE domain_id=%s AND source_id=%s AND source_key=%s""",
                [(master_id, self.domain_id, m["source_id"], m["source_key"]) for m in prior["members"]])
        after = [self._snapshot(cursor, s["master_id"]) for s in merge["before"]]
        return before, after, {"restored_merge_event_id": payload["merge_event_id"],
                              "restored_master_ids": [s["master_id"] for s in after], "split_policy": "restore_prior_identities"}

    def get(self, master_id):
        master_key(master_id)
        with self._transaction() as cursor:
            requested = self._snapshot(cursor, master_id)
            resolved, chain = self._resolve(cursor, master_id)
            current = requested if resolved == master_id else self._snapshot(cursor, resolved)
            return {"requested_master_id": master_id, "requested_revision": requested["revision"],
                    "requested_state": requested["state"], "redirect_chain": chain, **current}

    def resolve_source(self, source):
        if not isinstance(source, SourceRef):
            raise ContractError("Expected a typed source reference")
        with self._transaction() as cursor:
            bindings = self._bindings(cursor, [asdict(source)])
            if not bindings:
                raise IdentityUnavailable("Source reference is not bound in this domain")
            resolved, chain = self._resolve(cursor, next(iter(bindings.values())))
            return {"source": asdict(source), "redirect_chain": chain, **self._snapshot(cursor, resolved)}

    def resolve_alias(self, alias):
        if not isinstance(alias, LegacyAlias):
            raise ContractError("Expected a typed legacy alias")
        with self._transaction() as cursor:
            cursor.execute("""SELECT master_id FROM lm_control.identity_alias
                WHERE domain_id=%s AND policy_version=%s AND namespace=%s AND old_id=%s""",
                (self.domain_id, alias.policy_version, alias.namespace, alias.old_id))
            row = cursor.fetchone()
            if row is None:
                raise IdentityUnavailable("Legacy alias is not bound in this domain")
            resolved, chain = self._resolve(cursor, str(row["master_id"]))
            return {"alias": asdict(alias), "redirect_chain": chain, **self._snapshot(cursor, resolved)}

    def history(self, *, after_sequence=0, limit=100):
        if type(after_sequence) is not int or after_sequence < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ContractError("History requires a nonnegative cursor and limit 1–100")
        with self._transaction() as cursor:
            cursor.execute("""SELECT sequence,receipt FROM lm_control.identity_event
                WHERE domain_id=%s AND sequence>%s ORDER BY sequence LIMIT %s""",
                (self.domain_id, after_sequence, limit))
            return cursor.fetchall()
