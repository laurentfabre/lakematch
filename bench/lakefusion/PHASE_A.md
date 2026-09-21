# LF-A execution checkpoint — 21 September 2026

**Phase A is in progress.** The user requested execution of `goal_lakefusion.md`.
Its additional source/distribution/AI/protocol decisions are pending. The
[pilot contract](../../spec/lakefusion/PHASE_A.md) and
[evaluation protocol](../../spec/lakefusion/PROTOCOL.md) are concrete drafts;
neither a quality evaluation nor a product phase has been declared passed.

## Delivered and verified

| Work | Observed result | Evidence |
|---|---|---|
| Typed domain/mapping prototype | Strict scalar types, required fields, schema drift checks, immutable definition binding and deterministic mapping receipts | [Contracts](../../src/lakematch/mastering/contracts.py), [tests](../../tests/test_mastering_contracts.py) |
| Two-source proposal | 13 synthetic source rows, six legal companies, one branch, conflicting values, hierarchy, collision and mutation scenarios | [Fixture and canonical hashes](../../examples/mastering/company_pilot/manifest.json) |
| Policy prototype | Explicit domain/object/field grants, default deny, role separation, independent approval and uncached revocation evaluation | [Policy](../../src/lakematch/mastering/policy.py), [tests](../../tests/test_mastering_policy.py) |
| Final local checks | **37 tests passed**, no failures/errors/skips: 35 contract/policy tests plus two existing source-hygiene checks | [JUnit](contracts-tests-final.xml), [run receipt](../../experiments/20260921T115557Z-lf-a-contracts-final-8f72e0/manifest.json) |
| Local PostgreSQL 16.15 spike | **12 checks passed**: migration retry/checksum, FK binding, one concurrent claim winner, stale revision rejection, rollback, uniqueness, transactional outbox, domain isolation, immutable decisions, required/nonblank publication receipt | [Final result](postgres-spike-final-20260921.json), [run receipt](../../experiments/20260921T115851Z-lf-a-postgres-final-eca0c7/manifest.json) |
| Workspace preflight | **Eight metadata reads passed** on explicitly selected `fevm-gdpr2`; no resource mutations | [Result](preflight-20260921.json), [run receipt](../../experiments/20260921T114652Z-lf-a-metadata-9262ad/manifest.json) |
| Environment preparation | Separate planned bundle roots, UC schemas, Lakebase projects, app identities and bindings; existing bundles unchanged | [Isolation plan](../../spec/lakefusion/PHASE_A.md#environment-isolation-plan) |

The local commit gate now runs contract/policy tests when their implementation,
tests or fixture changes. No mandatory engine dependency was added. These
prototypes are separate from the current pair-review app and v1 matching engine.

## Workspace evidence boundaries

Authentication and metadata reads succeeded for Lakebase projects, AI Search
endpoints, model-serving endpoints, the existing app, owned warehouse, Genie
space and campaign schema. List calls were limited to one resource and retained
only counts; no other application's resources were modified or exercised.

The owned app and warehouse were **STOPPED**. The warehouse metadata reports
`enable_serverless_compute=true`, `warehouse_type=PRO` and ten-minute auto-stop;
the PRO value alone does not imply classic compute. The app response did not
report token forwarding; the existing bundle disables it. Delegated app
authorization remains untested.

Metadata listing does not prove creation rights, Lakebase database connections,
SQL execution, model inference, index retrieval or on-behalf-of-user Genie.
The original [redeployment audit](../REDEPLOYMENT.md) and
[corpus replays](../../reports/test-runs/20260921T092956Z/README.md) remain prior
evidence; they were not rerun or used for tuning in this checkpoint.

## Retained failure and cleanup

The [first unit run](../../experiments/20260921T115056Z-lf-a-contracts-2974ce/manifest.json)
passed its then-current 33 assertions, but the experiment runner could not run
`ps` inside the sandbox. It correctly remained **failed**, with cleanup evidence
pending. The expanded final run used the needed process-list visibility and
passed all 37 tests with owned-process cleanup verified. No failure receipt was
rewritten and the first test report remains [available](contracts-tests.xml).
A separate [cleanup follow-up](initial-cleanup-followup.json) verifies that the
original failed runner's process group has no live members; its failure receipt
remains unchanged.

The temporary PostgreSQL server accepted only a private Unix socket, used its
own temporary data directory and stopped successfully. No SQL warehouse, cloud
app, Lakebase project, index or serving endpoint was started or created. The
user-facing demo from the earlier task was not touched.

Five bounded experiment receipts count against LF-A's eight-iteration envelope:
metadata, initial unit/cleanup failure, initial Postgres, final unit checks, and
final Postgres constraints/overlapping-claim checks. The [initial 11-check result](postgres-spike-20260921.json) remains intact. No matching
quality comparison, confirmation scoring or old ZR-cap reset occurred.

## Remaining work

Resolve the four explicit decisions in `goal_lakefusion.md` §1. The proposals are
synthetic ERP/CRM sources with legal-company masters, internal distribution,
optional AI disabled for the pilot, and the draft evaluation protocol. Then
record a versioned decision/freeze receipt and decide the required next capability
spikes from the verified metadata and local database results.

LM-001/003/007/008/024 have groundwork in progress. Their full application
contracts, authenticated APIs, durable registry/workflow adapters, RLS bindings,
remote database acceptance and isolated deployments remain incomplete. Phase B
does not start on an assumed answer to the pending business decisions.
