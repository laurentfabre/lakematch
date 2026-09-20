# Clustering validation measurements

Frozen entity-disjoint partitions; confirmation remains unscored. [Protocol](CLUSTER_PLAN.md).
Splink uses its separately declared blocking budget and supervised training procedure. It is a measured baseline, not an equal-candidate-budget retriever comparison.

| Corpus | Method | Pairwise F1 [95% CI] | B-cubed F1 [95% CI] | Precision | Recall | Seconds |
|---|---|---|---|---:|---:|---:|
| febrl3 | Splink supervised / components | 0.9979 [0.9943, 1.0000] | 0.9986 [0.9964, 1.0000] | 1.0000 | 0.9959 | 1.86 |
| historical_50k | Splink supervised / components | 0.8580 [0.8429, 0.8716] | 0.8797 [0.8725, 0.8869] | 0.9324 | 0.7946 | 6.50 |

Splink seconds cover data preparation, fit, score, threshold tuning, metrics and database cleanup; Spark method seconds cover clustering and owned-table cleanup on a shared scored graph. They are different timing boundaries.

Native method selection, incremental identity reconciliation and CLI acceptance remain pending. Historical published figures are not used as acceptance evidence.

- `splink-febrl3`: [20260920T005517Z-splink-febrl3-0a57a2](../experiments/20260920T005517Z-splink-febrl3-0a57a2/manifest.json).
- `splink-historical_50k`: [20260920T005520Z-splink-historical_50k-df150d](../experiments/20260920T005520Z-splink-historical_50k-df150d/manifest.json).

Missing compatible comparisons: cluster-febrl3, cluster-historical_50k.

Retained failures:
- [20260920T005314Z-splink-febrl3-7aa05c](../experiments/20260920T005314Z-splink-febrl3-7aa05c/manifest.json): failed.
- [20260920T005352Z-splink-febrl3-ade5ac](../experiments/20260920T005352Z-splink-febrl3-ade5ac/manifest.json): failed.
