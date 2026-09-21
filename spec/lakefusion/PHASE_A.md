# LF-A pilot contract and feasibility decisions

Version: **0.1 draft, 2026-09-21**. This is a reviewable proposal under LM-001.
Execution was requested through `goal_lakefusion.md`; the user-added decisions
in its §1 remain pending until answered. The schema and policy code delivered
with this document are prototypes, not a completed application workflow.

## Decision record

| Decision | Concrete proposal | State |
|---|---|---|
| Source systems | Synthetic ERP vendor master (`erp_vendor`) and CRM accounts (`crm_account`) | Awaiting user selection |
| Master granularity | Legal company; physical branches and corporate families remain separate objects/relationships | Awaiting user selection |
| Distribution | Internal application; LM-025 not applicable if confirmed | Awaiting user selection |
| Optional AI in pilot | Disabled; adapters and enabled/disabled acceptance remain in later phases | Awaiting user selection |
| Workload/splits/cost | [Evaluation protocol v0.1](PROTOCOL.md) | Awaiting user selection; not frozen |

The prepared [fixture](../../examples/mastering/company_pilot/README.md) contains
13 synthetic rows, six company identities, one branch, a hierarchy, conflicting
addresses, an erroneous identifier collision and reversible-mutation scenarios.
It can change with the source decision. It is never evidence of general matching
accuracy and its truth metadata must not enter feature generation.

## Typed domain and mapping contract

`DomainContract` is separate from the existing engine v1 config. A domain has a
schema version, domain ID, immutable definition version, identity granularity,
typed fields and a canonical SHA-256 digest. The initial implementation supports
strings, string arrays, integers, finite numbers, booleans, dates and timestamps
with explicit time zones. Required values cannot be null or blank. No implicit
string/numeric conversion occurs.

A source mapping binds a literal schema and source key to the exact domain
version **and digest**. Mapping steps use an allowlist of string transforms;
source-schema drift, unknown targets and missing required mappings fail before
processing. Mapping receipts include source ID/key, definition versions, input
contract digests and the canonical payload digest. Leading zeros in identifiers
are preserved. Mapping a row does not determine whether it is a legal-company
candidate, allocate a master ID, perform matching or select winning values.

Source-event sequencing, deletes, reference validation and nested schemas remain
future extensions with explicit schema versions. They will not be introduced
as silent defaults into the existing benchmark contract.

## Initial API contract

These routes are proposed interfaces; they are not registered in the current app.
Existing review routes and receipt formats remain available during migration.

| Route | Request/response essentials | Policy and concurrency |
|---|---|---|
| `GET /v1/domains/{id}/versions/{version}` | Typed definition, digest, state, revision | Scoped read with an explicit allowed field projection |
| `POST /v1/domains/{id}/versions` | Definition and expected previous revision → draft version/digest | Engineer; immutable version; duplicate payload retry returns original receipt |
| `POST /v1/sources/{id}/mappings` | Domain ID/version/digest, source columns/key, field mappings → draft version | Engineer; schema validation and preview before approval |
| `POST /v1/sources/{id}/preview` | Mapping version plus bounded synthetic/sample records → mapped rows and validation errors | Engineer; sample policy and row/byte limits; no publication |
| `GET /v1/entities/{id}` | Published revision, values, memberships, aliases and attribute provenance | Viewer; domain/object/field scope; publication and freshness envelope |
| `POST /v1/operations` | Operation kind, target IDs, expected revisions, reason and payload → pending operation receipt | Steward proposal; authenticated caller is server-derived; idempotency key binds caller and request digest |
| `POST /v1/operations/{id}/approve` | Expected operation revision, reason → approval receipt | Independent Approver; stale revision or self-approval rejected |
| `GET /v1/operations/{id}` | Draft/approval/applying/published/conflict/failed status and publication receipt | Scoped read; saved intent does not imply published data |

Use `Idempotency-Key` for commands and explicit expected revisions. Reusing a
key for a different payload returns conflict. Validation errors are 422, stale
versions/idempotency conflicts 409, and denied operations 403; authentication
failures are 401. A missing object must not reveal another domain's data.
Every list route needs bounded cursor pagination before application integration.

## Ownership and transactional prototype

The [Postgres migration](../../app/migrations/mastering/0001_control.sql) defines
domain/mapping versions, master identity allocation, operation intents, steward
tasks/decisions and the delivery outbox. A checksummed, transactional migration
spike uses an advisory lock and rejects a changed applied migration.

