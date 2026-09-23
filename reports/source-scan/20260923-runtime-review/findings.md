# vibe-doctor scan — findings

- **target**: `/var/folders/m4/qxnnrm4s5q5f_p71yp5qdzmc0000gp/T/lakematch-source-scan-whvk1vwp`
- **rules**: `/Users/laurent.fabre/.local/share/vibe-doctor/best-practices.yaml`
- **rules in catalog**: 569
- **rules with offline checks**: 181
- **rules fired**: 45
- **rules skipped (online-only)**: 384
- **rules skipped (transcript-only)**: 4
- **rules skipped (language-scope)**: 1
- **files scanned**: 339
- **bytes scanned**: 2096808
- **bundle yaml files skipped**: 0
- **yaml_key checks unsupported**: 32
- **findings**: 131

## Severity breakdown

| severity | count |
|---|---|
| error | 1 |
| warn | 26 |
| info | 104 |

## Top rules

| rule | severity | title | hits |
|---|---|---|---|
| `BP-349` | error | Store all secrets in Databricks Secrets or an external vault — never in code. | 1 |
| `BP-128` | warn | Log parameters, metrics, and artifacts for every run. | 7 |
| `BP-101` | warn | Implement idempotent pipelines: re-running should not duplicate data. | 6 |
| `BP-542` | warn | Tag model serving endpoints with cost_center / team / environment so per-endpoint DBU lands on the right budget owner. | 3 |
| `BP-381` | warn | Use Mosaic AI Model Serving for deploying models — it provides managed, scalable endpoints. | 3 |
| `BP-059` | warn | Use parameterized queries instead of string concatenation to prevent SQL injection. | 2 |
| `BP-309` | warn | Store secrets (tokens, connection strings) in a secrets manager, not in code or notebooks. | 1 |
| `BP-131` | warn | Organize experiments by project/team using workspace folder structure. | 1 |
| `BP-555` | warn | Author Genie space artifacts in round-trip-stable form — `join_specs[*]` sorted by `id`, `text_instructions[]` as one consolidated block, `version: 2` — so POST-then-GET produces zero diff and future edits don't churn. | 1 |
| `BP-549` | warn | Enable Genie format assistance — without it, Genie returns raw SQL output instead of formatted answers, and downstream agents (chat panes, briefings) lose the structured shape they need. | 1 |
| `BP-551` | warn | Set a Genie space thumbnail (or emoji / cover_image) — bare spaces show as identical tiles in the Genie picker, which kills the per-persona visual cue customers expect at workshop time. | 1 |
| `BP-557` | info | Relabel the UI surface for known data artefacts — when a column or family is known to be a math/data artefact (e.g. clean family flagged CRITICAL due to drift-score artefact), reword sample_questions and instructions to neutral terms (`monitored families` not `adversarial families`; `configured threshold and alert status` not `breached threshold`) rather than rewiring the schema. | 28 |
| `BP-211` | info | Enable liquid clustering instead of traditional partitioning for new tables. | 10 |
| `BP-234` | info | Use NOT NULL constraints on critical columns. | 6 |
| `BP-171` | info | Add clear, business-friendly descriptions to every table and column exposed to Genie. | 6 |
| `BP-022` | info | Add comments/descriptions to all tables, columns, and schemas for discoverability. | 6 |
| `BP-007` | info | Use service principals for all jobs and automation. | 4 |
| `BP-109` | info | Monitor pipeline freshness: alert if a pipeline hasn't completed within its SLA. | 4 |
| `BP-227` | info | Use CHECK constraints for basic data validation at the table level. | 4 |
| `BP-047` | info | Set max scaling (max clusters) to control cost ceilings. | 3 |
| `BP-001` | info | Make Unity Catalog the default governance plane for all data and AI assets. | 3 |
| `BP-303` | info | Separate dev, staging, and prod environments at the workspace or catalog level. | 3 |
| `BP-098` | info | Use Enhanced Autoscaling in DLT to balance cost and throughput. | 3 |
| `BP-085` | info | Use Lakeflow Declarative Pipelines (DLT) for all production ETL/ELT. | 2 |
| `BP-095` | info | Set pipeline target to a Unity Catalog schema, not the legacy Hive metastore. | 2 |

## Findings

### Error (1)

| rule | file:line | detail | hint |
|---|---|---|---|
| `BP-349` | `runtime/tests/test_settings_credentials.py:141` | file_grep matched pattern_any | Possible hardcoded secret in code — use Databricks Secrets |

### Warn (26)

