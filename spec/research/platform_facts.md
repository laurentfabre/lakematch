# Databricks platform facts for the clean-room matching engine

*Research digest, 2026-09-19, from official documentation (pages dated 2026-09-11) unless marked (inference) or
(unverified). Feeds `goals/goal_zingg_rewrite.md`. Naming drift: Genie spaces → **Genie Agents**; DABs → **Declarative
Automation Bundles**; Vector Search → **AI Search**; Lakehouse Monitoring → **Data profiling**; DLT → Lakeflow Spark
Declarative Pipelines (SDP).*

## DQX (databrickslabs.github.io/dqx)

- Data-quality framework for PySpark: row-level and dataset-level checks, criticality `error` (row goes to quarantine
  only) / `warn` (row goes to both), checks as code or YAML/JSON/Delta, `apply_checks_and_split` → valid + quarantined
  DataFrames with `_errors` / `_warnings` structs, profiler + rule generator, dashboards, streaming support.
- Version 0.16.0 (PyPI, 2026-08-13). Hard dependencies: `databricks-sdk`, `databricks-labs-blueprint`, pydantic, pyyaml,
  sqlalchemy. `pyspark` is not declared. Engine is constructed as `DQEngine(WorkspaceClient())`.
- **Licence: "Databricks License"** — use permitted "solely for the purposes of using the Licensed Materials within or
  connecting to the Databricks Services"; PyPI classifier "Other/Proprietary". Not OSI open source, not supported
  with SLAs. → optional adapter only; never vendored, never a mandatory dependency of the (Apache-2.0) engine; laptop mode needs a native fallback.
- In SDP: "does not use Expectations but DQX's own methods" — a view returns `apply_checks_by_metadata(df, checks)`,
  then `get_valid` / `get_invalid` feed the silver and quarantine datasets. For materialized views set static
  `ExtraParams(run_time_overwrite, run_id_overwrite)` so refresh stays incremental.
- Local: "Local Testing (Experimental)" with `MagicMock(spec=WorkspaceClient)`; only `apply_checks*`, `validate_checks`,
  `get_valid/invalid`, file-based `load/save_checks` work locally; nothing that saves to tables.
- Native expectations (Lakeflow only, absent from open-source SDP): SQL boolean, no Python, warn / drop / fail, metrics
  in the event log. Complementary to DQX (per-row reasons + quarantine).

## Photon

- Native C++ engine; falls back transparently per operation. Operators: scan, filter, project, hash aggregate / join /
  shuffle, nested-loop join, union, expand, sort, top-k, limit, **window**, Delta/Parquet write. Expression categories
  (not exhaustive): comparison, arithmetic, conditional, **string**, casts, aggregates, dates. Types include struct,
  array, map, collated string. **Generate (explode) is not in the operator list.**
- "Photon doesn't support UDFs, RDD APIs, or Dataset APIs." Stateless streaming only. No gain under ~2 s queries.
- Always on for serverless, SQL warehouses and serverless pipelines; default on for classic, toggle with
  `runtime_engine: PHOTON|STANDARD` (clusters/jobs) and `photon: true|false` (classic pipelines). Different DBU rate on
  classic (`product_features.is_photon`).
- Nothing says Spark ML *training* is accelerated (inference): only the DataFrame feature preparation.
- Check: query profile (serverless/warehouses: share of task time in Photon); Spark UI colours on classic.
- No per-function list is published: coverage of `levenshtein`, `soundex`, `regexp_*`, `explode`, `transform` /
  `aggregate` is (unverified) → measure with the query profile, never assume.

## Databricks Apps

- Python (Streamlit, Dash, Gradio, Flask, FastAPI) and Node (React/AppKit, Express…). Python 3.11, files ≤ 10 MB.
- Auth: app service principal (`DATABRICKS_CLIENT_ID/SECRET` injected) or on-behalf-of-user (`x-forwarded-access-token`,
  declared scopes such as `sql`, `genie`). Resources in `app.yaml` via `valueFrom`: SQL warehouse, Genie Agent,
  UC table/volume/function, serving endpoint, Lakebase, secret, MLflow experiment, job.
- Cost: Medium 0.5 DBU/h, Large 1 DBU/h, billed while running; stopped = free. Free Edition: 3 apps, auto-stop after
  24 h, restart any time.

## Genie in an app

- Add the Genie Agent as an app resource (`GENIE_SPACE_ID` from `valueFrom: genie-space`); call
  `w.genie.start_conversation_and_wait` / `create_message_and_wait`, or the GA Conversation API
  (`/api/2.0/genie/spaces/{id}/start-conversation`, `…/messages`, poll every 1–5 s up to 10 min, `…/query-result`).
  The caller needs the agent permission + USE CATALOG / USE SCHEMA / SELECT + CAN USE on a pro or serverless warehouse.
  Up to 50 tables per agent.
