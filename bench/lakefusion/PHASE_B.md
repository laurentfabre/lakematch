# LF-B checkpoint — updated 22 September 2026

**Phase B is in progress: 8/8 experiment slots consumed.** Phase A and LM-001 are
complete at commit `96edbf8`. LM-002–006 now provide bounded company candidate
retrieval, an approved registry, persistent identities, scalar survivorship and
immutable provenance snapshots. Existing
Spark v1 configuration and frozen replay contracts remain unchanged. A new
classifier and the corresponding app flow are pending.

## Candidate comparison

The [predeclared comparison](CANDIDATE_PLAN.md) used 4,000 ERP anchors against
4,000 CRM records in the synthetic validation partition. The corpus, generator
and split hashes were committed before the run; confirmation remains
unmaterialized. Every ERP anchor and all 4,000 known positives are included.

| Alternative | Candidate recall | Retained pairs | Raw posting visits | Truncated anchors | Positive cap losses | Local retrieval time |
|---|---:|---:|---:|---:|---:|---:|
| Identifier + jurisdiction | 65% | 3,000 | 3,000 | 0 | 0 | 0.066 s |
| Plus normalized names | 95% | 8,552 | 10,552 | 0 | 0 | 0.080 s |
| Plus lexical tokens | 100% | 190,137 | 216,687 | 1,966 | 0 | 0.614 s |
| Plus character trigrams | 100% | 200,000 | 1,326,629 | 4,000 | 0 | 2.127 s |

These are measured local retrieval times including index construction, not
serving latency or a remote scale result. All alternatives used the same limits:
50 unique candidates per ERP after union, 2m retained pairs, 20m raw posting
visits and 120 seconds. Observed process peak memory stayed below **223 MiB**
(4 GiB gate); the peak includes earlier alternatives in the same process.

The predeclared cheapest-passing selection is **identifier + normalized name**:
95% recall at 2.138 retained pairs per anchor. It misses **all 200 combined-error
positives** (missing ID + spelling/suffix change + changed address). This limitation
must remain visible; the overall gate does not establish robustness in that
stratum. The lexical union recovers those 200 positives at approximately **22.2×**
as many retained pairs and remains within every envelope. Trigrams add no recall
on this workload and increase expansion. Subsequent scorer/calibration work must
record its chosen candidate configuration and this cost/coverage trade-off before
confirmation release. No auto-merge or product promotion is implied.

The lexical methods hit per-anchor caps, so their truncation is reported explicitly.
No known positive was lost at those caps on this validation partition. Per-stratum
and method contributions, hashes and timing are in the
[compact report](candidates-validation-v0.1.json). Raw candidate receipts remain
under ignored `data/lakefusion/candidate-validation-v0.1/` with checksums in that
report and can be reproduced from the frozen source corpus.

## Verification and limits

The [run](../../experiments/20260921T125904Z-lf-b-candidate-unions-e50a8b/manifest.json)
passed its focused contract/retrieval tests and comparison. Tests cover missing-ID
recovery, provenance, cap losses, fail-closed global budgets, duplicate keys,
feature exclusions and order independence; see [JUnit](candidate-tests-v0.1.xml).
Owned-process cleanup passed. No cloud resource or AI call ran. Historical public
corpus recall has not changed, and this synthetic experiment does not qualify
general customer data, merge precision, online latency or Spark scalability.

## Next work

LM-002–006 are complete for the declared bounded internal worker contracts.
Deterministic matching/decision foundations and the first golden-record app view
remain Phase B work. The eight-slot LF-B experiment budget is exhausted; do not
start another experiment without a revised bound. Independent implementation
and documentation can continue.
Later remote/application gates listed in the Phase A freeze remain mandatory.

## Durable registry and exact job replay — 22 September

The second [LF-B experiment](../../experiments/20260921T221824Z-lf-b-registry-5fab9f/manifest.json)
passed **93 tests with no errors, failures or skips**, including 18 real PostgreSQL
integration cases. The [report](registry-20260922.json) and
[JUnit evidence](registry-tests-20260922.xml) retain exact results.

The optional PostgreSQL adapter persists immutable domain, mapping and execution
definitions, expected-version/revision checks, independent approval and append-only
history. Checksummed migration 0002 is additive; changed migrations, downgrades and
unattributed legacy approvals fail without partial application. Concurrent submits
and approvals have one winner; failed audit insertion rolls back the definition.
Approvals remain identical after an actual PostgreSQL process restart.

The bound job validates both input schemas, code and contract hashes, then
reproduces the preceding `identifier_name` candidate rows exactly: **8,552 pairs,
3,800/4,000 positives, 95% recall**. This preserves the original 200 combined-error
misses and does not tune or regenerate confirmation data. The separate seven-row
CRM preview accepts six legal companies and quarantines one branch. The explicit
v1 adapter preserves string identifiers and rejects incompatible old configs
without mutating them.