| rule | file:line | detail | hint |
|---|---|---|---|
| `BP-381` | `app/databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in app/databricks.yml |  |
| `BP-542` | `app/databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in app/databricks.yml |  |
| `BP-381` | `databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in databricks.yml |  |
| `BP-542` | `databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in databricks.yml |  |
| `BP-549` | `genie/build_space.py:2` | file_grep matched pattern_any | Python file uses Genie SDK markers but never references `format_assistance` (kwarg-style or dict-key) — set `format_assistance=True` on the space config (and pair with `entity_matching=True` per BP-550). |
| `BP-551` | `genie/build_space.py:2` | file_grep matched pattern_any | Python file uses Genie SDK markers but never references thumbnail / emoji / cover_image / icon. Per `rules/api_capabilities.yaml`, the upload endpoints PUT/POST `/api/2.0/genie/spaces/{id}/{thumbnail,image,icon,cover-image}` are unsupported (return 404), so set the thumbnail via the Genie UI after deploy and verify with `GET /api/2.0/genie/spaces/{id}` that the field is non-empty. |
| `BP-555` | `genie/build_space.py:214` | file_grep matched pattern_any | Python project declares `join_specs` but never sorts by `id` before POST. The server re-sorts on GET, so unsorted POSTs produce noisy round-trip diffs. Sort `join_specs` by `id` at author time. Note: this check skips JSON exports because those are already server-sorted (BP-555 ships only the source-side static check; the round-trip property is checked by api_get against a live workspace). |
| `BP-381` | `genie/databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in genie/databricks.yml |  |
| `BP-542` | `genie/databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in genie/databricks.yml |  |
| `BP-101` | `runtime/tests/test_postgres_runtime.py:110` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-309` | `runtime/tests/test_settings_credentials.py:141` | file_grep matched pattern_any | Possible hardcoded secret — move to a secrets manager |
| `BP-128` | `src/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `src/lakematch/mastering/access_registry.py:86` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-101` | `src/lakematch/mastering/registry.py:71` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-059` | `src/lakematch/mastering/workflow.py:70` | file_grep matched pattern_any | SQL built by string concatenation/f-string before .execute — use parameterized queries to prevent injection |
| `BP-101` | `src/lakematch/publication.py:124` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-101` | `tests/postgres/test_registry.py:96` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-059` | `tests/postgres/test_workflow.py:84` | file_grep matched pattern_any | SQL built by string concatenation/f-string before .execute — use parameterized queries to prevent injection |
| `BP-101` | `tests/test_source_hygiene.py:15` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `tests/test_tracking.py:66` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `tools/run_candidate_pairs.py:135` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `tools/run_compact_features.py:187` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `tools/run_linkage_candidates.py:143` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `tools/run_methods.py:195` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-131` | `tools/serverless_canary.py:63` | file_grep matched pattern_any | Per-user experiment path — shared projects should use /Shared/<project>/... |
| `BP-128` | `tools/tracking_canary.py:76` | file_grep matched pattern_any | start_run without logging is nearly empty |

### Info (104)

| rule | file:line | detail | hint |
|---|---|---|---|
| `BP-140` | _(repo-level)_ | file_present: no file matches glob **/{validate,validation}*.py |  |
| `BP-157` | _(repo-level)_ | file_present: no file matches glob **/{cleanup,prune}_experiments*.py |  |
| `BP-275` | _(repo-level)_ | file_present: no file matches glob **/tests/init_*.sh |  |
| `BP-305` | _(repo-level)_ | file_present: no file matches glob .github/workflows/*.yml |  |
| `BP-307` | _(repo-level)_ | file_present: no file matches glob .github/workflows/*.yml |  |
| `BP-513` | _(repo-level)_ | file_present: no file matches glob **/persona_tabs.yaml |  |
| `BP-516` | _(repo-level)_ | file_present: no file matches glob **/brand_assets.yaml |  |
| `BP-518` | _(repo-level)_ | file_present: no file matches glob **/requirements.yaml |  |
| `BP-524` | _(repo-level)_ | file_present: no file matches glob **/.github/workflows/docs-lag*.yml |  |
| `BP-525` | _(repo-level)_ | file_present: no file matches glob **/.vibe-doctor/branch_ownership.yaml |  |
| `BP-528` | _(repo-level)_ | file_grep pattern_none: no file under '**/.gitignore' contains the required pattern | Project tracks routeTree.gen.* or *.gen.* files — add to .gitignore and regenerate via pre-commit (P23). |
| `BP-529` | _(repo-level)_ | file_present: no file matches glob **/scripts/predeploy_smoke*.sh |  |
| `BP-535` | _(repo-level)_ | file_present: no file matches glob **/golden_questions.yaml |  |
| `BP-539` | _(repo-level)_ | file_present: no file matches glob **/vibe-doctor.yaml |  |
| `BP-540` | _(repo-level)_ | file_present: no file matches glob **/SESSION_STATE.md |  |
| `BP-001` | `app/databricks.yml` | yaml_key 'bundle.targets' not declared in app/databricks.yml |  |
| `BP-007` | `app/databricks.yml` | yaml_key 'resources.jobs' not declared in app/databricks.yml |  |
| `BP-047` | `app/databricks.yml` | yaml_key 'resources.sql_warehouses' not declared in app/databricks.yml |  |
| `BP-085` | `app/databricks.yml` | yaml_key 'resources.pipelines' not declared in app/databricks.yml |  |
| `BP-095` | `app/databricks.yml` | yaml_key 'resources.pipelines' not declared in app/databricks.yml |  |
| `BP-098` | `app/databricks.yml` | yaml_key 'resources.pipelines' not declared in app/databricks.yml |  |
| `BP-109` | `app/databricks.yml` | yaml_key 'resources.jobs' not declared in app/databricks.yml |  |
| `BP-303` | `app/databricks.yml` | yaml_key 'targets.prod' not declared in app/databricks.yml |  |
| `BP-544` | `app/databricks.yml` | yaml_key 'resources.apps.review.budget_policy_id' not declared in app/databricks.yml |  |
| `BP-022` | `app/migrations/mastering/0001_control.sql:3` | file_grep matched pattern_any | CREATE TABLE without COMMENT — add table and column descriptions for discoverability |
| `BP-171` | `app/migrations/mastering/0001_control.sql:3` | file_grep matched pattern_any | Table created without COMMENT on columns |
| `BP-234` | `app/migrations/mastering/0001_control.sql:5` | file_grep matched pattern_any | NOT NULL used — document critical-column constraints |
| `BP-227` | `app/migrations/mastering/0002_registry.sql:4` | file_grep matched pattern_any | CHECK constraint added — good for data validation |
| `BP-234` | `app/migrations/mastering/0002_registry.sql:5` | file_grep matched pattern_any | NOT NULL used — document critical-column constraints |
| `BP-022` | `app/migrations/mastering/0002_registry.sql:28` | file_grep matched pattern_any | CREATE TABLE without COMMENT — add table and column descriptions for discoverability |
| `BP-171` | `app/migrations/mastering/0002_registry.sql:28` | file_grep matched pattern_any | Table created without COMMENT on columns |
| `BP-227` | `app/migrations/mastering/0003_identity.sql:2` | file_grep matched pattern_any | CHECK constraint added — good for data validation |
| `BP-234` | `app/migrations/mastering/0003_identity.sql:6` | file_grep matched pattern_any | NOT NULL used — document critical-column constraints |
| `BP-022` | `app/migrations/mastering/0003_identity.sql:11` | file_grep matched pattern_any | CREATE TABLE without COMMENT — add table and column descriptions for discoverability |
| `BP-171` | `app/migrations/mastering/0003_identity.sql:11` | file_grep matched pattern_any | Table created without COMMENT on columns |
| `BP-022` | `app/migrations/mastering/0004_survivorship.sql:2` | file_grep matched pattern_any | CREATE TABLE without COMMENT — add table and column descriptions for discoverability |
| `BP-171` | `app/migrations/mastering/0004_survivorship.sql:2` | file_grep matched pattern_any | Table created without COMMENT on columns |
| `BP-234` | `app/migrations/mastering/0004_survivorship.sql:3` | file_grep matched pattern_any | NOT NULL used — document critical-column constraints |
| `BP-227` | `app/migrations/mastering/0004_survivorship.sql:26` | file_grep matched pattern_any | CHECK constraint added — good for data validation |
| `BP-227` | `app/migrations/mastering/0005_workflow.sql:3` | file_grep matched pattern_any | CHECK constraint added — good for data validation |
| `BP-234` | `app/migrations/mastering/0005_workflow.sql:4` | file_grep matched pattern_any | NOT NULL used — document critical-column constraints |
| `BP-022` | `app/migrations/mastering/0005_workflow.sql:49` | file_grep matched pattern_any | CREATE TABLE without COMMENT — add table and column descriptions for discoverability |
| `BP-171` | `app/migrations/mastering/0005_workflow.sql:49` | file_grep matched pattern_any | Table created without COMMENT on columns |
| `BP-022` | `app/migrations/mastering/0006_access.sql:3` | file_grep matched pattern_any | CREATE TABLE without COMMENT — add table and column descriptions for discoverability |
| `BP-171` | `app/migrations/mastering/0006_access.sql:3` | file_grep matched pattern_any | Table created without COMMENT on columns |
| `BP-234` | `app/migrations/mastering/0006_access.sql:4` | file_grep matched pattern_any | NOT NULL used — document critical-column constraints |
| `BP-319` | `app/pyproject.toml:39` | file_grep matched pattern_any | pyproject.toml declares hatchling backend but no [tool.hatch.build.targets.wheel] block — hatchling will fall back to default discovery. After a project rename this ships an empty wheel to Apps. See P11 in docs/demos/socomec-personas-postmortem.md. |
| `BP-557` | `app/tests/test_golden_demo.py:66` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-001` | `databricks.yml` | yaml_key 'bundle.targets' not declared in databricks.yml |  |
| `BP-007` | `databricks.yml` | yaml_key 'resources.jobs.frozen_pipeline.run_as' not declared in databricks.yml |  |
| `BP-007` | `databricks.yml` | yaml_key 'resources.jobs.cluster_fixture.run_as' not declared in databricks.yml |  |
| `BP-047` | `databricks.yml` | yaml_key 'resources.sql_warehouses' not declared in databricks.yml |  |
| `BP-098` | `databricks.yml` | yaml_key 'resources.pipelines.matching.clusters' not declared in databricks.yml |  |
| `BP-109` | `databricks.yml` | yaml_key 'resources.jobs.frozen_pipeline.tasks[0].depends_on' not declared in databricks.yml |  |
| `BP-109` | `databricks.yml` | yaml_key 'resources.jobs.cluster_fixture.tasks[0].depends_on' not declared in databricks.yml |  |
| `BP-303` | `databricks.yml` | yaml_key 'targets.prod' not declared in databricks.yml |  |
| `BP-001` | `genie/databricks.yml` | yaml_key 'bundle.targets' not declared in genie/databricks.yml |  |
| `BP-007` | `genie/databricks.yml` | yaml_key 'resources.jobs' not declared in genie/databricks.yml |  |
| `BP-047` | `genie/databricks.yml` | yaml_key 'resources.sql_warehouses' not declared in genie/databricks.yml |  |
| `BP-085` | `genie/databricks.yml` | yaml_key 'resources.pipelines' not declared in genie/databricks.yml |  |
| `BP-095` | `genie/databricks.yml` | yaml_key 'resources.pipelines' not declared in genie/databricks.yml |  |
| `BP-098` | `genie/databricks.yml` | yaml_key 'resources.pipelines' not declared in genie/databricks.yml |  |
| `BP-109` | `genie/databricks.yml` | yaml_key 'resources.jobs' not declared in genie/databricks.yml |  |
| `BP-303` | `genie/databricks.yml` | yaml_key 'targets.prod' not declared in genie/databricks.yml |  |
| `BP-557` | `src/lakematch/benchmark/company_pilot.py:3` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-211` | `src/lakematch/blocking.py:101` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `src/lakematch/candidates.py:77` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `src/lakematch/cluster_job.py:79` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `src/lakematch/clustering.py:106` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `src/lakematch/decision.py:19` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-557` | `src/lakematch/mastering/probability.py:30` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `src/lakematch/mastering/score_contract.py:24` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-211` | `src/lakematch/native_ml.py:132` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `src/lakematch/quality/native.py:36` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `src/lakematch/quality/rules.py:27` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-557` | `src/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `src/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `src/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `src/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `tools/accept_zr1.py:16` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/accept_zr2.py:29` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/accept_zr5_local.py:13` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/benchmark_campaign.py:36` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/candidate_pairs_sweep.py:26` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/cluster_sweep.py:33` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/compact_features_sweep.py:30` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/experiment.py:52` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/final_sweep.py:34` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/lakefusion_calibration.py:243` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/lakefusion_registry_run.py:83` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/linkage_sweep.py:27` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/methods_sweep.py:29` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/report_ablation.py:31` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/report_clusters.py:83` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/report_final.py:108` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/report_identity.py:105` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/report_linkage.py:41` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/report_retrieval.py:47` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-211` | `tools/run_clusters.py:143` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-557` | `tools/run_compatibility.py:29` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-211` | `tools/run_identity_increment.py:117` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-557` | `tools/serverless_adapter_sweep.py:33` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/verify.py:46` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-557` | `tools/verify_clusters.py:37` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
