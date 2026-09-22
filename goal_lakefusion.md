# Goal: deliver governed MDM, relationship graphs and PIM in Lakematch

Created: **2026-09-21**. Status: **LF-A complete; LF-B in progress (8/12 experiments)**.
Research baseline: **`a007166`**. Phase IDs: **LF-A through LF-F**.

Deliver the capabilities defined in the
[LakeFusion assessment](spec/research/lakefusion/README.md) and
[implementation design](spec/research/lakefusion/IMPLEMENTATION.md): a governed
master-data application with persistent identities, explainable golden records,
concurrent stewardship, incremental processing, online resolution, business
relationships, product catalogs and reliable deployment.

This file is the execution and acceptance ledger for the new product roadmap.
It contains all six delivery phases and all 25 work packages from the
[backlog](spec/research/lakefusion/backlog.csv). Execution was requested on
2026-09-21; the [Phase A checkpoint](bench/lakefusion/PHASE_A.md) records the
delivered prototypes, measured evidence and dependency decisions. Resume with:

```text
$goal ./goal_lakefusion.md
```

A section selector narrows work while retaining dependencies; for example,
`$goal ./goal_lakefusion.md 4` selects Phase A. The selector is the section
number, which maps to phases as **§4→LF-A, §5→LF-B, §6→LF-C, §7→LF-D, §8→LF-E,
§9→LF-F** (§1–3 and §10–11 are always in scope as context). The original
[goal.md](goal.md) remains authoritative for the ZR campaign and its existing
results and limits.

## § 1 — Outcome and scope

The first release is a company/supplier MDM pilot using synthetic ERP vendor
records and CRM accounts, with one master per legal company. It must explain every published field, distribute review work,
apply approved edits and reversible identity changes, and recover from partial
failures. Later releases add online access, relationship intelligence and PIM.

Required functional scope:

- Versioned domains, source mappings, onboarding, quality checks and remediation.
- Bounded candidate retrieval; deterministic rules, calibrated matching and
  evidence; an optional LLM adapter with abstention and measured benefit.
- Persistent master IDs, aliases, source crosswalks, scalar/nested survivorship,
  reference data and winning-value provenance.
- Concurrent steward tasks, roles, approvals, overrides, merge/split/unmerge,
  immutable decisions and recoverable publication.
- Incremental source changes/deletes, online search-before-create, typed
  relationships, hierarchies and bounded graph exploration.
- MCP tools and delegated Genie access over authorized data.
- PIM families/variants/SKUs, taxonomies/crosswalks, assets, locale/channel values,
  completeness, editorial review, catalog releases and controlled delivery.
- Isolated environments, operational metrics, job controls, a constrained
  pipeline editor, graph alerts/actions, migrations, recovery and user help.

Deliver this as a **customer-deployable Solution Accelerator and SA demo kit**.
Customer installation, sample data, demo/reset scripts and qualification remain
required in Phase F/LM-024. Commercial licensing, marketplace distribution and
entitlements (LM-025) are not applicable to the selected scope. See the
[decision record](spec/lakefusion/DECISIONS.md).
Licensed enrichment connectors require a concrete source
and usage rights before activation. Optional AI integrations must have tested
enabled and disabled contracts; a paid-feature flag alone is not implementation.

The [source register](spec/research/lakefusion/SOURCES.md) distinguishes vendor
claims from platform documentation and repository evidence. The finish line is
the explicit acceptance contract below. Advertised vendor speed, scale or cost
figures are not Lakematch results or automatic acceptance thresholds.

**Decisions required before Phase A can close — all resolved.** Recorded user
selections for LM-001:

- **Resolved:** synthetic ERP vendor records plus CRM accounts; legal-company
  masters with branches/families modelled separately (LF-DEC-001).
- **Resolved:** customer Solution Accelerator and SA demo kit. LM-025 is not
  applicable; customer deployment packaging stays required in LM-024 (LF-DEC-002).
- **Resolved:** use AI via Unity Gateway (LF-DEC-003). Enabled, disabled and
  failure contracts and quality gates remain required before product promotion.
- **Resolved:** protocol v0.1 as drafted (LF-DEC-004): 40,000 synthetic source
  rows, whole-family 60/20/20 splits, finite budgets and resource/run cost
  attribution. The explicit Unity Gateway choice supersedes the draft's
  disabled-AI proposal; numerical gates are unchanged.

## § 2 — Architecture and execution context

- Retain **APX 0.3.8, React and FastAPI**. Preserve the independent Apache-2.0
  Spark engine, portable local execution and separate optional integrations.
- Delta/Unity Catalog owns versioned source data and published master records,
  memberships, relationships and analytic audit history. Lakebase/Postgres owns
  operational commands, task leases, approvals, ID allocation and PIM drafts.
  Serving projections are rebuildable and carry publication/freshness metadata.