Observed main-process peak RSS was **89.2 MiB**. Local PostgreSQL 16.15 used a
private Unix socket with TCP disabled and fsync enabled; owned server/process
cleanup passed. psycopg 3.3.5 is an optional locked dependency. No cloud service or
AI call ran, and no existing database was used for resets. The full contract,
operator instructions and limitations are in [REGISTRY.md](../../spec/lakefusion/REGISTRY.md).

The separate [packaging check](registry-package-20260922.json) built the 91,488-byte
wheel, verified exact source inclusion and optional PostgreSQL metadata, and
checked portable imports with the driver unavailable. A missing Hatchling backend
in the runtime virtualenv prevented the first non-isolated build; the declared
isolated build then passed. Both build attempts are retained in that receipt.

This is an internal worker/storage capability. Actors in the evidence are
synthetic fixtures; HTTP authentication, domain grants, database RLS, Lakebase
OAuth/connection tests, publication and app integration are not claimed complete.

## Scan maintenance — 22 September

The [static/live triage](../../reports/triage-20260922/README.md) verifies the
existing review/publication retry contracts and gives a reproducible source-only
scan command. Generated source copies remain Git-ignored; the scanner snapshot
now also excludes ignored tracked files, includes pilot examples/dependencies,
and preserves previous reports. All 21 focused source/publication/app tests pass.
Workspace reads started no compute. This is LM-024 maintenance, not a new LF-B
experiment or product gate; the counter remains **2/8** and LM-004 remains next.

## Persistent identities — 22 September

LM-004 now has an optional PostgreSQL worker adapter selected through the
`persistent_uuid_v1` context. It allocates a public UUID once, enforces unique
source references, preserves immutable legacy aliases and records every command
with its before/after state. Adding an earlier-sorting source key preserves the
UUID. A merge names its survivor; a split explicitly creates a new ID or restores
the original IDs from a recorded merge. Nested merges restore in reverse order,
with current expected revisions and no silent loss of intervening changes.

The [first run](../../experiments/20260922T084351Z-lf-b-persistent-identity-6122ca/manifest.json)
passed 134 checks plus the identity lifecycle. Review found that timestamps were
serialized in the session timezone, which could reject an otherwise valid
restoration through a differently configured connection. The predeclared
[follow-up](IDENTITY_FOLLOWUP_PLAN.md) normalizes timestamps to UTC and adds
timezone, populated-schema upgrade and source-namespace checks.

The [final run](../../experiments/20260922T084732Z-lf-b-identity-upgrade-dbab23/manifest.json)
passed **138 tests, zero failures/errors/skips**, including 30 identity PostgreSQL
cases, 18 existing registry integration cases, unchanged Spark identity tests and
an actual Spark-to-legacy-alias bridge. [Final report](identity-20260922-final.json)
and [JUnit](identity-tests-20260922-final.xml) preserve the results. The earlier
[134-test report](identity-20260922.json) remains intact.

Verified behavior includes one UUID under concurrent reservations, stale/conflict
rejection, exact retries after later changes or lost acknowledgements, atomic
rollback when a process dies before commit, immutable audit/alias guards and
bounded redirect chains. A real PostgreSQL restart preserves exact current state
and all saved command receipts. Additive migration 0003 preserves valid prototype
IDs and fails atomically for merged prototype rows without a redirect; 0001/0002
checksums and all frozen Phase A files are unchanged.

The final lifecycle retained three active identities, five source references,
two legacy aliases and six events after allocate → attach → merge → restore →
new-ID split. It took **21.60 seconds** including the test suite and independent
restart probe. Main Python process peak RSS was **41.3 MiB**; this is not aggregate
Spark/Postgres memory. PostgreSQL 16.15 used a private Unix socket, TCP disabled
and fsync enabled. Both experiments cleaned up every owned process. No cloud,
AI or evaluation-corpus call ran; confirmation remains untouched.

The [worker contract and usage](../../spec/lakefusion/IDENTITY.md) describe finite
member/alias/redirect limits and the serialized writer. These operations return
`identity_applied`, not a Delta publication receipt. They do not implement HTTP
authentication, domain RLS, business approval, source deletion, golden values or
the steward UI. LM-007/008/009/011 remain open. GitHub publishing is also pending
the repository visibility decision; the work is available locally.

## Scalar survivorship — 22 September

LM-005 now calculates golden values using an immutable policy resolved through
approved domain and source mapping versions. The ordered rules select an
approved override, then verification status, source priority, quality, freshness
and deterministic source/key ties. Quality assessments and steward approvals
are explicit trusted inputs; the evidence uses synthetic actors and assessments.
It does not establish an authenticated stewardship workflow.

