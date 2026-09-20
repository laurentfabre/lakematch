# Synthetic scale measurements

Exact duplicates with unique SHA-256 codes; separate 400-record training namespace. These results measure native work and cap-induced loss, not realistic corruption accuracy. Unchanged local[2], default JVM memory, k=5, four hash tables, cap 400, 50-million retained join rows. [Plan](FINAL_PLAN.md).

| Total records | Join rows before cap | After cap | Candidate pairs | Recall@5 | F1 | Wall s | Records/s | Shuffle read/write bytes | Max/median task ms ratio |
|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| 1000 | 10642 | 10642 | 2483 | 1.0000 | 1.0000 | 21.10 | 47.4 | 1108318 / 1021272 | 60.82 |
| 10000 | 866666 | 866666 | 25000 | 1.0000 | 1.0000 | 34.45 | 290.3 | 20444592 / 20313274 | 460.00 |
| 100000 | 85220228 | 22090339 | 238553 | 0.9555 | 0.9772 | 342.12 | 292.3 | 438844247 / 438550605 | 3554.29 |
| 1000000 | 8450667332 | 20326239 | 471655 | unavailable | unavailable | 672.80 (failed) | unavailable | 2895181199 / 4168325860 | 3803.78 |

Hot-key fixture: 2000 indistinguishable records; pre-cap join rows 4000000, post-cap 0, recall 0.0000. Dropping nonselective buckets bounds work at the expense of recall.
The million-record run failed during candidate-table materialization with Java heap exhaustion. Its join counters and completed-task shuffle are partial observations. F1, candidate recall and successful throughput were not measured. Spark table cleanup also failed after the JVM failure; the runner verified termination of the owned process group. Memory and candidate budgets were not increased.

Wall/throughput includes training, model logging, generation, retrieval, scoring, output and Spark cleanup. Shuffle includes all task attempts; peak execution memory is per task, not process RSS. Raw event logs and output checksums are sealed. Local publication crash/retry evidence is [separate](PUBLICATION.md); remote fixture recovery evidence is tracked separately in [SERVERLESS.md](SERVERLESS.md).

- scale-1000000: failed; partial counters retained, no completed output or quality claim