- Use real transactional constraints for workflow uniqueness. Synced Lakebase
  tables are serving projections, with their documented permission restrictions;
  they are not the operational write store. Keep the existing immutable-snapshot
  publisher until a measured migration justifies changing its contract.
- Keep the existing v1 engine configuration, historical model artifacts, label
  receipts, benchmark IDs and sealed replays readable through explicit adapters.
- Use only public or synthetic corpora. Publish completed work to the public
  `laurentfabre/lakematch` repository under [LF-DEC-006](spec/lakefusion/EXECUTION_DECISIONS.md).
  Do not copy LakeFusion implementation assets or incompatible third-party source.
- Laurent already selected **`fevm-gdpr2`** in this conversation. Pass
  `--profile fevm-gdpr2` to workspace CLI commands and configure SDK clients
  explicitly. Do not substitute a different profile. Load `databricks-core`
  and the relevant product skills before remote operations.
- The earlier dev-workspace quota/expiry prerequisite was waived. Keep finite
  resource/time envelopes, measured consumption and cleanup. Capability checks
  still apply to Lakebase, Apps authorization, AI Search, serving and previews.
- The original million-record campaign remains parked at its iteration cap;
  classic compute was unavailable in this workspace. This goal does not reset
  those limits, reopen sealed confirmation tuning or authorize another workspace.
  Keep the original ZR gates visible where new work depends on them.

## § 3 — Phase and work-package ledger

All statuses start at **Not started**. A foundation can be delivered in an earlier
phase without closing its full work package. Close a package only when all its
acceptance criteria pass; update the CSV status as a projection of this ledger.
The backlog retains the detailed package dependencies and code-area mapping.

Two reconciliation rules keep this ledger and the backlog consistent:

- **Status vocabulary.** This ledger's `Not started` / `In progress` / `Done`
  map to the CSV's `proposed_not_started` / `in_progress` / `done`; the ledger's
  `Conditional; not started` maps to CSV `conditional`; `Not applicable` maps
  to CSV `not_applicable`. LM-025 is not applicable under LF-DEC-002.
- **Phase columns.** The backlog `stage` is the **work span** across which a
  package is active (e.g. `A-B`); this ledger's `Completion phase` is the phase
  in which the package **closes** (e.g. `LF-B`). A span that starts earlier than
  its completion phase is expected wherever a foundation is delivered ahead of
  closure (LM-004, LM-007, LM-009, LM-014, LM-016, LM-024).

| Phase | Deliverable | Entry dependency | Indicative timing | Status | Acceptance evidence |
|---|---|---|---|---|---|
| LF-A | Contracts, evaluation plan and feasibility | Execution requested | Weeks 1–2 | Done | [Frozen contracts, capability evidence and limits](bench/lakefusion/PHASE_A.md) |
| LF-B | Matching foundations and explainable golden records | LF-A; workflow schema needed for ID allocation | Weeks 3–6 | In progress | [Candidates, identity, survivorship and published provenance](bench/lakefusion/PHASE_B.md) |
| LF-C | Governed two-source MDM pilot | LF-B; authorization and workflow foundations | Weeks 7–12, plus 4 weeks contingency | Not started | None yet |
| LF-D | Online resolution, relationships, graph and agent access | LF-C; individual package prerequisites | Weeks 13–20 | Not started | None yet |
| LF-E | PIM catalog and editorial workflows | LF-C plus LF-D reference/nested contracts | Weeks 19–30 | Not started | None yet |
| LF-F | Production qualification and release | Relevant phase implementations; qualification starts earlier | Through months 6–9 | Not started | None yet |

Timing is a planning estimate: roughly 4–5 engineers for the pilot and 5–7 plus
QA for the broader product. Work can overlap once its prerequisites are met;
dates do not waive acceptance gates. Re-estimate after Phase A.

