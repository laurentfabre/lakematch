# vibe-doctor scan — findings

- **target**: `/var/folders/m4/qxnnrm4s5q5f_p71yp5qdzmc0000gp/T/lakematch-source-scan-urm6da5a`
- **rules**: `/Users/laurent.fabre/.local/share/vibe-doctor/best-practices.yaml`
- **rules in catalog**: 569
- **rules with offline checks**: 181
- **rules fired**: 36
- **rules skipped (online-only)**: 384
- **rules skipped (transcript-only)**: 4
- **rules skipped (language-scope)**: 21
- **files scanned**: 208
- **bytes scanned**: 924045
- **bundle yaml files skipped**: 0
- **yaml_key checks unsupported**: 32
- **findings**: 83

## Severity breakdown

| severity | count |
|---|---|
| error | 0 |
| warn | 15 |
| info | 68 |

## Top rules

| rule | severity | title | hits |
|---|---|---|---|
| `BP-128` | warn | Log parameters, metrics, and artifacts for every run. | 7 |
| `BP-542` | warn | Tag model serving endpoints with cost_center / team / environment so per-endpoint DBU lands on the right budget owner. | 2 |
| `BP-381` | warn | Use Mosaic AI Model Serving for deploying models — it provides managed, scalable endpoints. | 2 |
| `BP-101` | warn | Implement idempotent pipelines: re-running should not duplicate data. | 2 |
| `BP-131` | warn | Organize experiments by project/team using workspace folder structure. | 1 |
| `BP-556` | warn | Ship at least one `ask_genie` smoke-test artifact per Genie space — a real natural-language question whose row count is cross-checked against direct SQL via the warehouse. Round-trip GET alone misses binding/entity-match/join failures; only a real NL roundtrip catches them. | 1 |
| `BP-557` | info | Relabel the UI surface for known data artefacts — when a column or family is known to be a math/data artefact (e.g. clean family flagged CRITICAL due to drift-score artefact), reword sample_questions and instructions to neutral terms (`monitored families` not `adversarial families`; `configured threshold and alert status` not `breached threshold`) rather than rewiring the schema. | 22 |
| `BP-211` | info | Enable liquid clustering instead of traditional partitioning for new tables. | 10 |
| `BP-007` | info | Use service principals for all jobs and automation. | 3 |
| `BP-109` | info | Monitor pipeline freshness: alert if a pipeline hasn't completed within its SLA. | 3 |
| `BP-047` | info | Set max scaling (max clusters) to control cost ceilings. | 2 |
| `BP-001` | info | Make Unity Catalog the default governance plane for all data and AI assets. | 2 |
| `BP-303` | info | Separate dev, staging, and prod environments at the workspace or catalog level. | 2 |
| `BP-098` | info | Use Enhanced Autoscaling in DLT to balance cost and throughput. | 2 |
| `BP-516` | info | Reference brand assets (logos, palette colors) through a manifest with sha256 — inline SVGs drift from official brand. | 1 |
| `BP-525` | info | Multi-agent repos must declare branch ownership (.vibe-doctor/branch_ownership.yaml) — pre-push hook rejects overlapping path ownership across active PRs. | 1 |
| `BP-518` | info | Persist customer brief (attendees, personas, success outcomes, demo flows, excluded scopes) as a versioned requirements.yaml — workshop intent should not live only in chat. | 1 |
| `BP-132` | info | Log input datasets with mlflow.log_input() for reproducibility. | 1 |
| `BP-394` | info | Implement model signatures and input validation on serving endpoints. | 1 |
| `BP-524` | info | When databricks.yml resources or app.yml change, require a parallel diff in docs/{DEPLOY,RUNBOOK,CHANGELOG_*}.md — runbooks should not lag implementation. | 1 |
| `BP-305` | info | Automate deployments with CI/CD pipelines (GitHub Actions, Azure DevOps, GitLab CI, etc.). | 1 |
| `BP-529` | info | Pre-deploy smoke must verify codex/AI-gateway auth: ping `codex exec --skip-git-repo-check 'ping'` and assert HTTP 200 before relying on subagent reviews. | 1 |
| `BP-275` | info | Test new DBR versions in staging before promoting to production. | 1 |
| `BP-540` | info | Emit a SESSION_STATE.md checkpoint at 80% context budget — open issues, fixed invariants, branches, deploy URL, last smoke result — so a context reset doesn't lose state. | 1 |
| `BP-129` | info | Register production models in Unity Catalog Model Registry. | 1 |

## Findings

### Error (0)

_No findings at this severity._

### Warn (15)

| rule | file:line | detail | hint |
|---|---|---|---|
| `BP-556` | _(repo-level)_ | file_present: no file matches glob **/{tests,smoke,validation}/**/{ask_genie,genie_smoke,genie_validate}*.{py,sql,md,yaml,yml,json} | No `ask_genie` smoke-test artifact found. Add one NL question per space under tests/ or smoke/, recording the question text, the Genie row count, and the equivalent direct-SQL row count. |
| `BP-381` | `app/databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in app/databricks.yml |  |
| `BP-542` | `app/databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in app/databricks.yml |  |
| `BP-381` | `databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in databricks.yml |  |
| `BP-542` | `databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in databricks.yml |  |
| `BP-128` | `src/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `src/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-101` | `tests/test_source_hygiene.py:15` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `tests/test_tracking.py:66` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `tools/run_candidate_pairs.py:135` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `tools/run_compact_features.py:187` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `tools/run_linkage_candidates.py:143` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `tools/run_methods.py:195` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-131` | `tools/serverless_canary.py:63` | file_grep matched pattern_any | Per-user experiment path — shared projects should use /Shared/<project>/... |
| `BP-128` | `tools/tracking_canary.py:76` | file_grep matched pattern_any | start_run without logging is nearly empty |

### Info (68)

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
| `BP-544` | `app/databricks.yml` | yaml_key 'resources.apps.lakematch-review-app.budget_policy_id' not declared in app/databricks.yml |  |
| `BP-319` | `app/pyproject.toml:39` | file_grep matched pattern_any | pyproject.toml declares hatchling backend but no [tool.hatch.build.targets.wheel] block — hatchling will fall back to default discovery. After a project rename this ships an empty wheel to Apps. See P11 in docs/demos/socomec-personas-postmortem.md. |
| `BP-001` | `databricks.yml` | yaml_key 'bundle.targets' not declared in databricks.yml |  |
| `BP-007` | `databricks.yml` | yaml_key 'resources.jobs.frozen_pipeline.run_as' not declared in databricks.yml |  |
| `BP-007` | `databricks.yml` | yaml_key 'resources.jobs.cluster_fixture.run_as' not declared in databricks.yml |  |
| `BP-047` | `databricks.yml` | yaml_key 'resources.sql_warehouses' not declared in databricks.yml |  |
| `BP-098` | `databricks.yml` | yaml_key 'resources.pipelines.matching.clusters' not declared in databricks.yml |  |
| `BP-109` | `databricks.yml` | yaml_key 'resources.jobs.frozen_pipeline.tasks[0].depends_on' not declared in databricks.yml |  |
| `BP-109` | `databricks.yml` | yaml_key 'resources.jobs.cluster_fixture.tasks[0].depends_on' not declared in databricks.yml |  |
| `BP-303` | `databricks.yml` | yaml_key 'targets.prod' not declared in databricks.yml |  |
| `BP-211` | `src/lakematch/blocking.py:101` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `src/lakematch/candidates.py:77` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `src/lakematch/cluster_job.py:79` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `src/lakematch/clustering.py:106` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `src/lakematch/decision.py:19` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
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
