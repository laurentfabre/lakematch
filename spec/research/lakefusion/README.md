# LakeFusion feature assessment and Lakematch roadmap

Research date: **21 September 2026**. Lakematch baseline: **`9920ec8`**.
Scope: public resources and the existing repository. No product login, private
documentation, remote deployment, or new benchmark experiment was used.

**Lakematch can build comparable capabilities on its existing stack, but the
gap is a substantial MDM product layer, followed by two additional applications:
relationship intelligence and product information management.** The current
engine and review app are useful foundations; they are not full MDM parity.

Recommended order:

1. Improve candidate coverage and establish versioned domain/configuration contracts.
2. Add durable business identities, golden records, survivorship and attribute provenance.
3. Turn pair review into concurrent stewardship with edits, merge/unmerge and approvals.
4. Add incremental processing, online resolution and relationship exploration.
5. Build PIM on the shared governance and mastering services.

Retain APX 0.3.8/React/FastAPI for the application and Spark for batch processing.
Use Databricks platform services selectively, with portable interfaces and a
local test path. Changing frontend frameworks would not close the major gaps.

The detailed [implementation design](IMPLEMENTATION.md) includes architecture,
schemas, APIs, delivery phases and measurable acceptance gates. The
[backlog](backlog.csv) turns the recommendations into ordered work packages.
[Sources](SOURCES.md) links every public reference and records limitations;
[sources.json](sources.json) preserves retrieval dates and content hashes.
The [goal file](../../../goal_lakefusion.md) organizes all six phases and 25 work
packages into an execution ledger with dependencies and acceptance criteria.

## What LakeFusion publicly offers