| Package | Work | Completion phase | Status |
|---|---|---|---|
| LM-001 | Pilot contract and capability checks | LF-A | Done |
| LM-002 | Candidate coverage | LF-B | Done |
| LM-003 | Domain and mapping registry | LF-B | Done |
| LM-004 | Persistent business identity | LF-B | Done |
| LM-005 | Scalar survivorship | LF-B | Done |
| LM-006 | Winning-value provenance | LF-B | Done |
| LM-007 | Transactional workflow adapter | LF-C; allocation foundation in LF-B | In progress |
| LM-008 | Domain and action authorization | LF-C; extended checks in LF-D/E | In progress |
| LM-009 | Command publication and recovery | LF-C; first publication in LF-B | In progress |
| LM-010 | Entity explorer and steward inbox | LF-C | Not started |
| LM-011 | Governed edits and reversible merge/split | LF-C | Not started |
| LM-012 | Onboarding and quality remediation | LF-C | Not started |
| LM-013 | Incremental mastering | LF-C | Not started |
| LM-014 | Calibrated decisions and explanations | LF-D; pilot decisions in LF-C | In progress |
| LM-015 | Selective LLM adjudication | LF-D; activation optional | Not started |
| LM-016 | Reference entities and nested structures | LF-D; foundation in LF-C | Not started |
| LM-017 | Search-before-create and online scoring | LF-D | Not started |
| LM-018 | Business relationships and hierarchies | LF-D | Not started |
| LM-019 | Interactive graph serving | LF-D | Not started |
| LM-020 | MCP and delegated Genie | LF-D | Not started |
| LM-021 | PIM catalog and editorial core | LF-E | Not started |
| LM-022 | Taxonomy crosswalks | LF-E | Not started |
| LM-023 | Media, enrichment and channel delivery | LF-E | Not started |
| LM-024 | Environment separation and operational qualification | LF-F; milestones in every phase | In progress |
| LM-025 | Commercial distribution and entitlements | LF-F; excluded under LF-DEC-002 | Not applicable |

## § 4 — Phase A: contracts and feasibility

**Packages:** LM-001; initial LM-002/003/007/008/024 work.

Deliverables:

- [x] Define the company/supplier domain, distinguishing legal company, branch
  and corporate family; select two source schemas and representative tasks.
  [Sources and legal-company granularity selected](spec/lakefusion/DECISIONS.md).
- [x] Freeze domain/mapping contracts, role/action matrix and first API/table
  definitions using the implementation design's ownership boundaries.
  [Versioned freeze receipt](spec/lakefusion/frozen/phase-a-v0.1.json).
- [x] Prepare a synthetic vertical-slice fixture with conflicting addresses,
  parent-child relationships, an identifier collision and merge/split history.
  [Thirteen-row integration fixture](examples/mastering/company_pilot/README.md)
  uses the selected sources; mutation scenarios are specified, not yet executed.
- [x] Declare development/validation/untouched evaluation splits and candidate,
  join, memory, time and experiment budgets before comparing methods.
  [Generator contract](spec/lakefusion/GENERATOR.md) and
  [prepared-source manifest](bench/lakefusion/company-pilot-v0.1.json);
  32,000 source rows materialized, 8,000 confirmation rows withheld.
- [x] Record the local baseline and reusability of prior evidence. Probe the
  selected workspace's needed capabilities with bounded checks and explicit
  supported/unsupported/untested results.
  [Eight metadata checks and capability limits](bench/lakefusion/PHASE_A.md).
- [x] Design genuinely isolated bundle state/resources for each environment;
  establish operational schema/migration and authorization prototypes.
  [Draft isolation/API/role contract](spec/lakefusion/PHASE_A.md); 12 Postgres
  checks and 37 final local tests pass. Application/remote integration is pending.
- [x] Freeze the initial workload, quality/latency/freshness targets and cost
  measurement method. Record preview dependencies and fallback adapters.
  [Approved protocol v0.1](spec/lakefusion/PROTOCOL.md); all four user decisions
  resolved. Gateway inference passes as the selected user; app identity, quality
  benefit and billing reconciliation remain unproved. LF-A used **8/8** slots.

**Exit gate:** LM-001 has a versioned contract, evaluation protocol, capability
matrix, dependency decisions and resource envelope. Every later gate has a
measurement method. An unavailable remote capability is recorded precisely;
independent local work remains eligible. A capability listing is not proof that
an application flow works.

## § 5 — Phase B: matching and golden records

**Packages:** LM-002 through LM-006; LM-007 allocation foundation;
initial LM-009/014/024 work. **Depends on:** Phase A.

Deliverables:

- [x] Improve domain normalization and complementary candidate unions; record
  retrieval method, recall losses and cap/top-k truncation at equal budgets.
  [Four-alternative validation comparison](bench/lakefusion/PHASE_B.md): 65%
  identifier baseline, 95% with normalized names, 100% with lexical tokens.
  Cheapest passing configuration misses all 200 combined-error pairs; lexical
  coverage costs 22.2× more pairs but stays inside caps. The selected method now
  replays exactly through a versioned registry binding. Automatic-merge quality
  remains incomplete; confirmation is untouched.
- [x] Implement approved domain/source-mapping versions with drift detection
  and explicit compatibility with existing engine configurations.
  [Operational registry and execution contract](spec/lakefusion/REGISTRY.md):
  immutable definitions, approval/revision history, bounded mapping preview,
  pinned candidate jobs and an explicit v1 feature-row adapter. **93 tests pass**,
  including 18 PostgreSQL integration cases and actual restart persistence.
  Lakebase OAuth/RLS and authenticated app APIs remain later gates.
