# lakematch

*An entity-resolution engine for the lakehouse: one PySpark codebase for a laptop, Databricks serverless and
classic compute. Apache-2.0. **Private repository** — not for publication.*

## What / why

Matching, linking and mastering records with Spark SQL built-ins only (no JVM code, no UDF on a default path), inside
Spark Declarative Pipelines where the platform allows it, tracked in MLflow, with a human arbitration app (APX) and a
Genie agent. The full specification, the nine bounded phases ZR-1..9 and the ledger of the 28 design decisions are in
[`spec/BRIEF.md`](spec/BRIEF.md).

**State on 2026-09-20: ZR-1, ZR-2, ZR-4 and ZR-5 pass on the current source.** The engine includes YAML configuration,
native quality checks, bounded IDF candidates, comparison features, MLlib estimators and deterministic links.
The full classic local Spark and Spark Connect suites each pass the same 130 tests with no skips.
Earlier offline CLI, serverless model registration and fresh-task reload checks passed.
Typed native comparisons, optional similarities and an offline embedding provider are implemented;
see the [feature contract](bench/FEATURES.md) and measured [ablations](bench/ABLATION.md).
Frozen FEBRL confirmation passed at F1 0.9889 (all fields, 29.19s) and 0.9868 (SSN hidden, 27.30s).
The scale ladder completed through 100,000 records; the million-record run exhausted the fixed JVM heap
during candidate materialization. [Benchmarks](bench/BENCHMARKS.md) and [scale limits](bench/SCALE.md)
retain the measurements. Later phase acceptance is pending. [goal.md](goal.md) is the authoritative acceptance ledger;
[bench/ENGINE.md](bench/ENGINE.md) records development evidence and limitations.
Both DQX and native/all-paid-off serverless pipelines reproduce the frozen FEBRL F1 values exactly and quarantine
the seeded bad rows; remaining remote gates are tracked in [serverless evidence](bench/SERVERLESS.md).
`lakematch bench --all` executed eight exact frozen-model replays, the original-FEBRL diagnostic and both clustering comparisons, then stopped at the retained million-record failure. Full campaign acceptance remains blocked; `--plan` previews its stages.
Composite MLflow tracking and CLI integration are verified locally and on FEVM;
[model acceptance](bench/MODELS.md) records the evidence. The selected workspace explicitly
rejects classic compute, so ZR-9 remains parked; the remaining phases are pending.

## Run locally

Use Python 3.12 and Java 17. Install the private package and prepare the public synthetic corpus once:

```bash
uv venv --python 3.12
uv pip install -e '.[dev,connect,bench]'
source .venv/bin/activate
python tools/prepare_febrl.py
lakematch doctor --config examples/febrl4.yaml
lakematch run --config examples/febrl4.yaml
```

The example uses development truth labels, not held-out benchmark labels. It writes Parquet links and quarantine
rows under `data/febrl4/output`, plus runtime and budget metrics. `examples/synthetic.yaml` is a small fixture.
Every run logs its enabled paid features; laptop configs reject paid integrations.

New configurations default to MinHash retrieval, Levenshtein, IDF token cosine, GBT and verified merge with a
30-round limit, following the [validation selections](bench/METHODS.md). The examples explicitly retain their
historical gram/scalar settings. All eight frozen prediction replays now match exactly; the remaining integration gates are tracked in the ledger.

Run `pytest` with local Spark, or `python tools/connect_tests.py` to own a temporary local Connect server and
run the same tests. `tools/experiment.py` captures bounded commands and evidence; `bash verify_zr.sh 1` only
reads that evidence and fails when it is missing or stale. `bash verify_zr.sh 2` also checks all four corpus ablations. ZR-3 is blocked at its iteration cap; ZR-6/7/8 remain incomplete; ZR-9 is parked on a confirmed workspace restriction.

Prepare additional public corpora and the optional embedding snapshot with
`python tools/prepare_sources.py --model` after installing `.[embeddings]`.
`python tools/accept_zr2.py` runs the fixed local validation sweep; its four Spark runs each
have a 15-minute limit and deny external egress at the OS level. Embeddings remain off by default
because their paired validation improvement was inconclusive on both tested domains.

