# vibe-doctor scan — findings

- **target**: `/Users/laurent.fabre/Projects/Claude/lakematch/.`
- **rules**: `/Users/laurent.fabre/.local/share/vibe-doctor/best-practices.yaml`
- **rules in catalog**: 569
- **rules with offline checks**: 181
- **rules fired**: 47
- **rules skipped (online-only)**: 384
- **rules skipped (transcript-only)**: 4
- **rules skipped (language-scope)**: 1
- **files scanned**: 9904
- **bytes scanned**: 580671042
- **bundle yaml files skipped**: 0
- **yaml_key checks unsupported**: 32
- **findings**: 2239

## Online scan

| metric | value |
|---|---|
| online checks in catalog | 442 |
| attempted | 46 |
| evaluated (pass/fail) | 10 |
| → passed | 9 |
| → failed | 1 |
| unsupported predicate (state fetched) | 24 |
| skipped: templated | 391 |
| skipped: account-level | 5 |
| skipped: mutating SQL | 0 |
| skipped: below --min-severity | 0 |
| errored (auth/network/5xx) | 12 |

## Severity breakdown

| severity | count |
|---|---|
| error | 7 |
| warn | 359 |
| info | 1873 |

## Top rules

| rule | severity | title | hits |
|---|---|---|---|
| `BP-057` | error | Use warehouse profiles (channel) to test preview features before production. | 2 |
| `BP-075` | error | Avoid running DDL/DML on interactive warehouses; use jobs clusters instead. | 1 |
| `BP-053` | error | Avoid Classic SQL Warehouses for new workloads; prefer Serverless or Pro. | 1 |
| `BP-003` | error | Turn off workspace-level SCIM in Unity Catalog workspaces. | 1 |
| `BP-550` | error | Enable Genie entity matching whenever format assistance is on — entity matching grounds the formatted output to real Unity Catalog entities; without it, Genie can format hallucinated names that pass type checks but reference nothing. | 1 |
| `BP-045` | error | Enable auto-stop with a short idle timeout (5–10 min) for interactive warehouses. | 1 |
| `BP-128` | warn | Log parameters, metrics, and artifacts for every run. | 228 |
| `BP-101` | warn | Implement idempotent pipelines: re-running should not duplicate data. | 74 |
| `BP-558` | warn | Populate `instructions.example_question_sqls[]` on every Genie space — these are the curated example queries Genie shows alongside curated_questions; without them, the model has nothing to ground new questions against. | 5 |
| `BP-047` | warn | Set max scaling (max clusters) to control cost ceilings. | 5 |
| `BP-561` | warn | Populate `instructions.sql_snippets` with reusable filters, expressions, and measures — these are the named SQL fragments Genie composes user-questions from; without them, every answer rebuilds aggregations from scratch and answer style drifts across questions. | 5 |
| `BP-559` | warn | Declare `instructions.join_specs[]` when a Genie space references ≥2 tables — without declared joins, Genie writes ad-hoc JOIN SQL that ignores cardinality and produces row-explosion bugs (the BP-554 live-introspection lesson is moot if joins aren't pre-declared). | 5 |
| `BP-381` | warn | Use Mosaic AI Model Serving for deploying models — it provides managed, scalable endpoints. | 4 |
| `BP-043` | warn | Use Serverless SQL Warehouses as the default for all SQL workloads. | 4 |
| `BP-549` | warn | Enable Genie format assistance — without it, Genie returns raw SQL output instead of formatted answers, and downstream agents (chat panes, briefings) lose the structured shape they need. | 3 |
| `BP-048` | warn | Use query queuing behavior to tune concurrency vs. latency tradeoffs. | 3 |
| `BP-131` | warn | Organize experiments by project/team using workspace folder structure. | 3 |
| `BP-542` | warn | Tag model serving endpoints with cost_center / team / environment so per-endpoint DBU lands on the right budget owner. | 3 |
| `BP-078` | warn | Monitor queue depth; if queries queue frequently, add clusters or upsize. | 2 |
| `BP-562` | warn | Every `sql_snippets[*]` (filter / expression / measure) ships at least one `synonyms[]` entry — without synonyms, Genie can't map user phrasing (`brake rate`, `BRAKE share`) to the named snippet, defeating the entire point of declaring the snippet. | 2 |
| `BP-551` | warn | Set a Genie space thumbnail (or emoji / cover_image) — bare spaces show as identical tiles in the Genie picker, which kills the per-persona visual cue customers expect at workshop time. | 2 |
| `BP-555` | warn | Author Genie space artifacts in round-trip-stable form — `join_specs[*]` sorted by `id`, `text_instructions[]` as one consolidated block, `version: 2` — so POST-then-GET produces zero diff and future edits don't churn. | 2 |
| `BP-014` | warn | Use managed tables and managed volumes by default. | 2 |
| `BP-176` | warn | Use certified answers to lock in verified responses for critical questions. | 2 |
| `BP-554` | warn | Introspect every Genie-referenced table live (DESCRIBE / COUNT / COLLECT_SET on enum columns) before drafting SQL — without it, sample_questions and CSEs are written against assumed cardinality and enum values, which is the #1 source of CRITICAL Genie review findings (non-unique join keys, unknown enum values, zero-row edge cases). | 2 |

## Findings

### Error (7)

| rule | file:line | detail | hint |
|---|---|---|---|
| `BP-003` | _(repo-level)_ | online state fetched (count=1); expect 'provisioning disabled' not a count predicate — agent must interpret |  |
| `BP-045` | _(repo-level)_ | online state fetched (count=2); expect 'auto_stop_mins in [1, 30]' not a count predicate — agent must interpret |  |
| `BP-053` | _(repo-level)_ | online state fetched (count=2); expect 'no warehouses with warehouse_type=CLASSIC' not a count predicate — agent must interpret |  |
| `BP-057` | _(repo-level)_ | online state fetched (count=2); expect 'channel=CURRENT on prod-tagged warehouses' not a count predicate — agent must interpret |  |
| `BP-057` | _(repo-level)_ | online state fetched (count=2); expect 'if channel=PREVIEW then name matches /(?i)preview\|beta\|test/' not a count predicate — agent must interpret |  |
| `BP-075` | _(repo-level)_ | online state fetched (count=1); expect 'no all-purpose cluster tagged 'purpose=sql' or serving BI' not a count predicate — agent must interpret |  |
| `BP-550` | _(repo-level)_ | online state fetched (count=6); expect 'for each space where format_assistance=true, entity_matching is also true' not a count predicate — agent must interpret |  |

### Warn (359)

| rule | file:line | detail | hint |
|---|---|---|---|
| `BP-014` | _(repo-level)_ | online check errored: http-error (http 400) |  |
| `BP-017` | _(repo-level)_ | online state fetched (count=6); expect 'catalog names reflect env/team boundaries (e.g. *_dev, *_prod)' not a count predicate — agent must interpret |  |
| `BP-043` | _(repo-level)_ | online state fetched (count=2); expect 'warehouse_type=PRO and enable_serverless_compute=true' not a count predicate — agent must interpret |  |
| `BP-043` | _(repo-level)_ | online state fetched (count=2); expect 'latency-sensitive/BI workloads on serverless warehouses' not a count predicate — agent must interpret |  |
| `BP-043` | _(repo-level)_ | online state fetched (count=2); expect 'bursty-traffic warehouses are serverless' not a count predicate — agent must interpret |  |
| `BP-044` | _(repo-level)_ | online state fetched (count=2); expect 'start small and scale up based on query latency' not a count predicate — agent must interpret |  |
| `BP-046` | _(repo-level)_ | online state fetched (count=2); expect 'at least two warehouses with distinct purpose tags (bi, adhoc)' not a count predicate — agent must interpret |  |
| `BP-047` | _(repo-level)_ | online check errored: SqlFailed (http 0) |  |
| `BP-048` | _(repo-level)_ | online check errored: SqlFailed (http 0) |  |
| `BP-048` | _(repo-level)_ | online state fetched (count=2); expect 'max_num_clusters >= ceil(peak_concurrent_queries / 10)' not a count predicate — agent must interpret |  |
| `BP-049` | _(repo-level)_ | online state fetched (count=2); expect 'PRO (non-serverless) warehouses have a justification tag or comment' not a count predicate — agent must interpret |  |
| `BP-050` | _(repo-level)_ | online check errored: SqlFailed (http 0) |  |
| `BP-051` | _(repo-level)_ | online state fetched (count=2); expect 'tags.custom_tags includes environment, owner, cost_center' not a count predicate — agent must interpret |  |
| `BP-060` | _(repo-level)_ | online check errored: SqlFailed (http 0) |  |
| `BP-078` | _(repo-level)_ | online check errored: SqlFailed (http 0) |  |
| `BP-176` | _(repo-level)_ | online check errored: not-found (http 404) |  |
| `BP-213` | _(repo-level)_ | online check errored: SqlFailed (http 0) |  |
| `BP-260` | _(repo-level)_ | online state fetched (count=47); expect 'clusters use LTS or current runtime, not deprecated versions' not a count predicate — agent must interpret |  |
| `BP-267` | _(repo-level)_ | online state fetched (count=5); expect 'one or more custom policies exist; users cannot create unconstrained clusters' not a count predicate — agent must interpret |  |
| `BP-273` | _(repo-level)_ | online count 1 does not satisfy == 0 |  |
| `BP-341` | _(repo-level)_ | online state fetched (count=1); expect 'workspaceDefaultCatalog set to a UC catalog (not 'hive_metastore')' not a count predicate — agent must interpret |  |
| `BP-381` | _(repo-level)_ | online state fetched (count=41); expect 'endpoints exist for prod models' not a count predicate — agent must interpret |  |
| `BP-389` | _(repo-level)_ | online check errored: not-found (http 404) |  |
| `BP-393` | _(repo-level)_ | online check errored: not-found (http 404) |  |
| `BP-397` | _(repo-level)_ | online state fetched (count=41); expect 'GPU endpoints accompanied by a justification tag' not a count predicate — agent must interpret |  |
| `BP-414` | _(repo-level)_ | online check errored: not-found (http 404) |  |
| `BP-433` | _(repo-level)_ | online check errored: SqlFailed (http 0) |  |
| `BP-549` | _(repo-level)_ | online state fetched (count=6); expect 'space.config.format_assistance == true' not a count predicate — agent must interpret |  |
| `BP-381` | `app/databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in app/databricks.yml |  |
| `BP-542` | `app/databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in app/databricks.yml |  |
| `BP-128` | `data/frozen_models/abt_buy/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `data/frozen_models/abt_buy/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `data/frozen_models/affiliations/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `data/frozen_models/affiliations/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `data/frozen_models/amazon_google/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `data/frozen_models/amazon_google/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `data/frozen_models/bpid/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `data/frozen_models/bpid/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `data/frozen_models/dblp_acm/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `data/frozen_models/dblp_acm/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `data/frozen_models/febrl4_half_all/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `data/frozen_models/febrl4_half_all/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `data/frozen_models/febrl4_half_no_ssn/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `data/frozen_models/febrl4_half_no_ssn/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `data/frozen_models/walmart_amazon/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `data/frozen_models/walmart_amazon/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `data/frozen_sources/src/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `data/frozen_sources/src/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `data/remote_models/20260919T230816Z/fresh_loaded/code/lakematch/engine.py:105` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `data/remote_models/20260919T230816Z/loaded/model/code/lakematch/engine.py:105` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `data/remote_models/20260920T051312Z/fresh_loaded/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `data/remote_models/20260920T051312Z/fresh_loaded/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `data/remote_models/20260920T051312Z/loaded/model/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `data/remote_models/20260920T051312Z/loaded/model/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `data/serverless_runs/20260920T042153Z-serverless_native-fixture/volume/loaded/model/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `data/serverless_runs/20260920T042153Z-serverless_native-fixture/volume/loaded/model/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `data/test-runs/20260921T092956Z/replay-v2/src/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `data/test-runs/20260921T092956Z/replay-v2/src/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `data/test-runs/20260921T092956Z/replay-v2/tools/run_candidate_pairs.py:135` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `data/test-runs/20260921T092956Z/replay-v2/tools/run_compact_features.py:187` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `data/test-runs/20260921T092956Z/replay-v2/tools/run_linkage_candidates.py:143` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `data/test-runs/20260921T092956Z/replay-v2/tools/run_methods.py:195` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-131` | `data/test-runs/20260921T092956Z/replay-v2/tools/serverless_canary.py:63` | file_grep matched pattern_any | Per-user experiment path — shared projects should use /Shared/<project>/... |
| `BP-128` | `data/test-runs/20260921T092956Z/replay-v2/tools/tracking_canary.py:76` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `data/test-runs/20260921T092956Z/replay/src/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `data/test-runs/20260921T092956Z/replay/src/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `data/test-runs/20260921T092956Z/replay/tools/run_candidate_pairs.py:135` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `data/test-runs/20260921T092956Z/replay/tools/run_compact_features.py:187` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `data/test-runs/20260921T092956Z/replay/tools/run_linkage_candidates.py:143` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `data/test-runs/20260921T092956Z/replay/tools/run_methods.py:195` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-131` | `data/test-runs/20260921T092956Z/replay/tools/serverless_canary.py:63` | file_grep matched pattern_any | Per-user experiment path — shared projects should use /Shared/<project>/... |
| `BP-128` | `data/test-runs/20260921T092956Z/replay/tools/tracking_canary.py:76` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-381` | `databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in databricks.yml |  |
| `BP-542` | `databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in databricks.yml |  |
| `BP-549` | `genie/build_space.py:2` | file_grep matched pattern_any | Python file uses Genie SDK markers but never references `format_assistance` (kwarg-style or dict-key) — set `format_assistance=True` on the space config (and pair with `entity_matching=True` per BP-550). |
| `BP-551` | `genie/build_space.py:2` | file_grep matched pattern_any | Python file uses Genie SDK markers but never references thumbnail / emoji / cover_image / icon. Per `rules/api_capabilities.yaml`, the upload endpoints PUT/POST `/api/2.0/genie/spaces/{id}/{thumbnail,image,icon,cover-image}` are unsupported (return 404), so set the thumbnail via the Genie UI after deploy and verify with `GET /api/2.0/genie/spaces/{id}` that the field is non-empty. |
| `BP-555` | `genie/build_space.py:214` | file_grep matched pattern_any | Python project declares `join_specs` but never sorts by `id` before POST. The server re-sorts on GET, so unsorted POSTs produce noisy round-trip diffs. Sort `join_specs` by `id` at author time. Note: this check skips JSON exports because those are already server-sorted (BP-555 ships only the source-side static check; the round-trip property is checked by api_get against a live workspace). |
| `BP-381` | `genie/databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in genie/databricks.yml |  |
| `BP-542` | `genie/databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in genie/databricks.yml |  |
| `BP-128` | `mlruns/1/models/m-0095bc01084d4124a55a76056be07d29/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-0095bc01084d4124a55a76056be07d29/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-01c41b734960404f99c29ad60626e244/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-01cae41c82a04190add473f28987bba1/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-0262df05e3794bfd8484c4751f282b24/artifacts/code/lakematch/engine.py:118` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-03593d02037046f88888f0786c0288be/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-03593d02037046f88888f0786c0288be/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-03716b05ef724fb7a98b0642dbb230fb/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-03716b05ef724fb7a98b0642dbb230fb/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-04002ec716214bca9e7bd9973e80ff86/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-049bc3d940b84777b2a97c3f5629eb31/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-05ac6674290a4ce0b7bfd4868189c5f0/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-05ac6674290a4ce0b7bfd4868189c5f0/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-07a507f90f204ac896506518be91721c/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-07a507f90f204ac896506518be91721c/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-07a57031cdfb4f40b0e9da1c07199b5d/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-086df63c16e3449fbd18368813347ea3/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-090eacfc87714fc2b50a0afd1dc3c28d/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-0cd0380b28434faa9cb1b59b488889a9/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-0d84b06eb2d84734a0df4efa3463aee9/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-0de058a3fdfc40d0be4e95bd4f451ded/artifacts/code/lakematch/engine.py:105` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-0f417a6cc2df4f049aa62c3237edd2ae/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-0f417a6cc2df4f049aa62c3237edd2ae/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-122ea745183e47e6b65e02bafe7facea/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-149ae1aa196c495e8292ed76b05fd87b/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-15bab251f9e848aca3c3d8284cdb19bc/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-15bab251f9e848aca3c3d8284cdb19bc/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-1a72dea76a1a4061b02e9e4f30def01f/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-1a72dea76a1a4061b02e9e4f30def01f/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-1a91707b9bec4dc895db492b33dd113c/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-1ac94a076a8c4c1bbcfdd58fb2c51088/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-1adade8502264a66b761604f5afd836b/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-1bb86b753d0e4985affbcec1090522b5/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-1bb86b753d0e4985affbcec1090522b5/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-1c025a51dc834ae2b831848ba83ca78f/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-1c6e471dc942457697e59cbf15692d06/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-1cc1af133705460b87f5377191180727/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-1d82c443906f4c96b293ca33ddb9b863/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-1d82c443906f4c96b293ca33ddb9b863/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-1df5fa99123048cd8c876e2f074c9f1d/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-1e169024069e415b9711f18d3f8c086b/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-1f0660a15ea64b2ca93276570aef5ca2/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-2173365cd0f34655a8b3b3194d645c47/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-2173365cd0f34655a8b3b3194d645c47/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-236640dd46884575a3945840cc712846/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-24288230043f4b04a32a63b69fc708d0/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-24288230043f4b04a32a63b69fc708d0/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-250aa4bb1a9e429aac4d9a6e769a4372/artifacts/code/lakematch/engine.py:105` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-253281e19fb846caa2b54f8a285b11c7/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-29f86ea4e03c47e199739810159bdfe3/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-2d2f40e7d4a047458e1d23a2260a0abb/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-2d5b0d09245e4cc9a13c792645cc8767/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-2dbab5ad8c2d434fbdfdd0b02f412ab8/artifacts/code/lakematch/engine.py:102` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-30e02cebd4e64cdea8af98ec3065db3a/artifacts/code/lakematch/engine.py:118` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-3231de69bbe64f2d895183d103eb4e13/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-32954df8d73040b8895261a95ac3ee82/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-32c3b66715f34b86a5541896e8c55197/artifacts/code/lakematch/engine.py:97` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-36332eda06ae47669c3d8886beec12b8/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-38cc0c5f8f094c02ad17ee77affc9aa5/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-391096ceb9134988b1d42fa34bc365d2/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-3af23ecf63b947849522db42f160b223/artifacts/code/lakematch/engine.py:118` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-3cfe36d6e68b47daab6614e7e1b14159/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-3cfe36d6e68b47daab6614e7e1b14159/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-3d2b4a4d414e430987a5652c421aaee7/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-3d2b4a4d414e430987a5652c421aaee7/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-418de89978cc47b6a161e057af589bb5/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-418de89978cc47b6a161e057af589bb5/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-455de5ecb27240cdbeaf7000f552ac9b/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-467239392a69488e843546e52307f523/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-47192e340d7d4ef18957da27593bd0b7/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-485eca5392d54b4e913b3d31d55b6324/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-4a9da794d3fa451b97ec1d69a5a39939/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-4acbbe326e614c439b927a72f3d4843a/artifacts/code/lakematch/engine.py:97` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-4bfdb7cecc3a4d37b5e099deed3881c1/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-4dbf6716db4149aa8d8d2243545a0883/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-4dbf6716db4149aa8d8d2243545a0883/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-5042307ec29544de9f963f958c25822c/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-5357715f462842dda3f15da8638851e2/artifacts/code/lakematch/engine.py:102` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-571af9e5328b47fbba229460ef9588ae/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-5891a569f73b4d55aa795d6b8d536a87/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-5930e39cb1d34018b703fe3eb3901525/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-5930e39cb1d34018b703fe3eb3901525/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-5995cda6e7824f548b4d0c473d72f7a9/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-5cf2f7db936e4589a0f869b4c5a24995/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-5e485e369cc141eeb2d96708228933b8/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-5e57f8e37c0540cb846f1b549cd28ba0/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-5e57f8e37c0540cb846f1b549cd28ba0/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-5e7d4120a3394768950e519fa4203d7e/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-5e7d4120a3394768950e519fa4203d7e/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-60960c55ad404bca868680a41dc41cd4/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-60a1b9a313514e52bef42d123a9e2636/artifacts/code/lakematch/engine.py:105` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-60b741da7c8d4355bee5f1abd01b8808/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-60e223994dcf4b83a5fa31b3c38c83f5/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-6225f0dd4c6647f59bf72f4f7b9be2d0/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-647056e77e5d4c80a1b38fc998822728/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-648aae9557d84b5c8075d6c32ddac055/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-65218ea95dcc4fb88d418754b3082cb3/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-65a707aae0184868a4576ea01a3160d1/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-65e66655e56545f7ae0aa54b20c20f5a/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-65f498201b2440ffb67746f19f66b187/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-67cad8da002b4cfca0750ccfb0c8eda0/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-67cad8da002b4cfca0750ccfb0c8eda0/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-690abf237e324d169aea77d26434006e/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-6a203e603b624fb1a5a725433b17c329/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-6a76d28c7cde42a59fd576c663c5d503/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-6af4fae7f8e04065aaf322180ccae13a/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-6af4fae7f8e04065aaf322180ccae13a/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-6bcaa1fcadf248c6b681aba795f64b40/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-6c10eeb398e14d07bbb06a9ac794eccb/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-6c10eeb398e14d07bbb06a9ac794eccb/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-6c3230b620b74228b647a92b43e740c0/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-6ca8a3d3c5064f3eb2cd79c650c55365/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-6d029e764c444de38cbd4faef08144ed/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-6d029e764c444de38cbd4faef08144ed/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-6e2816ac1718456c8411a50f55b34cda/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-6e7f638a16e441cabfbb86b7ecf5a2f0/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-6f422494bb834917aaaa6208c92f2b59/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-6f422494bb834917aaaa6208c92f2b59/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-703b2dfa80414908a6ba3b8e7420ef63/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-703b2dfa80414908a6ba3b8e7420ef63/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-7114d21e769f4e7789590e4a50628595/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| _…truncated at 200 rows…_ | | | |

### Info (1873)

| rule | file:line | detail | hint |
|---|---|---|---|
| `BP-002` | _(repo-level)_ | online check skipped: account-level endpoint (v1 is workspace-only) |  |
| `BP-004` | _(repo-level)_ | online check skipped: account-level endpoint (v1 is workspace-only) |  |
| `BP-005` | _(repo-level)_ | online check skipped: templated |  |
| `BP-006` | _(repo-level)_ | online check skipped: templated |  |
| `BP-007` | _(repo-level)_ | online state fetched (count=6); expect 'job.settings.run_as_user_name is service-principal applicationId (UUID), not user email' not a count predicate — agent must interpret |  |
| `BP-008` | _(repo-level)_ | online check skipped: templated |  |
| `BP-009` | _(repo-level)_ | online check skipped: templated |  |
| `BP-010` | _(repo-level)_ | online check skipped: templated |  |
| `BP-012` | _(repo-level)_ | online check skipped: templated |  |
| `BP-013` | _(repo-level)_ | online check skipped: templated |  |
| `BP-014` | _(repo-level)_ | online check skipped: templated |  |
| `BP-019` | _(repo-level)_ | online check skipped: templated |  |
| `BP-020` | _(repo-level)_ | online check skipped: templated |  |
| `BP-023` | _(repo-level)_ | online check skipped: templated |  |
| `BP-024` | _(repo-level)_ | online check skipped: templated |  |
| `BP-025` | _(repo-level)_ | online check skipped: templated |  |
| `BP-026` | _(repo-level)_ | online check skipped: templated |  |
| `BP-027` | _(repo-level)_ | online check skipped: templated |  |
| `BP-028` | _(repo-level)_ | online check skipped: templated |  |
| `BP-029` | _(repo-level)_ | online check skipped: templated |  |
| `BP-030` | _(repo-level)_ | online check skipped: templated |  |
| `BP-031` | _(repo-level)_ | online check skipped: templated |  |
| `BP-032` | _(repo-level)_ | online check skipped: templated |  |
| `BP-033` | _(repo-level)_ | online check skipped: templated |  |
| `BP-034` | _(repo-level)_ | online check skipped: templated |  |
| `BP-035` | _(repo-level)_ | online check skipped: templated |  |
| `BP-036` | _(repo-level)_ | online check skipped: templated |  |
| `BP-037` | _(repo-level)_ | online check skipped: templated |  |
| `BP-038` | _(repo-level)_ | online check skipped: templated |  |
| `BP-039` | _(repo-level)_ | online check skipped: templated |  |
| `BP-040` | _(repo-level)_ | online check skipped: templated |  |
| `BP-041` | _(repo-level)_ | online check skipped: templated |  |
| `BP-042` | _(repo-level)_ | online check skipped: templated |  |
| `BP-043` | _(repo-level)_ | online check skipped: templated |  |
| `BP-047` | _(repo-level)_ | online check skipped: templated |  |
| `BP-048` | _(repo-level)_ | online check skipped: templated |  |
| `BP-052` | _(repo-level)_ | online check skipped: templated |  |
| `BP-054` | _(repo-level)_ | online check skipped: templated |  |
| `BP-055` | _(repo-level)_ | online check skipped: templated |  |
| `BP-058` | _(repo-level)_ | online check skipped: templated |  |
| `BP-064` | _(repo-level)_ | online check skipped: templated |  |
| `BP-065` | _(repo-level)_ | online check skipped: templated |  |
| `BP-066` | _(repo-level)_ | online check skipped: templated |  |
| `BP-067` | _(repo-level)_ | online check skipped: templated |  |
| `BP-068` | _(repo-level)_ | online check skipped: templated |  |
| `BP-069` | _(repo-level)_ | online check skipped: templated |  |
| `BP-070` | _(repo-level)_ | online check skipped: templated |  |
| `BP-071` | _(repo-level)_ | online check skipped: templated |  |
| `BP-072` | _(repo-level)_ | online check skipped: templated |  |
| `BP-073` | _(repo-level)_ | online check skipped: templated |  |
| `BP-074` | _(repo-level)_ | online check skipped: templated |  |
| `BP-076` | _(repo-level)_ | online check skipped: templated |  |
| `BP-077` | _(repo-level)_ | online check skipped: templated |  |
| `BP-078` | _(repo-level)_ | online check skipped: templated |  |
| `BP-079` | _(repo-level)_ | online check skipped: templated |  |
| `BP-080` | _(repo-level)_ | online check skipped: templated |  |
| `BP-081` | _(repo-level)_ | online check skipped: templated |  |
| `BP-082` | _(repo-level)_ | online check skipped: templated |  |
| `BP-083` | _(repo-level)_ | online check skipped: templated |  |
| `BP-084` | _(repo-level)_ | online check skipped: templated |  |
| `BP-088` | _(repo-level)_ | online check skipped: templated |  |
| `BP-090` | _(repo-level)_ | online check skipped: templated |  |
| `BP-094` | _(repo-level)_ | online check skipped: templated |  |
| `BP-097` | _(repo-level)_ | online check skipped: templated |  |
| `BP-100` | _(repo-level)_ | online check skipped: templated SQL (placeholders unresolved) |  |
| `BP-103` | _(repo-level)_ | online check skipped: templated |  |
| `BP-104` | _(repo-level)_ | online check skipped: templated |  |
| `BP-105` | _(repo-level)_ | online check skipped: templated |  |
| `BP-106` | _(repo-level)_ | online check skipped: templated |  |
| `BP-107` | _(repo-level)_ | online check skipped: templated |  |
| `BP-108` | _(repo-level)_ | online check skipped: templated |  |
| `BP-109` | _(repo-level)_ | online check skipped: templated SQL (placeholders unresolved) |  |
| `BP-111` | _(repo-level)_ | online check skipped: templated |  |
| `BP-112` | _(repo-level)_ | online check skipped: templated |  |
| `BP-113` | _(repo-level)_ | online check skipped: templated |  |
| `BP-114` | _(repo-level)_ | online check skipped: templated |  |
| `BP-115` | _(repo-level)_ | online check skipped: templated |  |
| `BP-116` | _(repo-level)_ | online check skipped: templated |  |
| `BP-117` | _(repo-level)_ | online check skipped: templated |  |
| `BP-118` | _(repo-level)_ | online check skipped: templated |  |
| `BP-119` | _(repo-level)_ | online check skipped: templated |  |
| `BP-120` | _(repo-level)_ | online check skipped: templated |  |
| `BP-121` | _(repo-level)_ | online check skipped: templated |  |
| `BP-122` | _(repo-level)_ | online check skipped: templated |  |
| `BP-123` | _(repo-level)_ | online check skipped: templated |  |
| `BP-124` | _(repo-level)_ | online check skipped: templated |  |
| `BP-125` | _(repo-level)_ | online check skipped: templated |  |
| `BP-126` | _(repo-level)_ | online check skipped: templated |  |
| `BP-136` | _(repo-level)_ | online check skipped: templated |  |
| `BP-137` | _(repo-level)_ | online check skipped: templated |  |
| `BP-139` | _(repo-level)_ | online check skipped: templated |  |
| `BP-140` | _(repo-level)_ | file_present: no file matches glob **/{validate,validation}*.py |  |
| `BP-141` | _(repo-level)_ | online check skipped: templated |  |
| `BP-143` | _(repo-level)_ | online check skipped: templated |  |
| `BP-145` | _(repo-level)_ | online check skipped: templated |  |
| `BP-146` | _(repo-level)_ | online check skipped: templated |  |
| `BP-147` | _(repo-level)_ | online check skipped: templated |  |
| `BP-149` | _(repo-level)_ | online check skipped: templated |  |
| `BP-150` | _(repo-level)_ | online check skipped: templated |  |
| `BP-151` | _(repo-level)_ | online check skipped: templated |  |
| `BP-152` | _(repo-level)_ | online check skipped: templated |  |
| `BP-153` | _(repo-level)_ | online check skipped: templated |  |
| `BP-154` | _(repo-level)_ | online check skipped: templated |  |
| `BP-155` | _(repo-level)_ | online check skipped: templated |  |
| `BP-156` | _(repo-level)_ | online check skipped: templated |  |
| `BP-157` | _(repo-level)_ | file_present: no file matches glob **/{cleanup,prune}_experiments*.py |  |
| `BP-158` | _(repo-level)_ | online check skipped: templated |  |
| `BP-159` | _(repo-level)_ | online check skipped: templated |  |
| `BP-160` | _(repo-level)_ | online check skipped: templated |  |
| `BP-162` | _(repo-level)_ | online check skipped: templated |  |
| `BP-163` | _(repo-level)_ | online check skipped: templated |  |
| `BP-164` | _(repo-level)_ | online check skipped: templated |  |
| `BP-165` | _(repo-level)_ | online check skipped: templated |  |
| `BP-166` | _(repo-level)_ | online check skipped: templated |  |
| `BP-167` | _(repo-level)_ | online check skipped: templated |  |
| `BP-168` | _(repo-level)_ | online check skipped: templated |  |
| `BP-169` | _(repo-level)_ | online check skipped: templated |  |
| `BP-170` | _(repo-level)_ | online check skipped: templated |  |
| `BP-171` | _(repo-level)_ | online check skipped: templated SQL (placeholders unresolved) |  |
| `BP-172` | _(repo-level)_ | online check skipped: templated |  |
| `BP-173` | _(repo-level)_ | online check skipped: templated |  |
| `BP-174` | _(repo-level)_ | online check skipped: templated |  |
| `BP-175` | _(repo-level)_ | online check skipped: templated |  |
| `BP-176` | _(repo-level)_ | online check skipped: templated |  |
| `BP-177` | _(repo-level)_ | online check skipped: templated |  |
| `BP-178` | _(repo-level)_ | online check skipped: templated |  |
| `BP-179` | _(repo-level)_ | online check skipped: templated |  |
| `BP-180` | _(repo-level)_ | online check skipped: templated |  |
| `BP-181` | _(repo-level)_ | online check skipped: templated |  |
| `BP-182` | _(repo-level)_ | online check skipped: templated |  |
| `BP-183` | _(repo-level)_ | online check skipped: templated |  |
| `BP-184` | _(repo-level)_ | online check skipped: templated |  |
| `BP-185` | _(repo-level)_ | online check skipped: templated |  |
| `BP-186` | _(repo-level)_ | online check skipped: templated |  |
| `BP-187` | _(repo-level)_ | online check skipped: templated |  |
| `BP-188` | _(repo-level)_ | online check skipped: templated |  |
| `BP-189` | _(repo-level)_ | online check skipped: templated |  |
| `BP-190` | _(repo-level)_ | online check skipped: templated SQL (placeholders unresolved) |  |
| `BP-191` | _(repo-level)_ | online check skipped: templated |  |
| `BP-192` | _(repo-level)_ | online check skipped: templated |  |
| `BP-193` | _(repo-level)_ | online check skipped: templated SQL (placeholders unresolved) |  |
| `BP-194` | _(repo-level)_ | online check skipped: templated |  |
| `BP-195` | _(repo-level)_ | online check skipped: templated |  |
| `BP-196` | _(repo-level)_ | online check skipped: templated |  |
| `BP-197` | _(repo-level)_ | online check skipped: templated |  |
| `BP-198` | _(repo-level)_ | online check skipped: templated |  |
| `BP-199` | _(repo-level)_ | online state fetched (count=6); expect 'distinct spaces per audience (finance, marketing, ops) not one mega-space' not a count predicate — agent must interpret |  |
| `BP-200` | _(repo-level)_ | online check skipped: templated |  |
| `BP-201` | _(repo-level)_ | online check skipped: templated |  |
| `BP-202` | _(repo-level)_ | online check skipped: templated |  |
| `BP-203` | _(repo-level)_ | online check skipped: templated |  |
| `BP-204` | _(repo-level)_ | online check skipped: templated |  |
| `BP-205` | _(repo-level)_ | online check skipped: templated |  |
| `BP-206` | _(repo-level)_ | online check skipped: templated |  |
| `BP-207` | _(repo-level)_ | online check skipped: templated |  |
| `BP-208` | _(repo-level)_ | online check skipped: templated |  |
| `BP-209` | _(repo-level)_ | online check skipped: templated |  |
| `BP-212` | _(repo-level)_ | online check skipped: templated |  |
| `BP-214` | _(repo-level)_ | online check skipped: templated |  |
| `BP-214` | _(repo-level)_ | online check skipped: templated SQL (placeholders unresolved) |  |
| `BP-217` | _(repo-level)_ | online check skipped: templated |  |
| `BP-218` | _(repo-level)_ | online check skipped: templated |  |
| `BP-219` | _(repo-level)_ | online check skipped: templated |  |
| `BP-220` | _(repo-level)_ | online check skipped: templated |  |
| `BP-222` | _(repo-level)_ | online check skipped: templated |  |
| `BP-223` | _(repo-level)_ | online check skipped: templated |  |
| `BP-224` | _(repo-level)_ | online check skipped: templated |  |
| `BP-225` | _(repo-level)_ | online check skipped: templated |  |
| `BP-226` | _(repo-level)_ | online check skipped: templated |  |
| `BP-228` | _(repo-level)_ | online check skipped: templated |  |
| `BP-229` | _(repo-level)_ | online check skipped: templated |  |
| `BP-231` | _(repo-level)_ | online check skipped: templated |  |
| `BP-232` | _(repo-level)_ | online check skipped: templated |  |
| `BP-233` | _(repo-level)_ | online check skipped: templated |  |
| `BP-235` | _(repo-level)_ | online check skipped: templated |  |
| `BP-236` | _(repo-level)_ | online check skipped: templated |  |
| `BP-237` | _(repo-level)_ | online check skipped: templated |  |
| `BP-238` | _(repo-level)_ | online check skipped: templated |  |
| `BP-239` | _(repo-level)_ | online check skipped: templated |  |
| `BP-240` | _(repo-level)_ | online check skipped: templated |  |
| `BP-241` | _(repo-level)_ | online check skipped: templated |  |
| `BP-242` | _(repo-level)_ | online check skipped: templated |  |
| `BP-243` | _(repo-level)_ | online check skipped: templated |  |
| `BP-244` | _(repo-level)_ | online check skipped: templated |  |
| `BP-245` | _(repo-level)_ | online check skipped: templated |  |
| `BP-246` | _(repo-level)_ | online check skipped: templated |  |
| `BP-247` | _(repo-level)_ | online check skipped: templated |  |
| `BP-248` | _(repo-level)_ | online check skipped: templated |  |
| `BP-250` | _(repo-level)_ | online check skipped: templated |  |
| `BP-251` | _(repo-level)_ | online check skipped: templated |  |
| `BP-253` | _(repo-level)_ | online check skipped: templated |  |
| `BP-255` | _(repo-level)_ | online check skipped: templated |  |
| `BP-257` | _(repo-level)_ | online check skipped: templated |  |
| `BP-259` | _(repo-level)_ | online check skipped: templated |  |
| `BP-261` | _(repo-level)_ | online check skipped: templated |  |
| `BP-262` | _(repo-level)_ | online check skipped: templated |  |
| `BP-263` | _(repo-level)_ | online check skipped: templated |  |
| `BP-264` | _(repo-level)_ | online check skipped: templated |  |
| `BP-266` | _(repo-level)_ | online check skipped: templated |  |
| `BP-268` | _(repo-level)_ | online check skipped: templated |  |
| _…truncated at 200 rows…_ | | | |