- [x] Allocate persistent business IDs transactionally. Add aliases and
  identity-event history; retain historical deterministic ID interpretation.
  [Persistent identity policy](spec/lakefusion/IDENTITY.md) and
  [final evidence](bench/lakefusion/identity-20260922-final.json): 138 checks pass,
  including 30 identity PostgreSQL cases and a bridge using actual legacy Spark
  IDs. Explicit survivor, new-ID split, exact merge restoration, concurrency,
  process-death rollback, UTC receipts, upgrade and restart persistence verified.
  This is an internal worker adapter; application approval, authorization and
  publication remain LM-007/008/009/011 work. LF-B now uses 4/8 slots.
- [x] Implement scalar survivorship with steward override, source precedence,
  quality/freshness, null semantics and deterministic tie-breaking.
  [Versioned scalar policy](spec/lakefusion/SURVIVORSHIP.md) and
  [bounded evidence](bench/lakefusion/survivorship-20260922.json): **195 checks
  pass**, including 55 PostgreSQL cases. Six synthetic companies replay exactly
  after restart; source updates/deletes, invalid values, overrides, policy
  approval and migration from populated 0003 pass. Mixed address sources require
  review. This calculates records from trusted snapshots; workflow approval,
  CDC and durable publication are later gates. LF-B now uses **5/8** slots.
- [x] Publish field-level winning-value provenance and source crosswalks in
  versioned snapshots, including rule/model/configuration references.
  [Immutable provenance contract](spec/lakefusion/LINEAGE.md): **225 final local
  checks** and [live Delta acceptance](bench/lakefusion/lineage-remote-20260922-final.json)
  pass. Two publications each retain six masters, 48 field explanations and
  twelve source versions/crosswalks. Historical reads, interrupted-write isolation,
  source updates/deletes, overrides and retries across implementation changes
  pass; local/Delta snapshot hashes match. Temporary tables/workspace files were
  removed. Matching uses declared fixture memberships, with no model; operational
  watermark rechecks, authorization, outbox delivery and UI remain open. LF-B
  used all eight originally authorized slots. The approved extension now sets
  the current count to **8/12** under LF-DEC-005.
- [ ] Version deterministic match rules, develop calibrated decision bands,
  and show actual field comparisons before adding model-specific explanations.
  [Worker comparison foundation](spec/lakefusion/MATCH_EVIDENCE.md) implemented:
  36 new portable checks pass, with pinned rules and actual values. All eligible
  suggestions require review. The [probability/band foundation](spec/lakefusion/PROBABILITY.md)
  adds explicit transforms, metadata bindings, conflict vetoes and diagnostic
  helpers. The [synthetic comparison UI](reports/lakefusion-comparison-ui-20260922/README.md)
  now displays actual/normalized values, conflicts and exclusions for twelve
  source pairs, with explicit origin and no model score. **301 portable and 25
  app checks pass**; type/build and desktop/mobile development checks pass.
  Empirical calibration, registry promotion, live comparison integration and
  matching-quality acceptance remain open. LF-B currently uses **8/12** slots.
- [ ] Deliver the first APX golden-record detail view using the synthetic slice.
  [Local APX preview](reports/lakefusion-comparison-ui-20260922/README.md) implemented:
  six companies, two publications, field alternatives, overrides and deleted
  sources. App/type/build and desktop/mobile development checks pass. The next
  full acceptance run is authorized as slot 9 under the approved extension;
  no acceptance result has been recorded yet.

**Exit gate:** two-source inputs reproduce the same golden records and provenance
on retry. Earlier-sorting source keys do not rekey public IDs. Every selected
value resolves to source versions and a policy/override. Candidate coverage meets
the frozen Phase A gate, with losses and budgets reported separately from scoring.
Existing frozen replay contracts remain intact. Complete LM-002–006 and record
the remaining operational work for LM-007/009/014.

## § 6 — Phase C: governed MDM pilot

**Packages:** LM-007 through LM-013; pilot LM-014, reference foundation LM-016,
and LM-024. **Depends on:** Phase B and the authorization/workflow foundations.

Deliverables:

- [ ] Implement Postgres/Lakebase tasks, leases, optimistic revisions,
  immutable decisions and idempotent commands; preserve existing label receipts.
- [ ] Enforce Viewer/Steward/Approver/Engineer/Administrator permissions with
  domain/object/action scopes and separation of proposal/approval where required.
- [ ] Add paginated entity search, task inbox, provenance, history and visible
  pending/approved/applying/published/conflict/failed operation states.
