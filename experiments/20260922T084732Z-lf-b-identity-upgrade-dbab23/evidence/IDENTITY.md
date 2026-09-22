# Persistent identity policy v0.1

LM-004 adds an explicitly selected `persistent_uuid_v1` worker adapter alongside
the unchanged Spark `identity.assign` minimum-member behavior. It requires the
optional PostgreSQL dependency and additive migration 0003. It does not alter
old configs, model files, deterministic IDs or published snapshots.

An identity context pins an approved domain version and its definition digest.
Source references are literal `(source_id, source_key)` pairs; the same source
key in another source or domain is distinct. Upstream mapping/decision workers
must supply eligible records: this service does not infer matches or treat a
branch as a legal company. It accepts no source payloads or evaluation truth.

## Commands and policy

- `allocate`: reserve a UUID for a nonempty group of unbound source references.
  If every reference already resolves to the same active master, reuse that
  master. Partially bound groups or groups spanning masters require an explicit
  attachment/merge and fail without mutation.
- `attach`: add references and/or legacy aliases to an explicitly selected active
  master at its expected revision. Keys already assigned elsewhere conflict.
  Adding an earlier-sorting key never changes the master UUID.
- `merge`: the request names the survivor and expected revision of every active
  participant. Memberships move to the survivor and losing UUIDs redirect to it.
- `split_new`: move a nonempty proper subset of one master's membership to a
  newly allocated UUID. Existing aliases stay bound to their original identities.
- `restore_merge`: invert one recorded merge, restoring its prior UUIDs and
  membership. Every participant must have the recorded post-merge membership,
  aliases and redirect state, at its current expected revision; nested merges
  must be reversed first. Each merge can be restored only once. Restoration
  increments revisions and appends history rather than erasing the merge.

The actor and idempotency key identify a command across domains. The digest binds
the domain/policy version, reason, inputs and expected revisions. An exact retry
returns its original immutable receipt, even after a later operation; reusing a
key with different content conflicts. A receipt says `identity_applied`, never
`published`: Delta snapshots and serving projections are separate work.

Aliases are immutable `(policy, namespace, old_id) → original UUID` bindings.
`spark_min_member_sha256_v1` accepts the exact 64-hex ID from an existing snapshot;
it never recalculates or rewrites that ID. Resolution follows UUID redirects.
After restoring a merge, an old alias resolves to its original restored UUID.
Mutations require canonical active IDs; passing an obsolete alias cannot silently
change which object a command edits.

## Transaction and operating boundary

Each write owns a dedicated transaction and takes the identity writer advisory
lock. Database primary/unique constraints back source and alias uniqueness.
Domain approval is read under a share lock. Membership, revisions and the
immutable event/receipt commit together. Reads use a consistent read-only
transaction. Bounds are 1,000 members/aliases per identity, 32 merge participants,
64 redirect hops, 1,000 ancestors inspected before a merge, 1 MiB per command
and 100 events per history page. A merge exceeding an ancestor/hop bound fails
before changing any redirect, so existing IDs remain resolvable.
Receipt and creation timestamps serialize in UTC, independently of a caller's
PostgreSQL session timezone.

The first adapter deliberately serializes identity writes; throughput at serving
scale has not been qualified. Actors must be derived by a trusted caller. No
authentication, domain grant, RLS or independent operation-approval boundary is
implemented here. Direct database access is privileged. This API is not exposed
to the app; LM-007/008/011 must enforce those boundaries before user-facing use.

Migration 0003 preserves prior checksums. Unattributed prototype `merged` rows
without redirects fail migration rather than inventing a destination. Original
0001/0002 and frozen Phase A evidence remain unchanged. Source deletion and ID
retirement are intentionally unsupported by this policy version.

## Internal worker use

Install the optional dependencies as described in [REGISTRY.md](REGISTRY.md),
and apply the complete checksummed migration directory through
`apply_migrations(connection, directory)`. Supply a factory for new dedicated
connections. Resolve an approved `DomainContract` before selecting this policy:

```python
from lakematch.mastering.identity_contract import IdentityContext, SourceRef
from lakematch.mastering.identity_registry import PostgresIdentityRegistry

identities = PostgresIdentityRegistry(
    connect, IdentityContext(domain.domain_id, domain.version, domain.sha256)
)
receipt = identities.allocate(
    [SourceRef("erp_vendor", "vendor-100"), SourceRef("crm_account", "account-100")],
    actor=trusted_actor, reason="Apply the approved membership decision", key=command_key,
)
master_id = receipt["result"]["master_id"]
```

Membership decisions and `trusted_actor` must come from the calling workflow;
candidate similarity alone does not authorize this allocation. `get` returns
the resolved master plus the requested identity's revision/state, so a caller
can display redirects and submit explicit expected revisions. History uses a
monotonically increasing sequence cursor; page with the last returned sequence.

`LAKEMATCH_TEST_POSTGRES=1 .venv/bin/python -m pytest -q tests/postgres`
runs against owned disposable local databases only. The separate
`tests/test_identity_bridge.py` also requires local Spark/Java 17 and verifies
actual old-policy IDs against the new alias resolver. The bounded evidence
runner is `tools/lakefusion_identity_run.py`; use fresh output paths.
