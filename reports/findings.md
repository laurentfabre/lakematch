# vibe-doctor scan — findings

- **target**: `/Users/laurent.fabre/Projects/Claude/lakematch/.`
- **rules**: `/Users/laurent.fabre/.local/share/vibe-doctor/best-practices.yaml`
- **rules in catalog**: 569
- **rules with offline checks**: 181
- **rules fired**: 45
- **rules skipped (online-only)**: 384
- **rules skipped (transcript-only)**: 4
- **rules skipped (language-scope)**: 21
- **files scanned**: 9127
- **bytes scanned**: 560002867
- **bundle yaml files skipped**: 0
- **yaml_key checks unsupported**: 32
- **findings**: 1687

## Severity breakdown

| severity | count |
|---|---|
| error | 0 |
| warn | 297 |
| info | 1390 |

## Top rules

| rule | severity | title | hits |
|---|---|---|---|
| `BP-128` | warn | Log parameters, metrics, and artifacts for every run. | 212 |
| `BP-101` | warn | Implement idempotent pipelines: re-running should not duplicate data. | 68 |
| `BP-542` | warn | Tag model serving endpoints with cost_center / team / environment so per-endpoint DBU lands on the right budget owner. | 2 |
| `BP-381` | warn | Use Mosaic AI Model Serving for deploying models — it provides managed, scalable endpoints. | 2 |
| `BP-549` | warn | Enable Genie format assistance — without it, Genie returns raw SQL output instead of formatted answers, and downstream agents (chat panes, briefings) lose the structured shape they need. | 2 |
| `BP-551` | warn | Set a Genie space thumbnail (or emoji / cover_image) — bare spaces show as identical tiles in the Genie picker, which kills the per-persona visual cue customers expect at workshop time. | 2 |
| `BP-559` | warn | Declare `instructions.join_specs[]` when a Genie space references ≥2 tables — without declared joins, Genie writes ad-hoc JOIN SQL that ignores cardinality and produces row-explosion bugs (the BP-554 live-introspection lesson is moot if joins aren't pre-declared). | 1 |
| `BP-562` | warn | Every `sql_snippets[*]` (filter / expression / measure) ships at least one `synonyms[]` entry — without synonyms, Genie can't map user phrasing (`brake rate`, `BRAKE share`) to the named snippet, defeating the entire point of declaring the snippet. | 1 |
| `BP-131` | warn | Organize experiments by project/team using workspace folder structure. | 1 |
| `BP-548` | warn | Add `synonyms=[...]` to every column with a description in a Genie space — without synonyms, Genie's NL→SQL grounding drops business terms (e.g. "customer" never resolves to `cust_id`). | 1 |
| `BP-555` | warn | Author Genie space artifacts in round-trip-stable form — `join_specs[*]` sorted by `id`, `text_instructions[]` as one consolidated block, `version: 2` — so POST-then-GET produces zero diff and future edits don't churn. | 1 |
| `BP-558` | warn | Populate `instructions.example_question_sqls[]` on every Genie space — these are the curated example queries Genie shows alongside curated_questions; without them, the model has nothing to ground new questions against. | 1 |
| `BP-561` | warn | Populate `instructions.sql_snippets` with reusable filters, expressions, and measures — these are the named SQL fragments Genie composes user-questions from; without them, every answer rebuilds aggregations from scratch and answer style drifts across questions. | 1 |
| `BP-556` | warn | Ship at least one `ask_genie` smoke-test artifact per Genie space — a real natural-language question whose row count is cross-checked against direct SQL via the warehouse. Round-trip GET alone misses binding/entity-match/join failures; only a real NL roundtrip catches them. | 1 |
| `BP-554` | warn | Introspect every Genie-referenced table live (DESCRIBE / COUNT / COLLECT_SET on enum columns) before drafting SQL — without it, sample_questions and CSEs are written against assumed cardinality and enum values, which is the #1 source of CRITICAL Genie review findings (non-unique join keys, unknown enum values, zero-row edge cases). | 1 |
| `BP-211` | info | Enable liquid clustering instead of traditional partitioning for new tables. | 500 |
| `BP-557` | info | Relabel the UI surface for known data artefacts — when a column or family is known to be a math/data artefact (e.g. clean family flagged CRITICAL due to drift-score artefact), reword sample_questions and instructions to neutral terms (`monitored families` not `adversarial families`; `configured threshold and alert status` not `breached threshold`) rather than rewiring the schema. | 230 |
| `BP-132` | info | Log input datasets with mlflow.log_input() for reproducibility. | 209 |
| `BP-394` | info | Implement model signatures and input validation on serving endpoints. | 209 |
| `BP-129` | info | Register production models in Unity Catalog Model Registry. | 209 |
| `BP-007` | info | Use service principals for all jobs and automation. | 3 |
| `BP-109` | info | Monitor pipeline freshness: alert if a pipeline hasn't completed within its SLA. | 3 |
| `BP-047` | info | Set max scaling (max clusters) to control cost ceilings. | 2 |
| `BP-001` | info | Make Unity Catalog the default governance plane for all data and AI assets. | 2 |
| `BP-303` | info | Separate dev, staging, and prod environments at the workspace or catalog level. | 2 |

## Findings

### Error (0)

_No findings at this severity._

### Warn (297)

| rule | file:line | detail | hint |
|---|---|---|---|
| `BP-556` | _(repo-level)_ | file_present: no file matches glob **/{tests,smoke,validation}/**/{ask_genie,genie_smoke,genie_validate}*.{py,sql,md,yaml,yml,json} | No `ask_genie` smoke-test artifact found. Add one NL question per space under tests/ or smoke/, recording the question text, the Genie row count, and the equivalent direct-SQL row count. |
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
| `BP-381` | `databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in databricks.yml |  |
| `BP-542` | `databricks.yml` | yaml_key 'resources.model_serving_endpoints' not declared in databricks.yml |  |
| `BP-549` | `genie/build_space.py:2` | file_grep matched pattern_any | Python file uses Genie SDK markers but never references `format_assistance` (kwarg-style or dict-key) — set `format_assistance=True` on the space config (and pair with `entity_matching=True` per BP-550). |
| `BP-551` | `genie/build_space.py:2` | file_grep matched pattern_any | Python file uses Genie SDK markers but never references thumbnail / emoji / cover_image / icon. Per `rules/api_capabilities.yaml`, the upload endpoints PUT/POST `/api/2.0/genie/spaces/{id}/{thumbnail,image,icon,cover-image}` are unsupported (return 404), so set the thumbnail via the Genie UI after deploy and verify with `GET /api/2.0/genie/spaces/{id}` that the field is non-empty. |
| `BP-555` | `genie/build_space.py:214` | file_grep matched pattern_any | Python project declares `join_specs` but never sorts by `id` before POST. The server re-sorts on GET, so unsorted POSTs produce noisy round-trip diffs. Sort `join_specs` by `id` at author time. Note: this check skips JSON exports because those are already server-sorted (BP-555 ships only the source-side static check; the round-trip property is checked by api_get against a live workspace). |
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
| `BP-128` | `mlruns/1/models/m-1c025a51dc834ae2b831848ba83ca78f/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-1c6e471dc942457697e59cbf15692d06/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-1cc1af133705460b87f5377191180727/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-1d82c443906f4c96b293ca33ddb9b863/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-1d82c443906f4c96b293ca33ddb9b863/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-1df5fa99123048cd8c876e2f074c9f1d/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-1e169024069e415b9711f18d3f8c086b/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-1f0660a15ea64b2ca93276570aef5ca2/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
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
| `BP-101` | `mlruns/1/models/m-7114d21e769f4e7789590e4a50628595/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-719a71d21f494ed1baac328e05cbb5c1/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-727d45525c3b4cda83b61534cebabfc6/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-75ee248887b64dd692646b8bb728338e/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-7850d7671f9545be9a7ccfdafaf45976/artifacts/code/lakematch/engine.py:118` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-79dd8da193a0445d9d62dfb407058338/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-7b13417aef34472d819ebdb74523a43d/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-7b13417aef34472d819ebdb74523a43d/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-7caad2a57f2c439aab4e7175710a8b24/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-7d77f2bbac2a4922ae4b1ccfbd34ec1e/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-7e11d9c81b714d99a3ef4841d6377860/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-7ebe7edad68f42d39c58237fa6a27a74/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-812f51f383da447bb6b6f80864ac921e/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-8138506d539d49af8393fdde43209e1a/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-81d2764ff0804ac695b81477dcbd4287/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-81d2764ff0804ac695b81477dcbd4287/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-81e6c739f3c54b9094e911d024090ad2/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-81e6c739f3c54b9094e911d024090ad2/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-829d6e389298474abc14419ea36975d7/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-829d6e389298474abc14419ea36975d7/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-85b1b0a8c11b44eba69db73e31e7aef9/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-8688d7aaf97f4bf3a297125590da86d2/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-8814d408b5b54eaf8456633f9b08541a/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-893963f0df56483ca936246d1eb1e759/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-8bc4533bd012484d9b5c505b11726c2a/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-8c76aff8f2ec4d4ab997e1d1df25bec7/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-8d4152a0d2f24e6f95102840f009d4be/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-8d964a48fbab456898e4317c775eb78d/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-8d964a48fbab456898e4317c775eb78d/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-8e0eabd407ea4965a83e5d0c1384219b/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-8ef94e76cef44b2ca45da5f9c1233e77/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-8fc4e96aa09b4e8283b10a4e0a84774c/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-91524089eb5b442dbe9f1ca4b848f3af/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-91524089eb5b442dbe9f1ca4b848f3af/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-924e6c9034aa4dd3b572881e71c52554/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-925a8266aa5449c89c573812033bd750/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-961dfaea35fd477bbb3a7381ad456766/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-961dfaea35fd477bbb3a7381ad456766/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-99443fc4514140b6af80f07430d902ef/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-9c839f4ac3264e5fbf4f4495e8571c2e/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-9c839f4ac3264e5fbf4f4495e8571c2e/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-9d4bbdf177a742ec9d09fe1f3bfc8538/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-9ec3ec10758c43058eefba43ccc3e6d7/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-9ec3ec10758c43058eefba43ccc3e6d7/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-9f8f6a4186e341ae887f642117c03add/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-9f8f6a4186e341ae887f642117c03add/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-a002f0f0dea24f8bb8873d7b279c18e1/artifacts/code/lakematch/engine.py:118` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-a02da8cf0bf846cfb43889b5527dd5de/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-128` | `mlruns/1/models/m-a6d0fc38091847a590a9c1261358037c/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| `BP-101` | `mlruns/1/models/m-a6d0fc38091847a590a9c1261358037c/artifacts/code/lakematch/publication.py:113` | file_grep matched pattern_any | Plain INSERT INTO without MERGE or INSERT OVERWRITE — non-idempotent under retry |
| `BP-128` | `mlruns/1/models/m-a71da44dd2ab42bf8a79b93a34ca0966/artifacts/code/lakematch/engine.py:131` | file_grep matched pattern_any | start_run without logging is nearly empty |
| _…truncated at 200 rows…_ | | | |

### Info (1390)

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
| `BP-557` | `data/frozen_models/abt_buy/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `data/frozen_models/abt_buy/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `data/frozen_models/abt_buy/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `data/frozen_models/abt_buy/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `data/frozen_models/affiliations/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `data/frozen_models/affiliations/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `data/frozen_models/affiliations/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `data/frozen_models/affiliations/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `data/frozen_models/amazon_google/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `data/frozen_models/amazon_google/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `data/frozen_models/amazon_google/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `data/frozen_models/amazon_google/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `data/frozen_models/bpid/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `data/frozen_models/bpid/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `data/frozen_models/bpid/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `data/frozen_models/bpid/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `data/frozen_models/dblp_acm/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `data/frozen_models/dblp_acm/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `data/frozen_models/dblp_acm/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `data/frozen_models/dblp_acm/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `data/frozen_models/febrl4_half_all/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `data/frozen_models/febrl4_half_all/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `data/frozen_models/febrl4_half_all/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `data/frozen_models/febrl4_half_all/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `data/frozen_models/febrl4_half_no_ssn/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `data/frozen_models/febrl4_half_no_ssn/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `data/frozen_models/febrl4_half_no_ssn/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `data/frozen_models/febrl4_half_no_ssn/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `data/frozen_models/walmart_amazon/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `data/frozen_models/walmart_amazon/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `data/frozen_models/walmart_amazon/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `data/frozen_models/walmart_amazon/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `data/frozen_sources/src/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `data/frozen_sources/src/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `data/frozen_sources/src/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `data/frozen_sources/src/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `data/remote_models/20260919T225721Z/fresh_loaded/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `data/remote_models/20260919T225721Z/fresh_loaded/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `data/remote_models/20260919T225721Z/fresh_loaded/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `data/remote_models/20260919T225721Z/fresh_loaded/code/lakematch/tracking.py:190` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `data/remote_models/20260919T225721Z/loaded/model/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `data/remote_models/20260919T225721Z/loaded/model/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `data/remote_models/20260919T225721Z/loaded/model/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `data/remote_models/20260919T225721Z/loaded/model/code/lakematch/tracking.py:190` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `data/remote_models/20260919T230816Z/fresh_loaded/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `data/remote_models/20260919T230816Z/fresh_loaded/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `data/remote_models/20260919T230816Z/fresh_loaded/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `data/remote_models/20260919T230816Z/fresh_loaded/code/lakematch/tracking.py:190` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `data/remote_models/20260919T230816Z/loaded/model/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `data/remote_models/20260919T230816Z/loaded/model/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `data/remote_models/20260919T230816Z/loaded/model/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `data/remote_models/20260919T230816Z/loaded/model/code/lakematch/tracking.py:190` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `data/remote_models/20260920T051312Z/fresh_loaded/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `data/remote_models/20260920T051312Z/fresh_loaded/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `data/remote_models/20260920T051312Z/fresh_loaded/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `data/remote_models/20260920T051312Z/fresh_loaded/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `data/remote_models/20260920T051312Z/loaded/model/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `data/remote_models/20260920T051312Z/loaded/model/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `data/remote_models/20260920T051312Z/loaded/model/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `data/remote_models/20260920T051312Z/loaded/model/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `data/serverless_runs/20260920T042153Z-serverless_native-fixture/volume/loaded/model/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `data/serverless_runs/20260920T042153Z-serverless_native-fixture/volume/loaded/model/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `data/serverless_runs/20260920T042153Z-serverless_native-fixture/volume/loaded/model/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `data/serverless_runs/20260920T042153Z-serverless_native-fixture/volume/loaded/model/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-001` | `databricks.yml` | yaml_key 'bundle.targets' not declared in databricks.yml |  |
| `BP-007` | `databricks.yml` | yaml_key 'resources.jobs.frozen_pipeline.run_as' not declared in databricks.yml |  |
| `BP-007` | `databricks.yml` | yaml_key 'resources.jobs.cluster_fixture.run_as' not declared in databricks.yml |  |
| `BP-047` | `databricks.yml` | yaml_key 'resources.sql_warehouses' not declared in databricks.yml |  |
| `BP-098` | `databricks.yml` | yaml_key 'resources.pipelines.matching.clusters' not declared in databricks.yml |  |
| `BP-109` | `databricks.yml` | yaml_key 'resources.jobs.frozen_pipeline.tasks[0].depends_on' not declared in databricks.yml |  |
| `BP-109` | `databricks.yml` | yaml_key 'resources.jobs.cluster_fixture.tasks[0].depends_on' not declared in databricks.yml |  |
| `BP-303` | `databricks.yml` | yaml_key 'targets.prod' not declared in databricks.yml |  |
| `BP-211` | `mlruns/1/models/m-0095bc01084d4124a55a76056be07d29/artifacts/code/lakematch/blocking.py:101` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-0095bc01084d4124a55a76056be07d29/artifacts/code/lakematch/candidates.py:77` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-0095bc01084d4124a55a76056be07d29/artifacts/code/lakematch/cluster_job.py:79` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-0095bc01084d4124a55a76056be07d29/artifacts/code/lakematch/clustering.py:106` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-0095bc01084d4124a55a76056be07d29/artifacts/code/lakematch/decision.py:19` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-0095bc01084d4124a55a76056be07d29/artifacts/code/lakematch/quality/native.py:36` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-557` | `mlruns/1/models/m-0095bc01084d4124a55a76056be07d29/artifacts/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `mlruns/1/models/m-0095bc01084d4124a55a76056be07d29/artifacts/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `mlruns/1/models/m-0095bc01084d4124a55a76056be07d29/artifacts/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `mlruns/1/models/m-0095bc01084d4124a55a76056be07d29/artifacts/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-211` | `mlruns/1/models/m-01c41b734960404f99c29ad60626e244/artifacts/code/lakematch/blocking.py:101` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-01c41b734960404f99c29ad60626e244/artifacts/code/lakematch/candidates.py:77` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-01c41b734960404f99c29ad60626e244/artifacts/code/lakematch/clustering.py:94` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-01c41b734960404f99c29ad60626e244/artifacts/code/lakematch/decision.py:19` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-01c41b734960404f99c29ad60626e244/artifacts/code/lakematch/quality/native.py:36` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-557` | `mlruns/1/models/m-01c41b734960404f99c29ad60626e244/artifacts/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `mlruns/1/models/m-01c41b734960404f99c29ad60626e244/artifacts/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `mlruns/1/models/m-01c41b734960404f99c29ad60626e244/artifacts/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `mlruns/1/models/m-01c41b734960404f99c29ad60626e244/artifacts/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `mlruns/1/models/m-01cae41c82a04190add473f28987bba1/artifacts/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `mlruns/1/models/m-01cae41c82a04190add473f28987bba1/artifacts/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `mlruns/1/models/m-01cae41c82a04190add473f28987bba1/artifacts/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `mlruns/1/models/m-01cae41c82a04190add473f28987bba1/artifacts/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `mlruns/1/models/m-0262df05e3794bfd8484c4751f282b24/artifacts/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `mlruns/1/models/m-0262df05e3794bfd8484c4751f282b24/artifacts/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `mlruns/1/models/m-0262df05e3794bfd8484c4751f282b24/artifacts/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `mlruns/1/models/m-0262df05e3794bfd8484c4751f282b24/artifacts/code/lakematch/tracking.py:190` | file_grep matched pattern_any | UC registry URI set |
| `BP-211` | `mlruns/1/models/m-03593d02037046f88888f0786c0288be/artifacts/code/lakematch/blocking.py:101` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-03593d02037046f88888f0786c0288be/artifacts/code/lakematch/candidates.py:77` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-03593d02037046f88888f0786c0288be/artifacts/code/lakematch/cluster_job.py:79` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-03593d02037046f88888f0786c0288be/artifacts/code/lakematch/clustering.py:106` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-03593d02037046f88888f0786c0288be/artifacts/code/lakematch/decision.py:19` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-03593d02037046f88888f0786c0288be/artifacts/code/lakematch/quality/native.py:36` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-557` | `mlruns/1/models/m-03593d02037046f88888f0786c0288be/artifacts/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `mlruns/1/models/m-03593d02037046f88888f0786c0288be/artifacts/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `mlruns/1/models/m-03593d02037046f88888f0786c0288be/artifacts/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `mlruns/1/models/m-03593d02037046f88888f0786c0288be/artifacts/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `mlruns/1/models/m-03716b05ef724fb7a98b0642dbb230fb/artifacts/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `mlruns/1/models/m-03716b05ef724fb7a98b0642dbb230fb/artifacts/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `mlruns/1/models/m-03716b05ef724fb7a98b0642dbb230fb/artifacts/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `mlruns/1/models/m-03716b05ef724fb7a98b0642dbb230fb/artifacts/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-211` | `mlruns/1/models/m-04002ec716214bca9e7bd9973e80ff86/artifacts/code/lakematch/blocking.py:101` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-04002ec716214bca9e7bd9973e80ff86/artifacts/code/lakematch/candidates.py:77` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-04002ec716214bca9e7bd9973e80ff86/artifacts/code/lakematch/clustering.py:94` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-04002ec716214bca9e7bd9973e80ff86/artifacts/code/lakematch/decision.py:19` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-04002ec716214bca9e7bd9973e80ff86/artifacts/code/lakematch/quality/native.py:36` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-557` | `mlruns/1/models/m-04002ec716214bca9e7bd9973e80ff86/artifacts/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `mlruns/1/models/m-04002ec716214bca9e7bd9973e80ff86/artifacts/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `mlruns/1/models/m-04002ec716214bca9e7bd9973e80ff86/artifacts/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `mlruns/1/models/m-04002ec716214bca9e7bd9973e80ff86/artifacts/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `mlruns/1/models/m-049bc3d940b84777b2a97c3f5629eb31/artifacts/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `mlruns/1/models/m-049bc3d940b84777b2a97c3f5629eb31/artifacts/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `mlruns/1/models/m-049bc3d940b84777b2a97c3f5629eb31/artifacts/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `mlruns/1/models/m-049bc3d940b84777b2a97c3f5629eb31/artifacts/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-211` | `mlruns/1/models/m-05ac6674290a4ce0b7bfd4868189c5f0/artifacts/code/lakematch/blocking.py:101` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-05ac6674290a4ce0b7bfd4868189c5f0/artifacts/code/lakematch/candidates.py:77` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-05ac6674290a4ce0b7bfd4868189c5f0/artifacts/code/lakematch/cluster_job.py:79` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-05ac6674290a4ce0b7bfd4868189c5f0/artifacts/code/lakematch/clustering.py:106` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-05ac6674290a4ce0b7bfd4868189c5f0/artifacts/code/lakematch/decision.py:19` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-05ac6674290a4ce0b7bfd4868189c5f0/artifacts/code/lakematch/quality/native.py:36` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-557` | `mlruns/1/models/m-05ac6674290a4ce0b7bfd4868189c5f0/artifacts/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `mlruns/1/models/m-05ac6674290a4ce0b7bfd4868189c5f0/artifacts/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `mlruns/1/models/m-05ac6674290a4ce0b7bfd4868189c5f0/artifacts/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `mlruns/1/models/m-05ac6674290a4ce0b7bfd4868189c5f0/artifacts/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `mlruns/1/models/m-07a507f90f204ac896506518be91721c/artifacts/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `mlruns/1/models/m-07a507f90f204ac896506518be91721c/artifacts/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `mlruns/1/models/m-07a507f90f204ac896506518be91721c/artifacts/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `mlruns/1/models/m-07a507f90f204ac896506518be91721c/artifacts/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `mlruns/1/models/m-07a57031cdfb4f40b0e9da1c07199b5d/artifacts/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `mlruns/1/models/m-07a57031cdfb4f40b0e9da1c07199b5d/artifacts/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `mlruns/1/models/m-07a57031cdfb4f40b0e9da1c07199b5d/artifacts/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `mlruns/1/models/m-07a57031cdfb4f40b0e9da1c07199b5d/artifacts/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `mlruns/1/models/m-086df63c16e3449fbd18368813347ea3/artifacts/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `mlruns/1/models/m-086df63c16e3449fbd18368813347ea3/artifacts/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `mlruns/1/models/m-086df63c16e3449fbd18368813347ea3/artifacts/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `mlruns/1/models/m-086df63c16e3449fbd18368813347ea3/artifacts/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-211` | `mlruns/1/models/m-090eacfc87714fc2b50a0afd1dc3c28d/artifacts/code/lakematch/blocking.py:101` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-090eacfc87714fc2b50a0afd1dc3c28d/artifacts/code/lakematch/candidates.py:77` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-090eacfc87714fc2b50a0afd1dc3c28d/artifacts/code/lakematch/clustering.py:94` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-090eacfc87714fc2b50a0afd1dc3c28d/artifacts/code/lakematch/decision.py:19` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-090eacfc87714fc2b50a0afd1dc3c28d/artifacts/code/lakematch/quality/native.py:36` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-557` | `mlruns/1/models/m-090eacfc87714fc2b50a0afd1dc3c28d/artifacts/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `mlruns/1/models/m-090eacfc87714fc2b50a0afd1dc3c28d/artifacts/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `mlruns/1/models/m-090eacfc87714fc2b50a0afd1dc3c28d/artifacts/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `mlruns/1/models/m-090eacfc87714fc2b50a0afd1dc3c28d/artifacts/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-211` | `mlruns/1/models/m-0cd0380b28434faa9cb1b59b488889a9/artifacts/code/lakematch/blocking.py:101` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-0cd0380b28434faa9cb1b59b488889a9/artifacts/code/lakematch/candidates.py:77` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-0cd0380b28434faa9cb1b59b488889a9/artifacts/code/lakematch/clustering.py:94` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-0cd0380b28434faa9cb1b59b488889a9/artifacts/code/lakematch/decision.py:19` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-0cd0380b28434faa9cb1b59b488889a9/artifacts/code/lakematch/quality/native.py:36` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-557` | `mlruns/1/models/m-0cd0380b28434faa9cb1b59b488889a9/artifacts/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `mlruns/1/models/m-0cd0380b28434faa9cb1b59b488889a9/artifacts/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `mlruns/1/models/m-0cd0380b28434faa9cb1b59b488889a9/artifacts/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `mlruns/1/models/m-0cd0380b28434faa9cb1b59b488889a9/artifacts/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-557` | `mlruns/1/models/m-0d84b06eb2d84734a0df4efa3463aee9/artifacts/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `mlruns/1/models/m-0d84b06eb2d84734a0df4efa3463aee9/artifacts/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| `BP-394` | `mlruns/1/models/m-0d84b06eb2d84734a0df4efa3463aee9/artifacts/code/lakematch/tracking.py:113` | file_grep matched pattern_any | Model signature set — good |
| `BP-129` | `mlruns/1/models/m-0d84b06eb2d84734a0df4efa3463aee9/artifacts/code/lakematch/tracking.py:196` | file_grep matched pattern_any | UC registry URI set |
| `BP-211` | `mlruns/1/models/m-0de058a3fdfc40d0be4e95bd4f451ded/artifacts/code/lakematch/candidates.py:69` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-0de058a3fdfc40d0be4e95bd4f451ded/artifacts/code/lakematch/decision.py:19` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-211` | `mlruns/1/models/m-0de058a3fdfc40d0be4e95bd4f451ded/artifacts/code/lakematch/quality/native.py:36` | file_grep matched pattern_any | partitionBy() in DataFrame write — prefer Delta CLUSTER BY |
| `BP-557` | `mlruns/1/models/m-0de058a3fdfc40d0be4e95bd4f451ded/artifacts/code/lakematch/tracking.py:1` | file_grep matched pattern_any | Python file acknowledges a data artefact in a comment but the user-visible strings (sample_questions, instructions) still use loaded labels. Relabel the surface to neutral terms — same defensibility, no architectural rewire. (Severity info, so the broader glob is acceptable even with some non-Genie false positives — the recommendation applies generally.) |
| `BP-132` | `mlruns/1/models/m-0de058a3fdfc40d0be4e95bd4f451ded/artifacts/code/lakematch/tracking.py:102` | file_grep matched pattern_any | mlflow.log_input() used — good for dataset lineage |
| _…truncated at 200 rows…_ | | | |