- [ ] Implement preview/propose/approve/apply for overrides and merge/split;
  reconcile reversal against subsequent edits and downstream references.
- [ ] Connect workflow outbox events to recoverable immutable publication and
  analytic audit export; reconcile lost acknowledgements without double-apply.
- [ ] Add source import/mapping preview, quality profiles, quarantine ownership
  and corrected-row resubmission. AI mapping suggestions require explicit review.
- [ ] Handle inserts, updates, deletes and late events; recompute affected
  matching neighborhoods and recover from change-history gaps with a full rebuild.
- [ ] Exercise the real app-to-review-to-training-to-publication path and restart
  persistence in the selected workspace under a separately declared run plan.
- [ ] Demonstrate isolated pilot deployment, schema migrations and restoration.

**Exit gate:** business users can complete the two-source MDM workflow. Concurrent
claims have one winner; stale decisions conflict; retries and crashes cannot
double-apply changes. Merge followed by split follows the recorded identity
policy. Incremental results agree with a full rebuild for the declared mutation
cases. Role denials and revocation hold across reads, writes and caches. Pilot
auto-merge quality passes its frozen gate and the local/remote receipts identify
the tested source revision. An unresolved required remote gate keeps the pilot
incomplete even if local tests pass.

## § 7 — Phase D: online access and relationship intelligence

**Packages:** finish LM-014; LM-015 through LM-020; graph operations in LM-024.
**Depends on:** Phase C. Package-level work may overlap after prerequisites pass.

Deliverables:

- [ ] Complete calibration, decision-band and explanation contracts; validate
  model-specific SHAP output/background compatibility where enabled.
- [ ] Implement optional structured LLM adjudication for uncertain pairs with
  abstention, versioned caching, latency/cost evidence and human fallback.
- [ ] Complete governed reference entities, dependent values, typed nested
  records and array survivorship that preserves structured tuples.
- [ ] Implement a measured non-Spark online feature/scorer path and governed
  candidate lookup. Return evidence, revision, freshness and explicit outcomes.
- [ ] Separate search from creation: use an idempotent create command, exact-key
  reservations and stewardship for ambiguous concurrent fuzzy duplicates.
- [ ] Add typed, effective-dated business relationships and hierarchies with
  domain, direction, cardinality and cycle rules.
- [ ] Add indexed adjacency projections and bounded graph traversal with
  explicit hop/node/edge/time limits, truncation and policy-aware caches.
- [ ] Expose narrow MCP tools over shared services; mutation tools propose
  governed operations. Demonstrate delegated Genie over approved master views.
  The ZR-8 Genie Agent already created on `fevm-gdpr2` (space
  `01f1b55eb48a1c0bae6f117fbdbc064e`, over `gdpr2_catalog.lakematch_20260919`
  gold tables; see [goal.md](goal.md) ZR-8) is the baseline to extend from — it
  proves the Conversation API answers as the user, but not yet on-behalf-of-user
  from the deployed app, which this package must establish.
- [ ] Add scheduled graph rules, deduplicated alerts and approved downstream
  actions using an outbox and visible delivery status.

**Exit gate:** online and graph workloads meet the frozen Phase A targets, with
warm/cold latency and freshness reported. Claimed batch/online parity is measured;
no request starts Spark as its online scoring strategy. Intermediate graph nodes,
edges and cached results enforce authorization. Reference/nested values remain
valid and explainable. MCP obeys the same policy as the UI; the deployed app
demonstrates the complete delegated Genie reference suite. Optional LLM activation
requires measured marginal benefit, validated error handling and the configured
provider boundary; disabled mode remains functional. Unsupported required
delegation remains an explicit dependency, not a passing smoke test.

## § 8 — Phase E: PIM and editorial workflows

**Packages:** LM-021 through LM-023, with LM-024 operations.
**Depends on:** Phase C and completed reference/nested contracts from Phase D.

Deliverables:

- [ ] Define separate product family, variant and SKU identities; add typed
  attributes, specifications, units, requiredness and inheritance rules.
- [ ] Implement import preview, bulk edits, category-specific completeness,
  working/live catalogs and immutable release manifests.
- [ ] Version taxonomies and reviewed crosswalks. Preview affected products,
  propagated values, cycles and editorial conflicts before applying a change.
- [ ] Store governed asset references with checksums, rights/provenance and
  approval state; support locale/channel values and visible fallback rules.
- [ ] Add optional copy/translation/enrichment proposals with source evidence,
  factual review and approval; do not present generated values as source facts.
- [ ] Publish approved releases through explicit channel connector contracts
  with idempotent delivery, retries and operator-visible failures.
- [ ] Extend domain roles, audit views, accessible UI and recovery tests to PIM.

