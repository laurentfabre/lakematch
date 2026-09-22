# Operational registry and candidate execution v0.1

Implemented 2026-09-22 for LM-002/003. This extends the immutable Phase A
contract with an additive migration and optional PostgreSQL adapter. It does
not change the Phase A frozen definitions, existing engine v1 configuration,
legacy model artifacts or sealed confirmation results.

## What is persistent

PostgreSQL stores domain, source-mapping, candidate-execution and scalar
survivorship policy versions.
Definitions are immutable even while in draft; edits create a new version.
Each namespace requires an explicit expected latest version. Submitting the
same version and content returns its original receipt; different content or a
stale latest-version expectation conflicts. A transaction includes the version
and its immutable audit event. Concurrent registry writes serialize under a
transaction-scoped database lock and are backed by unique constraints.

The lifecycle is `draft → approved → retired`. Approval requires an actor
different from the definition's creator, an explicit reason and the expected
revision. A retry of the same actor/reason/revision returns the same approval;
a competing approval conflicts. Retirement preserves approval attribution and
history, and prevents new jobs from resolving that dependency. A new version
does not silently replace an older approved version in a pinned job.

The adapter is for **trusted internal callers**. Its actor strings are supplied
by that caller; it does not authenticate people or issue domain permissions.
An application must derive actors from authenticated requests and enforce its
role/domain/field policy. Database roles/RLS and the HTTP registry routes remain
LM-008/application work. The migration grants no application access. Synthetic
test actors demonstrate state-machine behavior only.

## Job binding and compatibility

`ExecutionSpec` pins its own version, the domain version/hash, both source
mapping versions/hashes, the retrieval alternative, the retrieval implementation's
SHA-256 and all finite limits. Domain hashes are `DomainContract.sha256`; mapping
hashes are `SourceMapping.sha256`, which include the bound domain. These canonical
contract hashes are distinct from raw JSON-file checksums in fixture manifests.

`PostgresRegistry.run_candidates` resolves all four currently approved objects
and their matching immutable approval events under database row locks. It checks
every digest, code reference, identity granularity and required feature mapping,
then validates both full source inputs before retrieval. No partial candidate
result is returned if a row violates its schema or repeats a source key.

The returned job envelope includes the complete versioned definitions, approval
receipts, feature allowlist, input snapshot hashes/counts and a semantic hash of
the candidate rows. This supports exact retry comparison without comparing wall
time. Approval is recorded **at job resolution**. A saved envelope is not a new
authorization decision; application revocation and publication must recheck
their current policy when those paths are implemented.

The bound pilot uses the comparison's selected `identifier_name` alternative:
95% validation recall and 8,552 pairs. The 200 combined-error misses remain;
the lexical method's 100% coverage remains an explicitly different configuration.
Changing the alternative, limits, mappings or retrieval code requires a new
execution version and approval. This registry execution emits candidates, not
identity merges, master records or automatic matching decisions.

`preview_mapping` is bounded to 1,000 rows and 1 MiB. It returns accepted mapping
receipts and row-indexed errors. The company pilot quarantines branch records
for separate relationship handling. Source schema drift and duplicate keys are
visible failures. This is an engineering preview; it is not the completed
onboarding/remediation workflow in LM-012.

`company_feature_config` and `legacy_feature_rows` explicitly project legal-company
records into the existing v1 row/config shape. Identifiers remain strings; parent,
truth and split fields are excluded. An incompatible old configuration is rejected
without rewriting it. This adapter covers feature inputs only: it does not claim
that the new portable candidate union is the v1 Spark candidate implementation,
or that old models are compatible with a changed feature set.

## Installation, migration and checks

The engine remains usable without a PostgreSQL driver. Install the optional
extra for a registry worker (`lakematch[postgres]`) or reproduce the tested
local adapter dependencies with:

```sh
uv pip install --python .venv/bin/python --require-hashes -r requirements-postgres.lock
LAKEMATCH_TEST_POSTGRES=1 .venv/bin/python -m pytest -q tests/postgres
```

The [wheel packaging check](../../bench/lakefusion/registry-package-20260922.json)
passes with the declared isolated build backend (`uv build --wheel`). The 91,488-byte
wheel contains the exact tested mastering modules and declares psycopg only under
the `postgres` extra. Portable execution modules import successfully with that
driver unavailable. Ship the versioned SQL migration directory alongside the
wheel; those operator artifacts are not embedded in the engine wheel. The receipt
also retains the first non-isolated attempt's missing-build-backend failure.

The explicit integration suite requires installed `initdb` and `postgres`.
It creates a private temporary data directory and Unix socket, disables TCP,
keeps fsync enabled, and stops/removes only its own instance. No supplied DSN
or existing PostgreSQL service is used for test resets. The ordinary portable
test suite skips this optional integration module unless explicitly enabled;
the managed commit gate enables it when registry or migration files change.

Use `apply_migrations` with a dedicated idle connection and the complete
`app/migrations/mastering/` directory. It applies the ordered files atomically,
checks their SHA-256 values on every retry, and refuses gaps, changed applied
files and downgrade attempts. **Never edit applied migration 0001.** Migration
0002 adds revisions, approval attribution, execution definitions, immutable
registry events and definition/state guards.
Migration 0003 adds [persistent identities](IDENTITY.md); migration 0004 adds
the [scalar policy registry](SURVIVORSHIP.md). Applied migrations stay immutable.

An older prototype database containing approved rows without attribution fails
the upgrade atomically. Export and review those records before migration;
the tool does not invent approvers or silently reset approval state. Draft
prototype records retain their `legacy-unattributed` creator until reviewed
through an explicitly authored new version. Do not expose the database to app
users before the separately qualified grants/RLS deployment.

`PostgresRegistry` accepts a connection factory so deployment can provide its
own host/database credentials and connection renewal. The local tests qualify
PostgreSQL 16.15 and psycopg 3.3.5. They do not prove Lakebase connection grants,
OAuth refresh, app delegation or a remote deployment. No such resource was
provisioned or accessed in this increment.

## Evidence

The [registry experiment](../../bench/lakefusion/registry-20260922.json) reports
**93 passing checks, zero failures/errors/skips**, including 18 actual PostgreSQL
integration cases. Migration retry/drift/downgrade, concurrent submission and
approval, failed-audit rollback, immutable history, retirement and process
restart all pass. The registry-bound validation candidate rows exactly equal
the preceding retained artifact; source and implementation hashes are recorded.
The branch preview accepts six CRM legal companies and quarantines one branch.

Subsequent increments implement [persistent identities](IDENTITY.md) and
[scalar survivorship](SURVIVORSHIP.md) for internal workers. Use
`submit_survivorship(policy, actor=..., expected_latest=...)`, the existing
`transition("survivorship", ...)` lifecycle and
`resolve_survivorship(domain_id, policy_id, version)` to bind currently approved
domain/mapping/policy versions. Field provenance storage, publication and the
golden-record app view remain Phase B work. The registry alone does not complete
the MDM pilot.