- **Billing since July 2026**: `billing_origin_product = 'GENIE'`; each user has 150 DBU/month free and usage is free
  until 2027-01-31; "service principals do not receive free monthly usage and are billed for all of their usage". The
  warehouse compute of generated queries is separate. → `genie.auth_mode: user` by default.
- Genie works on Free Edition (confirmed by Laurent, 2026-09-19; the Free Edition page also lists it). An explicit
  statement for the Conversation API from an app was not found (unverified).
  Agent Bricks (Knowledge Assistant, Supervisor Agent) is a different product; Knowledge Assistant is unsupported there.

## What bills on top → needs an off-switch

Serverless performance mode for pipelines · Photon on classic · Model Serving / Foundation Model APIs / `ai_query` and
task AI functions (not on classic SQL warehouses) · AI Search endpoint (bills while it exists) · Lakebase · Apps compute
· Genie (as above) · Agent Bricks · **predictive optimization (on by default for new accounts, billed as serverless
jobs; `ALTER … DISABLE PREDICTIVE OPTIMIZATION`)** · data quality monitoring (`DATA_QUALITY_MONITORING`) · LLM judges
in MLflow evaluation (`AGENT_EVALUATION`). Free of their own SKU: MLflow tracking, UC model registry, system tables
(you pay the query compute).

## Free Edition (the `fourth-pat` workspace)

Serverless only, no custom compute configuration, one 2X-Small SQL warehouse, 5 concurrent job tasks, **one active
pipeline per pipeline type**, 3 apps (24 h), one AI Search endpoint, one Lakebase project, no R/Scala, non-commercial
use only; exceeding fair use shuts compute down for the day (or month). LinkedIn verification unlocks **only**
outbound internet and limited serverless GPU. → **classic compute cannot be tested there**; nor can Photon toggles.

## MLflow

- Local: SQLite is the default backend (`sqlite:///mlflow.db`); the file store is in maintenance and **cannot host the
  model registry** → use SQLite on the laptop so aliases work. Same code with `MLFLOW_TRACKING_URI=databricks`.
- `mlflow.spark` saves the native Spark ML format and always a pyfunc flavour; the pipeline must emit `prediction`.
  Composite model: a `mlflow.pyfunc.PythonModel` (models-from-code) whose `artifacts` hold the Spark pipeline, the
  config and the label-set pointer; UC requires a signature; aliases via `set_registered_model_alias`,
  `models:/cat.schema.name@champion`; no stages.
- `mlflow.models.evaluate` on a static dataset (predictions + targets) with `make_metric` custom metrics; GenAI scorers
  are a separate, non-interoperable system. `mlflow.data.from_spark/load_delta` + `log_input` for dataset lineage.
- Serverless environment v4: `pyspark.ml` + `mlflow.spark` supported, 100 MB per model, 1 GB per session; ships
  `mlflow-skinny 2.22.0` (pin MLflow in the job environment if MLflow 3 APIs are used). `MLFLOW_DFS_TMP` must point to
  a UC volume there (from an MLflow issue, not from docs — unverified). No distributed ML training over Databricks Connect.

## One codebase for serverless, classic and laptop

- Serverless: Spark Connect only; no RDD, no `sparkContext`, no `_jvm`; `cache()`, `persist()`, `checkpoint()`,
  `CACHE TABLE` raise; global temp views unsupported; UDFs cannot reach the internet and are capped at 1 GB; only six
  Spark confs settable; `createDataFrame` ≤ 128 MB; no Spark UI (use the query profile).
- Connect semantics: lazy analysis (errors at execution), temp views resolved by name at execution (use unique names),
  wrap UDF definitions in factories, avoid repeated `df.schema` in loops. `pyspark.sql.utils.is_remote()` to branch.
  Run the test suite locally in both classic mode and `SparkSession.builder.remote("sc://localhost")`.
- `databricks-connect` conflicts with `pyspark` → separate virtualenvs for "laptop OSS Spark" and "laptop → serverless".
- Open-source SDP: `materialized_view`, `table`, `temporary_view`, `append_flow`, `create_streaming_table`,
  `create_sink`; no expectations, no AUTO CDC → keep those in a Databricks-only module. Flow code may not call
  actions; measured locally: `count()`, `df.columns` and MLlib `fit` are refused, Python/pandas UDFs and
  `model.transform` of a model loaded at import are accepted.
- Bundles: serverless job = `environments` + `environment_key`; classic = `job_clusters` with `runtime_engine`;
  pipelines `serverless: true|false`, `photon`; variables per target, complex variables for cluster specs; **no
  conditional resource inclusion** → feature toggles travel in the engine's own config file and job parameters.
