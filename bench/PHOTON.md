# Photon on serverless — lakematch FEBRL4 (ZR-6)

Measured 2026-10-02T20:57:34+02:00 on fourth-pat (Free Edition, serverless, Spark 4.2.0) by `python bench/serverless.py all`; the run with every paid feature off.
Share = Photon time / task time, summed over the stage's statements in query history (the numbers the query profile shows). Fell back = the stage's physical-plan operators that are not Photon operators (formatted plan of the same stage on the same compute; the profile's operator tree has no public API).

| Stage | Where | Statements | Task time (s) | Photon time (s) | Photon share | Operators that fell back |
|---|---|---:|---:|---:|---:|---|
| gate | pipeline | 8 | 11.0 | 4.1 | 38% | `Filter`, `Project`, `Scan` — unsupported: `cast(struct -> struct with collations)` |
| entity | pipeline | 4 | 6.2 | 4.3 | 70% | none |
| candidates | pipeline | 2 | 91.7 | 89.3 | 97% | none |
| features | pipeline | 2 | 47.2 | 3.9 | 8% | `Project` — unsupported: `aggregate` |
| scores | pipeline | 2 | 1.3 | 0.8 | 62% | none |
| links | pipeline | 2 | 0.7 | 0.3 | 50% | none |
| plan | job task | 5 | 1.8 | 0.0 | 0% | — (MLlib / driver work) |
| train | job task | 20 | 5.7 | 0.7 | 13% | — (MLlib / driver work) |
| cluster | job task | 16 | 14.9 | 7.5 | 51% | — (MLlib / driver work) |

Notes

- Training (MLlib `fit`) runs in the train task; Photon accelerates DataFrame work only, never MLlib.
- Scoring inside the pipeline is a compiled Spark SQL expression (src/lakematch/scoring_sql.py), not MLlib: a serverless pipeline crashes when `pyspark.ml` or MLflow is imported in it.