Training logs a composite model to local SQLite, including the Spark pipeline, raw-pair
signature, candidate/feature specs, training label digest and evaluation. Supply
`input.validation_labels` and an explicit `mlflow.acceptance_f1` to promote a model;
the validation records must be separate from training records. Passing local runs
write `models/current.json` (configurable with `model.pointer`). A `run` without
`input.labels` resolves that immutable MLflow run. A training-only diagnostic does
not promote a model. See [the model contract](bench/MODELS.md) for batch-input semantics.

## What is here

```text
lakematch/
├── LICENSE                  Apache-2.0
├── goal.md                  authoritative task and acceptance ledger
├── src/lakematch/           ZR-1 engine, configuration, runtime, quality and CLI
├── examples/                small synthetic fixture and public FEBRL4 config
├── tests/                   same suite on classic local Spark and Spark Connect
├── experiments/             append-only run ledger, manifests and environment report
├── bench/                   measured new-engine evidence (historical harness stays below)
├── verify_zr.sh             read-only acceptance verifier; execution is tools/accept_zr1.py
├── spec/
│   ├── BRIEF.md             the brief: rules, config, method choices, phases, benchmarks, decisions
│   ├── zr_decisions.html    the 28-card decision board (open locally in a browser)
│   ├── research/            similarity_sota.md · platform_facts.md
│   ├── porting/             PORTING.md (adapt vs rewrite study) · PORTING_ASTRA_OPINION.md (adversarial review)
│   └── bench/               the measurement harness, the ~90-line pure-Spark prototype (proto_spark_native.py),
│                            README.md (results), ASTRA_REVIEW.md (independent review), cache/ (LLM judgments on
│                            public corpora, so reruns cost nothing)
└── tools/                   experiment runners, corpus preparation and Spark 4.3 release watcher
```

Not here, on purpose:

- **Zingg code**: the Spark 4.1 port and its patch live in the public fork `github.com/laurentfabre/zingg` (AGPL v3).
  AGPL code cannot be mixed into this Apache-2.0 repository; reading it is fine, copying it is not.
- `goals/goal_mdm.md` and every personal dataset. Only public or synthetic corpora are used, here and on any workspace.
- The corpora themselves (`spec/bench/data/`, `spec/bench/work/`, ~90 MB): `spec/bench/README.md` says where each one
  comes from; the loaders download them again.

## Resuming on another machine

For GitHub-to-workspace recovery, follow the [deployment runbook](deployment/README.md).
It covers all three bundles, checksummed inputs, durable reviews and existing
resource bindings. The illustrated [nontechnical explanation](reports/lakematch-explained/LakeMatch-Explained.pdf)
describes the measured campaign snapshot.

The [2026-09-21 test session](reports/test-runs/20260921T092956Z/README.md)
records the prepared corpus inventory, fresh Spark/Connect regression runs,
browser review and retraining checks, and frozen-model replays. The replay tool
`tools/replay_test_corpora.py --output <fresh-directory> --report <new-json>`
copies the execution sources and corpus manifests, verifies frozen input/model
hashes, and keeps new outputs separate from prior evidence. It requires the
prepared local benchmark/model stores and the macOS `sandbox-exec` offline
policy. Run it through `tools/experiment.py` with a finite timeout. The Connect
test runner accepts `--junitxml <new-path>` so new runs preserve earlier reports.

1. Java 17, Python 3.12, `pip install "pyspark[connect,pipelines]==4.1.3" mlflow pyyaml` in a virtualenv. Spark 4.1
   crashes on Java 23: pin `JAVA_HOME` to a 17.
2. Databricks CLI profiles are per machine. This campaign explicitly selected `fevm-gdpr2` for both serverless and
   classic; historical `fourth-pat` references are not execution settings. Always pass the selected profile.
3. The LLM labeller is optional and off by default; its key is read from the environment, never from the repository.
4. Stop the warehouse and terminate the cluster the moment a run ends.

## License

Apache-2.0 — see [`LICENSE`](LICENSE). The arbitration app (`app/`, APX) and the DQX adapter rely on components under
the Databricks licence; they are optional and never dependencies of the engine.

Prior art and comparison sources include Fellegi–Sunter, Splink, the Magellan group, SecondString and published
Zingg figures. This engine is independently implemented; no Zingg source, translation, JAR or adapter is included.