**Exit gate:** a representative product collection passes import → enrich/edit →
classify in two taxonomies → review → publish to a test channel. Only approved,
type-valid content is live. Locale fallback and taxonomy conflicts are visible;
retries do not duplicate deliveries. Historic releases are reproducible and
source/asset provenance remains inspectable after later edits.

## § 9 — Phase F: production qualification and release

**Packages:** finish LM-024; LM-025 not applicable under LF-DEC-002.
**Depends on:** the required Phase A–E capabilities. Qualification work starts
earlier and is repeated only when relevant changes invalidate evidence.

Deliverables:

- [ ] Provision isolated development/staging/production state, catalogs/schemas,
  service bindings and deployment identities appropriate to the selected scope.
- [ ] Make clean install, redeploy, migration, upgrade, rollback and restoration
  reproducible from the public repository and durable versioned artifacts.
- [ ] Package a customer Solution Accelerator with explicit workspace/profile,
  catalog/schema and resource bindings, prerequisite/permission checks, sample
  data and deployment/run/reset/cleanup instructions. Provide SA demo scripts and
  scenarios; verify a fresh install without Laurent's existing resource IDs.
- [ ] Finish approved job templates, status/log/cancel/retry controls and a
  constrained visual pipeline editor that emits validated job definitions.
- [ ] Qualify target workloads, bounded degradation, concurrency, permission
  revocation, projection lag, model/rule promotion and channel recovery.
- [ ] Publish measured quality, latency, capacity and cost with limitations;
  document operational ownership, troubleshooting, API/schema contracts and help.
- [ ] Deliver a nontechnical guide with workflow diagrams, measured statistics,
  application screenshots and PDF export for the released behavior.
- [ ] Reconcile all phase/package statuses against final-source evidence;
  retain failed results and clean up owned experimental resources.
- [x] Resolve LM-025: **Not applicable — customer Solution Accelerator and SA
  demo distribution**, selected in LF-DEC-002. Customer installation and release
  qualification remain required above; this is a scope disposition, not a
  completed commercial capability.

**Exit gate:** all required phase gates pass for the released configuration;
restoration and redeployment use the documented source and artifacts; user and
operator flows are demonstrated end to end. Optional/unavailable integrations
and commercial packaging status are stated explicitly. No complete feature-parity,
scale, SLA or cost claim exceeds the measured evidence.

## § 10 — Evaluation and shared acceptance contract

The following targets and workload are approved in protocol v0.1 (LF-DEC-004).
The Phase A freeze records sampling and measurement definitions before optimization. They
are not achieved results; changes require a recorded rationale and must not
retroactively convert a failed run into a pass.

| Area | Proposed gate | Measurement requirements |
|---|---|---|
| Retrieval | Candidate recall ≥95% on each chosen pilot validation task | Fixed truth/splits; candidate/join budgets; cap/truncation losses; no averaging away a failing domain |
| Auto-merge | Lower one-sided 95% precision confidence bound ≥99.5% | Representative labelled decisions; coverage and false negatives; grouping for dependent pairs |
| Online resolve | Warm p95 <1 second at 100,000 masters and 20 requests/second | Fixed request mix, index/configuration and error rate; cold starts separately |
| Graph | Warm p95 bounded 3-hop <2 seconds at 100,000 nodes/1 million edges and 10 requests/second | 10,000 visited-node and 2,000 returned-edge caps; degree distribution, truncation, cold starts and error rate |
| Serving freshness | p95 <60 seconds at the declared pilot input rate | Source-to-serving watermark; lag visible; authoritative recheck before creation/merge |
| Mutation correctness | No double application, silent stale overwrite or mixed publication | Concurrent claims, retries, lost acknowledgements and crash/restart fixtures |
| Authorization | Every tested denied action and record/path access is denied | Domain/field/action matrix; cache and index paths; revocation independent of data lag |
| PIM release | Approved, valid, attributable content and retry-safe delivery | Locale/taxonomy/asset fixtures; failed channel recovery; historic release replay |

For the precision target, roughly 600 independent error-free decisions are
needed even for a one-sided 95% error bound near 0.5%; grouped dependence can
require more. Report the sampling method and uncertainty rather than displaying
a small synthetic fixture as broad quality evidence.

Preserve the eight sealed corpus replays as regression evidence. Establish a
new untouched evaluation source/partition for improvement claims; do not tune
against the exposed confirmation results. Diagnose retrieval, scoring,
cardinality and clustering errors separately. Record preprocessing and startup
as well as scoring costs. Run affected classic-local/Connect, app, transactional
integration and remote checks appropriate to each change, retaining applicable
existing evidence instead of rerunning unrelated experiments.

