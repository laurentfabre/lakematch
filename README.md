# lakematch

*An entity-resolution engine for the lakehouse: one PySpark codebase for a laptop, Databricks serverless and
classic compute. Apache-2.0. **Private repository** — not for publication.*

## What / why

Matching, linking and mastering records with Spark SQL built-ins only (no JVM code, no UDF on a default path), inside
Spark Declarative Pipelines where the platform allows it, tracked in MLflow, with a human arbitration app (APX) and a
Genie agent. The full specification, the nine bounded phases ZR-1..9 and the ledger of the 28 design decisions are in
[`spec/BRIEF.md`](spec/BRIEF.md).

**State on 2026-09-19: ZR-1 passes its verifier; the serverless engine canary also passes.** The engine now includes YAML configuration,
native quality checks, bounded IDF candidates, comparison features, MLlib estimators and deterministic links.
The same 39-test suite passes on classic local Spark and Spark Connect, and an offline synthetic CLI run passes.
Later phases are pending. [goal.md](goal.md) is the authoritative acceptance ledger;
[bench/ENGINE.md](bench/ENGINE.md) records development evidence and limitations.

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

Run `pytest` with local Spark, or `python tools/connect_tests.py` to own a temporary local Connect server and
run the same tests. `tools/experiment.py` captures bounded commands and evidence; `bash verify_zr.sh 1` only
reads that evidence and fails when it is missing or stale. Phases 2–9 remain nonzero until implemented.

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
