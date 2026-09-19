# lakematch

*An entity-resolution engine for the lakehouse: one PySpark codebase for a laptop, Databricks serverless and
classic compute. Apache-2.0. **Private repository** — not for publication.*

## What / why

Matching, linking and mastering records with Spark SQL built-ins only (no JVM code, no UDF on a default path), inside
Spark Declarative Pipelines where the platform allows it, tracked in MLflow, with a human arbitration app (APX) and a
Genie agent. The full specification, the nine bounded phases ZR-1..9 and the ledger of the 28 design decisions are in
[`spec/BRIEF.md`](spec/BRIEF.md).

**State on 2026-09-19: nothing is built.** This repository holds the specification side only. Start with the ZR-1
`/goal` line of the brief, in a session opened at the root of this repository.

## What is here

```text
lakematch/
├── LICENSE                  Apache-2.0
├── spec/
│   ├── BRIEF.md             the brief: rules, config, method choices, phases, benchmarks, decisions
│   ├── zr_decisions.html    the 28-card decision board (open locally in a browser)
│   ├── research/            similarity_sota.md · platform_facts.md
│   ├── porting/             PORTING.md (adapt vs rewrite study) · PORTING_ASTRA_OPINION.md (adversarial review)
│   └── bench/               the measurement harness, the ~90-line pure-Spark prototype (proto_spark_native.py),
│                            README.md (results), ASTRA_REVIEW.md (independent review), cache/ (LLM judgments on
│                            public corpora, so reruns cost nothing)
└── tools/spark43_watch.py   weekly check for the Spark 4.3 release (Jaro-Winkler becomes a built-in)
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
2. Databricks CLI profiles are per machine. Serverless phases name `fourth-pat` (Free Edition); on this machine either
   create that profile or change the name in the brief and the config. **Classic phases (ZR-9) need `classic.profile`
   set by hand to the paid workspace** — it is never guessed.
3. The LLM labeller is optional and off by default; its key is read from the environment, never from the repository.
4. Stop the warehouse and terminate the cluster the moment a run ends.

## License

Apache-2.0 — see [`LICENSE`](LICENSE). The arbitration app (`app/`, APX) and the DQX adapter rely on components under
the Databricks licence; they are optional and never dependencies of the engine.