Missing, null, blank, disallowed and type-invalid values have separate exclusion
reasons. Source tombstones remove a source's values from consideration while
preserving identity bindings; an incomplete snapshot fails instead of guessing
a deletion. No prior golden value is carried forward. Required-value gaps,
all-deleted sources and mixed-source address components require review. Optional
fields can be explicitly cleared by an approved override. Stale identity/policy
approvals and conflicting active overrides fail visibly.

The [declared run](SURVIVORSHIP_PLAN.md) consumed slot 5 and
[passed](../../experiments/20260922T090927Z-lf-b-scalar-survivorship-c619ae/manifest.json)
**195 checks, zero failures/errors/skips**, including **55 PostgreSQL cases**.
The [report](survivorship-20260922.json) and
[JUnit](survivorship-tests-20260922.xml) retain exact evidence. Six legal companies
from twelve ERP/CRM rows reproduce the same complete calculation after database
restart; the thirteenth branch row stays outside company memberships. Memberships
come from the integration fixture's declared truth, not a new matching result.
Source update, winner deletion, the fixture's CRM deletion and an approved
override behave as declared. No public ID or identity member is deleted.

Additive migration 0004 introduces the policy registry using existing immutable
definition/audit guards. Upgrade from populated 0003, independent approval,
retirement, dependency drift and audit-event checks pass. Registry timestamps now
serialize in UTC so a session timezone change preserves the same binding receipt.
Earlier SQL migrations, frozen Phase A files and legacy Spark code are unchanged.

The run took **10.44 seconds**; main Python process peak RSS was **42.3 MiB**
(not aggregate PostgreSQL/test-process memory). PostgreSQL 16.15 used only owned
temporary storage, private Unix sockets, TCP disabled and fsync enabled. Database
and experiment process-group cleanup passed. No Spark, cloud, AI or evaluation
corpus ran; confirmation remains untouched.

The [scalar contract](../../spec/lakefusion/SURVIVORSHIP.md) bounds each master to
1,000 source members, 100 fields, 200 override decisions and 4 MiB input JSON.
Outputs include explanations, source version/hash, assessment and decision
references, policy/domain/mapping bindings and implementation/input hashes.
Durable historic provenance and publication remain LM-006/009; CDC, nested
addresses and application authorization remain their separate work packages.

## Immutable field provenance — 22 September

The [provenance contract](../../spec/lakefusion/LINEAGE.md) adds complete snapshots
of golden records, field explanations, source versions, source memberships and
domain/mapping/policy definitions. It uses the existing immutable publication
catalog and an explicit expected previous publication. Data revisions advance
independently of operational identity revisions; unchanged calculations retain
their data revision. Ruleset/configuration references and an explicit model
reference accompany the result. These fixtures use declared truth memberships
and no matching model.

Slot 6's [local run](../../experiments/20260922T093900Z-lf-b-provenance-local-56351f/manifest.json)
passed **224 checks, zero failures/errors/skips**, including 55 existing PostgreSQL
cases and 25 new provenance cases. The [local report](lineage-local-20260922.json)
and [JUnit](lineage-tests-20260922.xml) retain the evidence. Two publications each
contain **6 masters, 48 field explanations, 12 source versions, 12 memberships
and one complete contract definition**. Earlier field values remain explainable
after the address update, CRM tombstone and independently approved name override.

Checks include concurrent publication, process death during projection writes,
old-batch retries without head rewind, stale heads, source-version rollback,
changed content under a reused version, missing approvals, incomplete projection
integrity, review-required results and the absence of side effects on reads.
Historical reads succeed when the current survivorship function is deliberately
unavailable. A new worker and an actual PostgreSQL restart preserve the original
local snapshots and identity/data revision distinction.

The local run took **12.825 seconds**, with **44.3 MiB** observed main-process
peak RSS (not aggregate PostgreSQL/test-process memory). Owned PostgreSQL and
temporary publication storage were removed. Frozen Phase A content remains
unchanged; no evaluation corpus, confirmation data or AI endpoint was accessed.
The exact synthetic remote fixture is reproducible by the runner, stored under
ignored `data/lakefusion/`, and checksummed in the report.

Limits are 100 masters, 2,000 source versions, 10,000 field rows and 32 MiB per
snapshot. The entity-detail reader is an internal bounded service. Application
authorization, scalable query routes, operational watermark rechecks, outbox
delivery and Postgres/Delta command reconciliation remain LM-007/008/009/010 work.

Slot 7's [serverless run](../../experiments/20260922T094201Z-lf-b-provenance-delta-00774a/manifest.json)
also passed. [Workspace evidence](lineage-remote-20260922.json) records job run
`397340405198492` and task `967668840508116` on `fevm-gdpr2`. Both Delta snapshot
hashes exactly match the local artifacts. After deliberately interrupting a write
following its first table, readers still see the earlier complete publication;
the next successful write removes that abandoned table. New reader instances
resolve original field/source/override evidence, and retrying the old batch does
not move the head backward.

