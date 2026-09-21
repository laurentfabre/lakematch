# Source register

Retrieved **21 September 2026**. Source IDs in the assessment, implementation
design and backlog refer to this register. The machine-readable [sources.json](sources.json)
records URLs, redirects, retrieval timestamps and SHA-256 hashes. Public page
hashes cover raw HTML; dynamic page content can change them on a later request.
Original analysis is included here; cached copies of vendor pages are not distributed.

Product pages, release notes and customer stories establish what the vendor
advertises. They do not independently verify tenant behavior, performance or
total cost. Official platform documentation establishes documented capabilities,
not their availability in the selected workspace. This research made no remote
workspace changes and ran no new experiments.

## LakeFusion

| ID | Public resource | Evidence and qualification |
|---|---|---|
| LF01 | [LakeFusion homepage](https://www.lakefusion.ai/) | Product positioning across MDM, PIM and LakeGraph. Homepage retrieval retained at day precision. |
| LF02 | [MDM product](https://www.lakefusion.ai/mdm) | Matching, golden records and governed MDM. No tenant functionality was tested. |
| LF03 | [LakeFusion 6.0: 17 capabilities](https://www.lakefusion.ai/blog/introducing-lakefusion-6-0-17-capabilities-for-smarter-governed-master-data) | Matching cascade, AI mapping, roles, references, PIM, graph operations and MCP. Efficiency figures are vendor claims; no reproducible protocol or visible publication date was found. |
| LF04 | [LakeFusion 5.0](https://www.lakefusion.ai/blog/lakefusion-5-0) | Dated 14 July 2026: reference entities, relationships, structs/arrays and rule enhancements. |
| LF05 | [LakeGraph product and architecture](https://www.lakefusion.ai/graph) | Delta, persistent indexes, Lakebase, adjacency and caching. Advertised scale/latency lacks a reproducible benchmark protocol in the reviewed page. |
| LF06 | [PIM product](https://www.lakefusion.ai/pim) | Catalogs, taxonomies, attributes, assets, locales, channels and enrichment workflows. |
| LF07 | [Trust and security](https://www.lakefusion.ai/trust-and-security) | Vendor description of residency and platform controls; not an independent application security attestation. |
| LF08 | [MDM guide for enterprise teams](https://www.lakefusion.ai/blog/lakefusion-mdm-the-complete-guide-for-enterprise-data-teams) | Golden records, survivorship, stewardship and multidomain MDM positioning. |
| LF09 | [Global manufacturing company case study](https://www.lakefusion.ai/case-study/global-manufacturing-company) | Vendor-reported company/customer mastering, hierarchies and six-week delivery; not a controlled benchmark or software-build estimate. |
| LF10 | [Global professional services case study](https://www.lakefusion.ai/case-study/global-professional-services-enterprise) | Company mastering and identity granularity; no independent comparative evaluation. |
| LF11 | [AWS Marketplace listing](https://aws.amazon.com/marketplace/pp/prodview-hhofk6gcnpoca) | Listing shows v3.2.13.1, container/Fargate installation and initial deployment notes from 20 June 2025. May differ from current Apps packaging. |
| LF12 | [Databricks Marketplace App launch](https://www.lakefusion.ai/blog/lakefusion-joins-databricks-marketplace-app-launch-at-data-ai-summit-enabling-single-click-mdm-deployment) | Advertises Marketplace Apps deployment; check the specific delivery route and product version. |
| LF13 | [LakeFusion and Databricks](https://www.lakefusion.ai/lakefusion-databricks) | Platform integration, quality and deployment positioning; marketplace links. |
| LF14 | [Elliott Energy Customer 360 and D&B enrichment](https://www.lakefusion.ai/blog/elliott-energy-modernized-customer-360-with-databricks-native-mdm-dun-bradstreet-enriched-data) | Vendor-reported enrichment integration; does not establish included data licences or universal connector support. |
| LF15 | [AWS installation guide: sign-in boundary](https://support.lakefusion.ai/portal/en/kb/articles/lakefusion-installation-guide-via-aws-url) | Public link redirects to sign-in. Only the redirect/sign-in response was observed; installation content was not accessed. |

The installation guide (LF15) required sign-in. No login or private content was
used. The 6.0 page did not expose a reliable publication date in the extracted
public page; its retrieval date is recorded instead. The graph and matching
performance claims were not independently reproduced.

## Implementation references

These resources informed the proposed architecture; they do not imply that
LakeFusion uses each implementation or that Lakematch already implements it.

| ID | Resource | Design implication / constraint |
|---|---|---|
| D01 | [Apps authorization](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth) | Application/service-principal authorization differs from delegated user authorization. |
| D02 | [AI Search](https://docs.databricks.com/aws/en/ai-search/ai-search) | Search/index options and limitations: no direct row/column permissions, application ACL filters, unsupported `ARRAY<STRUCT>`. |
| D03 | [Lakebase Postgres](https://docs.databricks.com/aws/en/oltp/projects) | Operational Postgres foundation; availability and sizing require deployment-specific checks. |
| D04 | [Lakebase synced tables](https://docs.databricks.com/aws/en/oltp/projects/sync-tables) | Pipeline-owned serving tables, complex-type mapping, key requirements and distinct permission rules. Synced tables are not ordinary writable operational tables. |
| D05 | [Lakebase database permissions](https://docs.databricks.com/aws/en/oltp/projects/manage-roles-permissions) | Database/object privileges and role management; do not assume identical UC policy propagation for every access path. |
| D06 | [Delta change data feed](https://docs.databricks.com/aws/en/tables/features/change-data-feed) | Distinguishes legacy and automatic CDF. Automatic CDF requires Runtime 19+ and eligible tables; retention and policy limitations apply. |
| D07 | [AUTO CDC APIs](https://docs.databricks.com/aws/en/ldp/cdc) | Source change sequencing and SCD processing; does not implement incremental entity resolution. |
| D08 | [Databricks transactions](https://docs.databricks.com/aws/en/transactions) | Multi-statement/table transactions require eligible UC managed tables with Catalog commits and supported compute; no cross-system atomicity. |
| D09 | [Databricks constraints](https://docs.databricks.com/aws/en/tables/constraints) | PK/FK/unique constraints are informational. Do not use them as enforced uniqueness for operational task claims. |
| D10 | [Unity Catalog lineage](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage) | Platform/table/column lineage complements application attribute-value provenance. |
| D11 | [Model lifecycle in Unity Catalog](https://docs.databricks.com/aws/en/machine-learning/manage-model-lifecycle) | Governed model registration, versions and aliases; registration is separate from serving readiness. |
| D12 | [MCP and agent tools](https://docs.databricks.com/aws/en/agents/mcp-tools) | Platform tool integration options; application authorization still applies. |
| D13 | [ai_query](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_query) | Structured model invocation; runtime/region/model restrictions and SQL Classic limitations require checking. |
| D14 | [Apps on Databricks Marketplace](https://www.databricks.com/blog/announcing-apps-databricks-marketplace) | Launch article identifies Public Preview. Packaging eligibility must be checked before a release plan depends on it. |
| D15 | [Lakeflow Connect concepts](https://docs.databricks.com/aws/en/ingestion/lakeflow-connect) | Managed/standard source connectors; select only where source coverage and semantics fit. |
| D16 | [Lakebase changes into Delta](https://docs.databricks.com/aws/en/oltp/projects/quickstart-lakebase-cdf) | Lakebase change data feed is explicitly Public Preview in the retrieved documentation. |
| D17 | [Host a custom MCP server](https://docs.databricks.com/aws/en/agents/mcp-tools/custom-mcp) | Databricks Apps hosting route for custom MCP tools. |
| D18 | [Custom model serving](https://docs.databricks.com/aws/en/machine-learning/model-serving/custom-models) | Online inference architecture; does not make Lakematch's Spark-dependent pyfunc an online scorer automatically. |
| D19 | [Probability calibration](https://scikit-learn.org/stable/modules/calibration.html) | Calibration concepts and evaluation. Adapt to the Spark feature/model contract; no package replacement is implied. |
| D20 | [SHAP TreeExplainer](https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html) | Lists PySpark support; model, output mode and background-data compatibility need explicit tests. |
| D21 | [Splink blocking guide](https://moj-analytical-services.github.io/splink/topic_guides/blocking/blocking_rules.html) | Candidate/blocking trade-offs; conceptual implementation reference, not a proposed engine rewrite. |
| D22 | [Postgres row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) | RLS semantics and owner/superuser/BYPASSRLS exceptions; applies to owned tables, subject to Lakebase-specific restrictions. |

## Lakematch evidence

Baseline commit: `9920ec8126facdc5577517998190251097e0399c`. File hashes are in `sources.json`.
The latest test report identifies its engine-under-test revision and preserves
the original run receipts. Reading those receipts is not a fresh cloud test.

| ID | Code or evidence | Finding scope |
|---|---|---|
| E01 | [reports/test-runs/20260921T092956Z/README.md](../../../reports/test-runs/20260921T092956Z/README.md)<br>[reports/test-runs/20260921T092956Z/summary.json](../../../reports/test-runs/20260921T092956Z/summary.json) | Recorded local executions: 135 classic, 135 Connect, 13 app, eight exact replays. Domain metrics are task-specific, not an aggregate quality guarantee. |
| E02 | [bench/REDEPLOYMENT.md](../../../bench/REDEPLOYMENT.md)<br>[deployment/README.md](../../../deployment/README.md)<br>[databricks.yml](../../../databricks.yml)<br>[resources/serverless.job.yml](../../../resources/serverless.job.yml)<br>[resources/serverless.pipeline.yml](../../../resources/serverless.pipeline.yml)<br>[resources/serverless_fixture.job.yml](../../../resources/serverless_fixture.job.yml) | Existing bundle/recovery evidence; remote workspace was not rechecked for this research. Root targets share state/resources by design; full delegated acceptance remains pending. |
| E03 | [src/lakematch/config.py](../../../src/lakematch/config.py)<br>[src/lakematch/engine.py](../../../src/lakematch/engine.py)<br>[src/lakematch/entity.py](../../../src/lakematch/entity.py) | Available field/model choices and explicit implementation gates. Flags for paid integrations do not establish those implementations. |
| E04 | [src/lakematch/blocking.py](../../../src/lakematch/blocking.py)<br>[src/lakematch/candidates.py](../../../src/lakematch/candidates.py)<br>[src/lakematch/matcher.py](../../../src/lakematch/matcher.py)<br>[src/lakematch/embeddings.py](../../../src/lakematch/embeddings.py)<br>[src/lakematch/features.py](../../../src/lakematch/features.py) | Bounded candidate generation, native comparison features, RF/GBT/logistic estimators and optional local embeddings. |
| E05 | [app/src/lakematch_review/backend/router.py](../../../app/src/lakematch_review/backend/router.py)<br>[app/src/lakematch_review/backend/models.py](../../../app/src/lakematch_review/backend/models.py)<br>[app/src/lakematch_review/backend/store.py](../../../app/src/lakematch_review/backend/store.py)<br>[app/README.md](../../../app/README.md) | Pair review, provenance and single-writer Delta contract. Actor attribution is distinct from object-level authorization. |
| E06 | [src/lakematch/identity.py](../../../src/lakematch/identity.py)<br>[src/lakematch/clustering.py](../../../src/lakematch/clustering.py)<br>[src/lakematch/cluster_job.py](../../../src/lakematch/cluster_job.py)<br>[src/lakematch/publication.py](../../../src/lakematch/publication.py)<br>[src/lakematch/delta_publication.py](../../../src/lakematch/delta_publication.py) | Deterministic minimum-member identities, reconciliation journals and immutable snapshot publication. Memberships are not attribute-level golden records or business graphs. |
| E07 | [src/lakematch/quality/native.py](../../../src/lakematch/quality/native.py)<br>[src/lakematch/quality/dqx.py](../../../src/lakematch/quality/dqx.py)<br>[src/lakematch/quality/rules.py](../../../src/lakematch/quality/rules.py) | Validation/quarantine foundations, without the proposed stewardship quality dashboard. |
| E08 | [src/lakematch/composite_model.py](../../../src/lakematch/composite_model.py)<br>[src/lakematch/tracking.py](../../../src/lakematch/tracking.py)<br>[src/lakematch/native_ml.py](../../../src/lakematch/native_ml.py) | Spark-dependent batch scoring and immutable artifact/label evidence; requires separate work for low-latency online inference. |