Constraints enforce domain references, caller/idempotency-key uniqueness,
task lease shape, cross-domain decision isolation, append-only decisions and a
publication receipt for `published` operations. An atomic conditional update
demonstrates one winner for concurrent task claims. These database tests do not
implement the command processor, lease expiry/reclaim loop, an identity registry
API, business merge/split logic, outbox delivery or durable Delta publication.

The migration grants no application access. Database role/RLS bindings and the
authenticated app integration are still required before production use. Local
tests run in an owned temporary Postgres with TCP disabled, then stop it.

Delta remains authoritative for published source/master histories, crosswalks,
lineage and relationships. Postgres owns operational intent and concurrency.
Lakebase synced tables are read-only serving projections for application use;
the authoritative workflow tables must be owned operational tables. An outbox
and acknowledgement/reconciliation bridge the stores; there is no assumed
transaction spanning Postgres, Delta, AI Search and external delivery.

## Authorization prototype

| Role | Initial allowed business actions |
|---|---|
| Viewer | Scoped entity/provenance/task/graph/catalog reads |
| Steward | Viewer actions, task claim, decision proposal, product edit |
| Approver | Viewer actions, decision/catalog approval |
| Engineer | Viewer actions, domain configuration, mapping and bounded job execution |
| Administrator | These actions plus access management within an explicit domain |

The portable policy evaluator denies unknown actions, missing identities,
wrong domains, disallowed objects/fields and self-approval. Reads require an
explicit field projection. Grants come from a trusted server store; browser or
LLM input cannot assert roles. The function is not authentication or database
RLS. Integration must re-evaluate current policy on every data path and enforce
authorization on intermediate graph nodes, search filters and cached results.
An administrator grant for one domain does not grant access to another.

## Environment isolation plan

The original `serverless` and `serverless_native` targets intentionally share
state. New product environments use a separate bundle family and separate
resources. The following are planned names, not created resources:

| Binding | Development | Staging | Production qualification |
|---|---|---|---|
| Bundle | `lakematch-mdm-dev` | `lakematch-mdm-staging` | `lakematch-mdm-prod` |
| Workspace root suffix | `lakematch/mdm/dev` | `lakematch/mdm/staging` | `lakematch/mdm/prod` |
| UC schema | `gdpr2_catalog.lakematch_mdm_dev` | `gdpr2_catalog.lakematch_mdm_staging` | `gdpr2_catalog.lakematch_mdm_prod` |
| Lakebase project | `lakematch-mdm-dev` | `lakematch-mdm-staging` | `lakematch-mdm-prod` |
| App | `lakematch-mdm-dev` | `lakematch-mdm-staging` | `lakematch-mdm-prod` |

All initial qualification uses the explicitly selected `fevm-gdpr2` dev
workspace. These names do not establish a real production account/environment.
Workspace roots sit under the authenticated user's owned project path; bundle
state, app principals, grants, schema/volume/model names, Genie spaces and
serving endpoints must be independently bound by environment. Never copy
production grants or live user data into a development branch as a shortcut.

Use versioned migration artifacts, explicit optional resources, required tags,
finite task timeouts and independent deployment locks. Validate each target
strictly, compare resolved resource/state paths, and test restore/rollback before
promotion. Do not repurpose or delete the original campaign resources to test
this plan. A future genuine production destination needs an explicit selection.

## Capability decisions and fallbacks

- Metadata access on the selected workspace is recorded in the
  [preflight receipt](../../bench/lakefusion/preflight-20260921.json). It does not
  prove resource creation, SQL/inference, database connections or delegation.
- Local Postgres validates portable control-store assumptions. Lakebase adapter
  connections, OAuth renewal, grants and actual migration remain untested.
- AI Search is optional retrieval. Keep lexical retrieval portable; AI Search
  adoption requires measured improvement, flattened approved fields and explicit
  authorization filters. Do not assume UC row/column policy inheritance.
- Online inference needs a non-Spark feature/scorer implementation. A registered
  batch pyfunc is not accepted as an online endpoint.
- Lakebase-to-Delta CDF is a preview dependency; retain checkpointed outbox
  export/reconciliation as the baseline transport. Automatic Delta CDF requires
  eligible tables/runtime; capability-test it before use.
- The existing Genie space is a read-oriented baseline. Its recorded standalone
  answer does not prove the deployed app's on-behalf-of-user flow.

Phase A remains **In progress** until its decisions and evaluation protocol are
resolved and the capability findings have explicit accepted dependencies.
