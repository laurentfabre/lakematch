# LakeFusion-roadmap decision record

## LF-DEC-001 — Pilot sources and identity granularity

**Selected by Laurent on 2026-09-21:** “Use synthetic ERP + CRM, legal-company masters”.

The pilot uses synthetic ERP vendor records (`erp_vendor`) and synthetic CRM
accounts (`crm_account`). Each master represents a legal company. Branches and
corporate families are separate objects or relationships; sharing an address,
brand or parent does not establish identical legal identity. Supplier/customer
are business roles of a legal company rather than separate identity namespaces.

The [company fixture](../../examples/mastering/company_pilot/README.md) and its
versioned domain/source mappings are the implementation starting point. This
selection does not freeze the evaluation workload or its train/validation/
confirmation partitions.

## LF-DEC-002 — Customer Solution Accelerator and SA demo material

**Selected by Laurent on 2026-09-21:** “Solution Accelerator for Customers to
deploy and demo material for SAs”.

Deliver a customer-deployable Solution Accelerator plus an SA demo kit. Phase F
must include a parameterized installation path, customer prerequisite/permission
checks, synthetic sample data, guided demo scenarios, reset/cleanup procedures,
troubleshooting, upgrade/restore instructions and a nontechnical guide/PDF.
Validate deployment using supplied workspace/catalog/resource bindings rather
than requiring Laurent's existing workspace, user path or resource IDs.

Commercial licensing, subscription entitlements and marketplace distribution
in LM-025 are **not applicable to this selected accelerator scope**. Customer
packaging, documentation and deployment qualification remain required in LM-024.
The current repository remains private; choosing a distribution format does not
publish it or choose a customer's workspace on their behalf.

## LF-DEC-003 — AI through Unity Gateway

**Selected by Laurent on 2026-09-21:** “Use AI via Unity Gateway”.

AI-assisted pilot flows use Unity Gateway model services governed in Unity
Catalog. Discover available services on `fevm-gdpr2` before selecting a model;
use the workspace's `/ai-gateway/mlflow/v1` API with explicit profile credentials.
Direct provider calls and a legacy serving endpoint are not equivalent evidence
for this choice. No model response becomes a source fact, training label,
approved operation or automatic identity merge merely because inference works.

Implement bounded structured suggestions/adjudication with abstention, current
authorization, a versioned cache, token/latency/cost receipts and human review.
Test enabled and disabled/failure behavior. A gateway capability smoke is not
evidence of marginal quality benefit. Product activation remains subject to the
LM-014/015 quality gates; provider failure leaves deterministic and review flows
available. Licensed enrichment still needs source rights. No other provider is
silently substituted if this workspace lacks the selected gateway capability.

## LF-DEC-004 — Evaluation protocol v0.1

**Selected by Laurent on 2026-09-21:** “Use protocol v0.1 as drafted”.

The [approved draft snapshot](frozen/protocol-v0.1-approved.md) preserves the exact
draft bytes. The [effective protocol](PROTOCOL.md) records approved status and
the explicit LF-DEC-003 overlay replacing its proposal to disable pilot AI.
The numeric workload, partitions, quality/SLO targets and finite budgets are
unchanged. The [freeze receipt](frozen/phase-a-v0.1.json) binds these documents
and the initial domain, API, roles and database contracts by SHA-256.

The 40,000-row workload uses whole-family 60/20/20 splits. Generator corruption
counts, candidate-cap orientation and training-negative sampling are frozen
before quality comparisons, as required by the protocol. This approval is not
a quality result and does not reopen the original sealed benchmarks or ZR caps.
No §1 user selection remains pending.
