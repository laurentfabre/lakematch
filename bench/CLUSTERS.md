# Clustering validation measurements

Frozen entity-disjoint partitions; confirmation remains unscored. [Protocol](CLUSTER_PLAN.md).
Splink uses its separately declared blocking budget and supervised training procedure. It is a measured baseline, not an equal-candidate-budget retriever comparison.

| Corpus | Method | Pairwise F1 [95% CI] | B-cubed F1 [95% CI] | Precision | Recall | Seconds |
|---|---|---|---|---:|---:|---:|
| febrl3 | Splink supervised / components | 0.9979 [0.9943, 1.0000] | 0.9986 [0.9964, 1.0000] | 1.0000 | 0.9959 | 1.86 |
| febrl3 | connected_components | 1.0000 [1.0000, 1.0000] | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 2.58 |
| febrl3 | center | 0.9966 [0.9912, 1.0000] | 0.9984 [0.9960, 1.0000] | 1.0000 | 0.9931 | 2.91 |
| febrl3 | star | 1.0000 [1.0000, 1.0000] | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 2.35 |
| febrl3 | verified_merge | 1.0000 [1.0000, 1.0000] | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 18.82 |
| historical_50k | Splink supervised / components | 0.8580 [0.8429, 0.8716] | 0.8797 [0.8725, 0.8869] | 0.9324 | 0.7946 | 6.50 |
| historical_50k | connected_components | 0.1415 [0.1239, 0.1647] | 0.7831 [0.7620, 0.8037] | 0.0763 | 0.9749 | 10.34 |
| historical_50k | center | 0.5096 [0.4955, 0.5246] | 0.6494 [0.6355, 0.6635] | 0.9941 | 0.3426 | 5.54 |
| historical_50k | star | 0.8423 [0.8335, 0.8518] | 0.8746 [0.8675, 0.8825] | 0.9735 | 0.7422 | 4.26 |
| historical_50k | verified_merge | 0.9392 [0.9302, 0.9473] | 0.9454 [0.9395, 0.9508] | 0.9743 | 0.9066 | 88.25 |

Splink seconds cover data preparation, fit, score, threshold tuning, metrics and database cleanup; Spark method seconds cover clustering and owned-table cleanup on a shared scored graph. They are different timing boundaries.

Native method selection, incremental identity reconciliation and CLI acceptance remain pending. Historical published figures are not used as acceptance evidence.

- `splink-febrl3`: [20260920T005517Z-splink-febrl3-0a57a2](../experiments/20260920T005517Z-splink-febrl3-0a57a2/manifest.json).
- `cluster-febrl3`: [20260920T044336Z-cluster-febrl3-e627af](../experiments/20260920T044336Z-cluster-febrl3-e627af/manifest.json).
- `splink-historical_50k`: [20260920T005520Z-splink-historical_50k-df150d](../experiments/20260920T005520Z-splink-historical_50k-df150d/manifest.json).
- `cluster-historical_50k`: [20260920T044433Z-cluster-historical_50k-8a67c9](../experiments/20260920T044433Z-cluster-historical_50k-8a67c9/manifest.json).

Retained failures:
- [20260920T005314Z-splink-febrl3-7aa05c](../experiments/20260920T005314Z-splink-febrl3-7aa05c/manifest.json): failed.
- [20260920T005352Z-splink-febrl3-ade5ac](../experiments/20260920T005352Z-splink-febrl3-ade5ac/manifest.json): failed.
- [20260920T010851Z-cluster-historical_50k-e76bf6](../experiments/20260920T010851Z-cluster-historical_50k-e76bf6/manifest.json): failed.
- [20260920T011350Z-cluster-febrl3-40aea9](../experiments/20260920T011350Z-cluster-febrl3-40aea9/manifest.json): failed.

## Equal-corpus macro comparison

| Method | Pairwise F1 | B-cubed F1 | Paired F1 change CI vs components | Mean clustering s |
|---|---:|---:|---|---:|
| connected_components | 0.5707 | 0.8915 | [+0.0000, +0.0000] | 6.46 |
| center | 0.7531 | 0.8239 | [+0.1689, +0.1947] | 4.23 |
| star | 0.9211 | 0.9373 | [+0.3397, +0.3605] | 3.31 |
| verified_merge | 0.9696 | 0.9727 | [+0.3879, +0.4082] | 53.54 |

Validation recommendation: `verified_merge`. No model/default is promoted by this report.
Macro uncertainty uses independent namespaced entity draws for the two corpora, paired across methods; 2,000 PCG64 resamples with seed derived from SHA-256 of 2026091902/clusters/corpus. Incremental identities and CLI acceptance still require execution.

## Final-source acceptance

Iteration 8 reused the original two models, training IDF and thresholds; no
model was refitted. Every scored edge and membership reproduced the preserved
validation outputs. Both exact identity mutations and the normal CLI publication
checks subsequently passed, and `bash verify_zr.sh 4` exits zero. See
[the prior-output audit](../experiments/identity-replay-audit.json) and
[publication evidence](PUBLICATION.md).