Track DBUs/dollars per 1,000 input records and online requests, pairs per record,
LLM escalation/error rate, queue age, disagreements, publication/projection lag,
graph expansion, storage/index size and delivery retries. Missing billing data
is missing evidence, never zero cost. Optional AI Search, Lakebase CDF, model
serving and marketplace routes require capability checks against current docs;
keep preview-specific dependencies visible.

## § 11 — Execution loop, evidence and finish line

Once execution is requested:

1. Read this ledger, the backlog dependencies and the latest relevant evidence.
   Select the first eligible unmet gate and record its hypothesis and bounds.
2. Implement a reviewable increment within the selected architecture; run checks
   appropriate to the change. Preserve source/configuration/label compatibility.
3. For an experiment, use the existing bounded runner and append-only run ledger.
   Record exact commands, commit/patch digest, environment, corpus/split/config
   hashes, seeds, resources, metrics, timing and cleanup. Never record credentials.
4. Capture terminal success or failure and diagnose the result. Retry a transient
   infrastructure failure at most twice; repeated unsupported operations park
   their dependent work while independent tasks continue.
5. Update phase/package status, evidence links, iteration count and next action.
   Keep the research backlog status synchronized. A code commit or deployed app
   alone cannot mark a feature gate passed.
6. Commit completed work and compact evidence to the existing public GitHub
   repository under the standing push instruction, preserving managed hooks.

Retain one active remote experiment and an eight-iteration experiment cap per
new LF phase, with **LF-B increased to twelve** by
[LF-DEC-005](spec/lakefusion/EXECUTION_DECISIONS.md). Declare finite per-run/sweep
limits before execution. These caps do not reset old ZR counters. Stop a sweep at its bound, retain the diagnosis
and continue eligible nondependent work. Stop only owned experimental resources
after evidence capture; respect an explicit user request to leave a demo running.
Record ongoing services required by an accepted deployment separately.

Store compact manifests and reports in the existing `experiments/` and `bench/`
evidence structure, with an LF phase/package identifier. Keep bulk models,
datasets, logs and generated caches ignored; preserve reproducible download/build
instructions and checksummed durable references. Missing or stale evidence must
remain visible. A read-only acceptance verifier must not generate its own proof.