The first remote proof took **275.814 seconds** inside the notebook, after a
**216-second** serverless startup; the bounded outer run took **519.51 seconds**.
It removed all **11** owned final tables and its workspace directory, with no
remaining tables or cleanup errors. Billing is **unreconciled**, not zero. No
existing demo table, app, bundle deployment, permanent job or warehouse changed.

Review identified a stricter upgrade case: the adapters recomputed calculations
before resolving a committed duplicate. The [last-slot follow-up](LINEAGE_RETRY_PLAN.md)
moves full replay into the new-publication builder, retaining structural/integrity
checks before catalog lookup. The [final local report](lineage-local-20260922-final.json)
passes **225 checks** in **11.483 seconds**, at **46.1 MiB** main-process peak RSS.
It verifies that a committed retry works with the current calculator unavailable,
while a new batch still fails until its calculation can be reproduced. The
follow-up's [final remote proof](lineage-remote-20260922-final.json) also passes;
previous reports remain unchanged.

The final [experiment](../../experiments/20260922T095127Z-lf-b-provenance-retry-c09f7c/manifest.json)
consumed slot **8/8**. Serverless job `823127979502708`, task `397745388413974`,
repeated local/Delta hash parity, historic reads, partial-write isolation and
abandoned-table recovery using the final source. It additionally retried the
committed first publication while the current scalar implementation was disabled,
then proved that a new publication was refused under the same condition.
The final notebook took **290.085 seconds** after a **136-second** startup; the
combined local/remote experiment took **468.60 seconds**. Its 11 final tables and
workspace files were removed with no remaining resources or cleanup errors.

LM-006 is complete for this bounded internal service. LM-009 has a tested first
publication foundation but remains in progress for operational outbox and command
reconciliation. LM-014 matching/decision foundations and the golden-record UI
remain Phase B work. This exhausts the phase's experiment cap; further experiments
need a revised bound. Final-source hashes and all frozen Phase A files are
verified. GitHub publishing remains pending the repository visibility decision.

## LM-014 foundations and first APX preview — 2026-09-22

Development continued under the exhausted experiment cap, following the
[bounded development plan](MATCH_EVIDENCE_PLAN.md). **No new experiment ran;
LF-B remains 8/8.** LM-014 is now in progress. The Phase B checkboxes remain open
pending calibrated bands and the next authorized acceptance run.

The [comparison contract](../../spec/lakefusion/MATCH_EVIDENCE.md) pins domain,
mapping, normalization, Unicode and implementation versions. It preserves actual
mapped values, absent/invalid states, field agreements, source hashes and rule
precedence. Identifier conflicts, incompatible granularity and self-comparison
are explicit. Eligible suggestions route to review and expose no probability or
automatic-merge authority. This is separate from the v1 engine; rule registry
approval, model/calibrator integration, quality evidence and comparison UI
integration remain open.

The APX **Golden records** tab uses a packaged export of the existing synthetic
fixture and provenance transforms. It displays six companies, two publications,
all eight fields per company, source alternatives, approved name edits, deleted
sources and policy/publication references. The app reads bounded JSON under
`/api/demo/`; it never imports the Python 3.12 engine into the Python 3.11 app.
The synthetic demo has no customer-data adapter and does not fetch or seed the
review store. It is not a completed LM-010 workflow or a live-authorization gate.

Observed development checks:

- **206 portable checks pass**, including 36 new comparison cases and existing
  mastering/publication/configuration/hygiene compatibility.
- **19 app checks pass**, including six demo API/packaging cases. An initial
  assertion used the wrong fixture company name; its expectation was corrected.
- APX Python/TypeScript checks and the pinned production build pass. APX's check
  command refreshed two router-development dependency pins; those incidental
  changes were restored, and final direct type checks use the original lockfile.
  Four deployment files, largest **156,717 bytes**; synthetic JSON is in the wheel.
- [Final desktop/mobile preview](../../reports/lakefusion-ui-20260922-final/README.md)
  passes with no page errors or horizontal overflow, showing an earlier
  publication and source deletion. The initial selector-label failure is retained.
  Owned preview servers and temporary databases were cleaned up.
- All **15 frozen Phase A files** retain their checksums. No model training,
  development/validation corpus evaluation, confirmation materialization, AI
  call, remote experiment or workspace deployment occurred.

These checks support a development increment, not calibrated quality, a remote
acceptance result or phase closure. The [proposed four-slot extension](NEXT_EXPERIMENTS.md)
is pending authorization. GitHub still reports `laurentfabre/lakematch` as public;
publishing remains pending the §2 private-repository requirement's resolution.