Its current site presents **MDM, PIM and LakeGraph** as three product areas.
MDM includes governed golden records, survivorship, stewardship and multidomain
modelling. PIM adds catalog operations and publishing. Graph adds relationships
and interactive traversal. These are public product descriptions, not features
we exercised in a tenant. [LF01–LF08](SOURCES.md#lakefusion)

The 6.0 announcement adds a deterministic → Random Forest → LLM matching
cascade, score bands and SHAP explanations; hierarchy/reference enhancements;
AI mapping; search-before-create; granular roles; PIM taxonomy crosswalks;
graph alerts/actions; MCP access; licensing and external environments. It also
describes an in-app pipeline editor. [LF03](SOURCES.md#lakefusion)

### Feature comparison

“Present” refers to specific code or recorded evidence. “Partial” means that
the underlying primitive exists, but the complete product workflow does not.
“New” means no corresponding implementation was found in the reviewed modules.

| Capability advertised by LakeFusion | Lakematch today | Work needed for comparable functionality | Evidence |
|---|---|---|---|
| Databricks-native deployment | Present: engine, app and Genie bundles; same-workspace recovery tested | Separate development/staging/production state, migrations, release/rollback and installation checks | LF02, LF13; E02 |
| Multiple business domains | Partial: configurable fields per engine invocation | Versioned domain registry, business identity granularity, source mappings and domain-specific policies | LF08; E03 |
| Profiling, validation and quarantine | Partial: native/DQX checks and quarantined outputs | Profiling dashboard, editable rules, exception ownership and remediation/resubmit | LF08, LF13; E07 |
| Deterministic, probabilistic and AI matching | Partial: blocking, GBT/RF/logistic models, optional local embeddings | Ordered match rules, calibrated decision bands, bounded LLM adjudication and model comparisons | LF02, LF03; E03–E04 |
| Explainable matching | Partial: probability, model version and raw records in review | Per-field evidence and tested model-specific explanations; distinguish contributions from causal explanations | LF03; E05 |
| Golden records and survivorship | New: output links/memberships are not winning attribute values | Attribute-level winners, source priority, verified overrides, nested/array policies and history | LF04, LF08; E06 |
| No-code stewardship, edits and unmatching | Partial: pair labels, reasons, immutable receipts, history, training export | Entity search/detail, task ownership, conflicts, approvals, merge preview, split/unmerge and correction events | LF08; E05 |
| Stable master identities and source lineage | Partial: deterministic IDs and complete reconciliation journals | Persistent identity registry, aliases and attribute lineage; preserve IDs when canonical source membership changes | LF08–LF10; E06 |
| Reference data and nested references | Partial: scalar field types and string arrays in engine | Governed reference entities, parent-child constraints, typed nested schemas and reference resolution | LF03–LF04; E03, E05 |
| Business relationships and hierarchies | New: match graphs express identity, not business relationships | Typed/effective-dated edges, cardinalities, cycle policies, relationship attributes and hierarchy views | LF04–LF05; E06 |
| Interactive graph queries | New | Bounded traversal API, governed adjacency projection, freshness/version tracking and graph UI | LF05; E06 |
| Online search-before-create | New: current model is Spark batch-oriented | Fast retrieval and non-Spark scoring; explicit existing/review/create outcomes and reservation semantics | LF03; E08 |
| AI-assisted source mapping | New | Schema/sample profiler, typed suggestions, approval, reusable mapping versions and drift detection | LF03; E03 |
| Granular application roles | Partial: authenticated actor plus service-principal Delta access | Domain/object/action authorization, separation of proposal/approval and consistent serving permissions | LF03, LF07; E05 |
| Incremental operational mastering | Partial: triggered jobs and full-snapshot reconciliation | Change cursors, deletes, affected-entity recomputation, durable publication and recovery from retention gaps | LF05, LF08; E02, E06 |
| Pipeline editor and operations | Partial: fixed DAB job dependencies | Template-based configuration, run status, logs, cancellation/retry and later a constrained canvas | LF03; E02 |
| PIM catalog, attributes and content | New: product benchmark matching is not PIM | Family/variant model, taxonomy, working/live catalogs, completeness, assets, locale/channel values | LF06; E01 |
| Multiple taxonomies and crosswalks | New | Versioned classifications, reviewed mappings, propagation preview and conflict handling | LF03; E03 |
| PIM enrichment and localization | New | Approved content-generation/translation jobs, factual validation, provenance and publishing review | LF06 |
| Graph alerts and downstream actions | New | Scheduled rules, deduplicated events, approval boundaries and an outbox for delivery | LF03 |
| MCP and conversational access | Partial: standalone Genie smoke; delegated app acceptance pending | Narrow typed tools, shared authorization, provenance/freshness envelope and separate mutation approval | LF03; E02 |
| Documentation and environment management | Partial: substantial engineering/runbook material | User help, versioned API/schema docs, domain templates, independent environments and upgrade tooling | LF03; E02 |
| Licensing and feature entitlements | New; not needed for an internal pilot | Only if commercial distribution is intended: signed entitlements, metering and outage/grace policy | LF03 |
| External enrichment and domain solutions | New | Optional licensed adapters, starting with one concrete source; distinguish enrichment from verified truth | LF09, LF14 |

Evidence references E01–E08 resolve to code and reports in
[the source register](SOURCES.md#lakematch-evidence).

## The most important technical findings

### 1. Retrieval quality comes before a larger model stack

The latest local run passed **283 regression test executions** and reproduced
eight frozen cases exactly. That proves useful correctness and reproducibility,
but quality varies by domain. [E01](SOURCES.md#lakematch-evidence)

| Held-out corpus/task | F1 | Candidate recall |
|---|---:|---:|
| FEBRL4, all fields | 98.89% | 97.80% |
| FEBRL4, SSN hidden | 98.68% | 97.40% |
| BPID | 56.05% | 54.61% |
| Abt–Buy | 60.11% | 62.07% |
| Amazon–Google | 68.23% | 88.53% |
| Walmart–Amazon | 68.34% | 76.04% |
| DBLP–ACM | 98.75% | 97.97% |
| Affiliations | 26.39% | 15.20% |

These are different evaluation tasks; do not average their F1 values. At present,
the affiliation candidate stage excludes about 85% of known positive links.
An RF or LLM operating only on those candidates cannot recover excluded pairs.
Start with domain-specific normalization and unions of complementary candidate
methods, preserving the existing pre-join and pair budgets. Use semantic search
where measured lexical retrieval leaves a gap, rather than treating embeddings
as an automatic improvement. [E01, E04; D02, D21](SOURCES.md)

### 2. A business identity must survive source-record changes

`identity.assign()` hashes a namespace with the minimum member record ID.
The implementation explicitly documents that adding a smaller ID or removing
the canonical member can rekey the cluster. Existing journals make that
change observable, but an operational master ID should generally persist.
Introduce an identity registry and alias history; retain the deterministic
algorithm for existing benchmark compatibility. [E06](SOURCES.md#lakematch-evidence)

### 3. Golden records require decisions at the attribute level

Knowing that two records match does not decide which name, address, legal
identifier or classification to publish. Add reproducible survivorship rules
and provenance for each selected value. Unity Catalog lineage complements this
history; it is not a substitute for a record-level “why this value won” journal.
[LF08; D10](SOURCES.md)

### 4. The current review store is a bounded batch-review design

The app has a single process lock for Delta writes, a 10,000-row snapshot bound,
and one accepted review per pair. That supports its tested batch contract.
It does not provide distributed task claiming, concurrent approvals, editing,
or an enterprise inbox. Add a transactional workflow store before allowing
multiple app workers. Preserve current immutable label receipts and migrate
through an explicit adapter. [E05](SOURCES.md#lakematch-evidence)

### 5. Online serving is a separate execution path

`PairModel.predict()` creates/uses Spark and assumes a complete candidate-pair
snapshot for cardinality. Registering this model does not establish a low-latency
search-before-create service. Implement a measured non-Spark scorer/feature path,
or a separately trained online model, and retain batch/online parity checks.
Per-request pair scoring must not silently change global matching constraints.
[E08; D18](SOURCES.md)

### 6. Graph functionality needs a serving design

LakeGraph's public architecture describes Delta tables, a persistent index,
Lakebase queries, adjacency lists and caching. It also advertises 5-hop queries
in seconds and sub-5-ms 1-hop lookups. No reproducible workload/hardware/cache
protocol was found in the reviewed pages. Treat these as vendor performance
claims, not Lakematch acceptance results. [LF05](SOURCES.md#lakefusion)

Use Delta as the published relationship system of record and a rebuildable,
versioned serving projection for interactive exploration. A copied index inside
the Databricks platform still has storage, synchronization and access-control
requirements. Describe its actual data boundary rather than promising literal
“zero copies.” [D03–D05](SOURCES.md#implementation-references)

## What the public evidence does and does not establish

- **Product breadth:** clear public descriptions of MDM, Graph and PIM, with
  detailed 5.0/6.0 release notes. Actual tenant behavior was not exercised.
- **Customer usage:** two vendor case studies describe customer/company mastering;
  one reports delivery in six weeks. Neither is a controlled comparison against
  Lakematch. Customer implementation duration is not a product-build estimate.
  [LF09–LF10](SOURCES.md#lakefusion)
- **Matching economics:** the 6.0 article cites approximately 80% deterministic
  clearance and 50% fewer LLM calls. The reviewed material does not supply an
  independently reproducible protocol. [LF03](SOURCES.md#lakefusion)
- **Deployment versions:** the AWS listing presents a container/Fargate installer
  and version `v3.2.13.1`; newer material discusses Databricks Marketplace Apps.
  These are different public deployment descriptions. Confirm a specific product
  version before assuming one architecture. [LF11–LF13; D14](SOURCES.md)
- **Security:** native deployment and inherited platform controls are useful
  foundations, but they do not establish every application authorization,
  certification, residency or external-model behavior. The trust page and the
  newer 6.0 application-role description also differ in emphasis.
  [LF03, LF07](SOURCES.md#lakefusion)
- **Documentation access:** the installation guide linked by AWS redirected to
  a sign-in page. It was not accessed beyond that public boundary. “External
  Environments” is named in 6.0 without enough detail to define precise parity.
  [LF03, LF15](SOURCES.md#lakefusion)
- **Unknowns:** reproducible matching/graph benchmarks, current detailed API
  contracts, tenant-level feature availability, HA/SLA behavior and total cost
  under a fixed workload remain unverified by this research.

## Delivery recommendation

Aim first for a **single-domain governed MDM pilot**, not a broad imitation of
every screen. It should onboard two sources, produce explainable golden records,
handle conflicting values, support reversible decisions, and survive concurrent
reviews and failed publications. A company/supplier domain is a practical first
vertical because it exercises both identity and hierarchy without introducing
all PIM editorial workflows at once.

Planning estimate, not a commitment: **12–16 weeks for that pilot** with roughly
four to five engineers spanning Spark/ML, backend/data, frontend and platform,
plus regular steward/UX input. **Six to nine months** is a more credible starting
range for useful MDM + Graph + PIM breadth with five to seven engineers and QA
support. Enterprise-scale performance, commercial packaging and domain-specific
connectors can extend that range. Re-estimate after the first two-week spike.

The first implementation slice should be a versioned domain contract, persistent
identity registry, scalar survivorship and a golden-record detail page with
source provenance. Run a bounded retrieval-improvement study alongside that
slice under a new declared validation plan. Do not retune against the sealed
confirmation results or silently reopen the parked million-record campaign.

No existing engine code, deployment configuration, test evidence or campaign
acceptance status was changed for this assessment.