| Checkpoint | Observed state | Next eligible action |
|---|---|---|
| 2026-09-21: plan created | Research committed at `a007166`; LF-A–F have no execution evidence. Existing [local test receipts](reports/test-runs/20260921T092956Z/README.md) and [redeployment audit](bench/REDEPLOYMENT.md) remain the baseline. | When execution is requested, start §4 with LM-001 and the two-source company/supplier contract. |
| 2026-09-21: LF-A execution | Typed contracts, synthetic fixture, policy and Postgres prototypes verified; eight metadata reads, 12 database checks and 37 final local tests pass. Five bounded receipts, including one retained runner-cleanup failure. [Evidence](bench/lakefusion/PHASE_A.md). | Resolve the four §1 decisions against the [pilot proposal](spec/lakefusion/PHASE_A.md) and [protocol](spec/lakefusion/PROTOCOL.md); then freeze the contract and select remaining capability spikes. |
| 2026-09-21: LF-A closed / LF-B started | All four decisions resolved; protocol/generator freeze committed; Unity Gateway smoke passes. Candidate comparison records 65% baseline, 95% name union and 100% lexical coverage. LF-A 8/8; LF-B 1/8. | Bind the selected candidate method to durable approved domain/mapping versions. |
| 2026-09-22: registry and execution binding | LM-002/003 complete for the declared pilot contract. 93 checks pass; immutable PostgreSQL versions, concurrent approval, restart persistence and exact candidate replay verified. LF-B 2/8. [Evidence](bench/lakefusion/registry-20260922.json). | LM-004: transactional persistent master IDs, aliases and identity-event history, preserving old deterministic IDs. |
| 2026-09-22: scan maintenance | Reviewed refreshed static/live findings; source-only scanning excludes generated copies and preserves prior reports. 21 local source/publication/app checks pass. Read-only metadata confirms serverless warehouses and no global init scripts. [Triage](reports/triage-20260922/README.md). No experiment slot consumed; LF-B remains 2/8. | LM-004 remains next; scan warnings do not close any product acceptance gate. |
| 2026-09-22: human-facing README | Rewrote the [project introduction](README.md) around customer use, the actual review app, a bundled local example, measured results and the delivery roadmap. Removed competitor references from the README. All 24 local links/images resolve and the synthetic quickstart configuration validates. Documentation only; LF-B remains 2/8. | LM-004 remains next; no implementation or acceptance status changed. |
| 2026-09-22: persistent identity | LM-004 complete for the internal worker contract. Two bounded local experiments pass (134 checks, then 138 after UTC/upgrade verification). IDs, legacy aliases and merge/split receipts survive concurrency and restart; old Spark behavior is unchanged. [Evidence](bench/lakefusion/identity-20260922-final.json). LF-B 4/8. | LM-005: scalar survivorship, followed by LM-006 provenance. GitHub publication remains pending resolution of the observed public visibility versus §2's private-repository requirement; local development continues. |
| 2026-09-22: scalar survivorship | LM-005 complete for the internal worker contract. Approved domain/mapping/policy bindings produce deterministic scalar records with explicit override, invalid-value and deletion behavior. 195 checks and six-company restart replay pass. [Evidence](bench/lakefusion/survivorship-20260922.json). LF-B 5/8. | LM-006: persist winning-value provenance and source crosswalks in versioned snapshots, keeping historic revisions explainable. GitHub publication remains pending the repository visibility decision. |
| 2026-09-22: immutable provenance | LM-006 complete for bounded internal publication/read services. Initial local/Delta proofs pass; the final [follow-up](experiments/20260922T095127Z-lf-b-provenance-retry-c09f7c/manifest.json) passes 225 local checks and live Delta verification, including retries with current scalar code unavailable. All owned tables/workspace files cleaned. LM-009 publication foundation is in progress; outbox/reconciliation remain open. LF-B 8/8. | Continue LM-014 matching/decision foundations and the first APX golden-record detail view; revise the LF-B experiment bound before further experiments. Phase B remains open. GitHub publishing remains pending the public/private visibility decision. |
| 2026-09-22: comparison foundation and APX preview | LM-014 in progress. 206 portable and 19 app checks pass; versioned comparison evidence routes eligible suggestions to review. A packaged six-company APX screen shows two publications and all field provenance. Type/build and desktop/mobile development checks pass. [Checkpoint](bench/lakefusion/PHASE_B.md). No new experiment; LF-B stays 8/8. | Approve or revise the [proposed four-run extension](bench/lakefusion/NEXT_EXPERIMENTS.md) before calibration/acceptance experiments. Phase B remains open. GitHub publishing still awaits resolution of the public/private visibility conflict. |
| 2026-09-22: recurring scan follow-up | Fresh source-only scan: 294 files, 0 errors, 21 warnings; warning rule/file locations unchanged. Latest raw JSON has no findings in the named review store/acceptance files. Live errors are 7 SQL, 1 HTTP 400 and 4 HTTP 404; cold-start cause is unproved. [Triage](reports/scan-followup-20260922/README.md). No code change or experiment; LF-B remains 8/8. | Existing calibration/acceptance and repository-visibility decisions remain pending. Scan repetition does not close those gates. |
| 2026-09-22: probability and band foundation | 294 portable checks pass, including 88 new analytical probability cases. Immutable model/feature/calibration/band metadata, declared split disjointness, deterministic vetoes and Brier/ECE/precision-bound helpers are implemented. [Contract](spec/lakefusion/PROBABILITY.md). Every eligible preview still routes to review; no fitting, corpus evaluation or automatic quality claim. LF-B remains 8/8; LM-014 remains in progress. | Calibration and acceptance experiments await the proposed bound extension. Comparison UI and promotion integration remain open. GitHub publication still awaits resolution of the public/private visibility conflict. |
| 2026-09-22: synthetic comparison explorer | The APX demo displays seven actual/normalized field comparisons for six companies across two publications, with conflicts, deletion and explicit pair origin. 301 portable and 25 app checks pass; pinned build, types, keyboard/error recovery and desktop/mobile preview pass. [Evidence](reports/lakefusion-comparison-ui-20260922/README.md). Historic publication values/hashes and frozen inputs are preserved. LF-B stays 8/8; LM-014 remains in progress. | Empirical calibration, promotion/live integration and full acceptance remain open. Further experiments need a revised bound; GitHub publication still awaits the repository-visibility decision. |
| 2026-09-22: extension and public publication approved | Laurent explicitly selected “raise it to 12” and “change to public”. [LF-DEC-005/006](spec/lakefusion/EXECUTION_DECISIONS.md) authorize LF-B 8/12 and publication to the existing public GitHub repository. Earlier protocol bytes and eight consumed runs remain unchanged. | Push completed commits through managed hooks, then execute slot 9's bounded APX acceptance plan. Calibration and quality gates remain open. |

**Finish line:** LF-A–F pass their required gates; all 25 packages have an honest
disposition, including conditional LM-025; the final app-to-master-to-graph/PIM
flows, upgrades and recovery are demonstrated; evidence and user/operator
documentation are committed; owned experimental resources are cleaned up. Any
remaining required capability leaves this goal incomplete until resolved or
explicitly removed from scope by the user.
