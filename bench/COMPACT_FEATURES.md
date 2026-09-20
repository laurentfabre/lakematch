# Compact native feature comparison

Validation-only measurements under [COMPACT_PLAN.md](COMPACT_PLAN.md). Thresholds and policies are chosen on validation.
Intervals describe sampling uncertainty; they do not correct for model, threshold or policy selection optimism.
Supplied-pair tasks and full-universe FEBRL linkage have different evaluation scopes. Neither is confirmation evidence.

## febrl4_half_all

Run [20260920T005641Z-compact-febrl4-all-da9e9b](../experiments/20260920T005641Z-compact-febrl4-all-da9e9b/manifest.json); scope: closed-world transductive linkage. Preparation/Spark/output wall: 78.6s; complete runner wall including evidence hashing/compression and cleanup: 94.7s.

| Feature set | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| native_all | gbt | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.58/3.64/0.51 |
| native_all | gbt | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.58/3.64/0.51 |
| native_all | gbt | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.58/3.64/0.51 |
| idf_only | gbt | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 1.71/3.07/0.37 |
| idf_only | gbt | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 1.71/3.07/0.37 |
| idf_only | gbt | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 1.71/3.07/0.37 |
| scalar_fields | gbt | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 1.41/2.91/0.35 |
| scalar_fields | gbt | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 1.41/2.91/0.35 |
| scalar_fields | gbt | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 1.41/2.91/0.35 |

- Baseline nearest_neighbour: F1 0.6667, threshold 0.00, IDF gram cosine.
- Baseline scalar_threshold: F1 1.0000, threshold 0.54, IDF gram cosine.

## febrl4_half_no_ssn

Run [20260920T005816Z-compact-febrl4-no_ssn-58e10e](../experiments/20260920T005816Z-compact-febrl4-no_ssn-58e10e/manifest.json); scope: closed-world transductive linkage. Preparation/Spark/output wall: 72.6s; complete runner wall including evidence hashing/compression and cleanup: 88.7s.

| Feature set | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| native_all | gbt | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.25/3.62/0.48 |
| native_all | gbt | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.25/3.62/0.48 |
| native_all | gbt | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.25/3.62/0.48 |
| idf_only | gbt | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 1.54/2.95/0.37 |
| idf_only | gbt | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 1.54/2.95/0.37 |
| idf_only | gbt | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 1.54/2.95/0.37 |
| scalar_fields | gbt | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 1.29/2.84/0.33 |
| scalar_fields | gbt | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 1.29/2.84/0.33 |
| scalar_fields | gbt | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 1.29/2.84/0.33 |

- Baseline nearest_neighbour: F1 0.6667, threshold 0.00, IDF gram cosine.
- Baseline scalar_threshold: F1 1.0000, threshold 0.46, IDF gram cosine.

## febrl4_half_no_ssn_dob

Run [20260920T005946Z-compact-febrl4-no_ssn_dob-0cf154](../experiments/20260920T005946Z-compact-febrl4-no_ssn_dob-0cf154/manifest.json); scope: closed-world transductive linkage. Preparation/Spark/output wall: 69.5s; complete runner wall including evidence hashing/compression and cleanup: 85.2s.

| Feature set | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| native_all | gbt | one_to_one | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.9980 | 0.89 | 2.99/3.52/0.44 |
| native_all | gbt | many_to_one | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.9980 | 0.89 | 2.99/3.52/0.44 |
| native_all | gbt | unrestricted | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.9980 | 0.89 | 2.99/3.52/0.44 |
| idf_only | gbt | one_to_one | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.9980 | 0.89 | 1.42/2.90/0.35 |
| idf_only | gbt | many_to_one | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.9980 | 0.89 | 1.42/2.90/0.35 |
| idf_only | gbt | unrestricted | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.9980 | 0.89 | 1.42/2.90/0.35 |
| scalar_fields | gbt | one_to_one | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.9980 | 0.89 | 1.14/2.77/0.32 |
| scalar_fields | gbt | many_to_one | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.9980 | 0.89 | 1.14/2.77/0.32 |
| scalar_fields | gbt | unrestricted | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.9980 | 0.89 | 1.14/2.77/0.32 |

- Baseline nearest_neighbour: F1 0.6667, threshold 0.00, IDF gram cosine.
- Baseline scalar_threshold: F1 0.9990, threshold 0.42, IDF gram cosine.

## bpid

Run [20260920T010112Z-compact-bpid-e3504e](../experiments/20260920T010112Z-compact-bpid-e3504e/manifest.json); scope: supplied labelled pairs only. Preparation/Spark/output wall: 49.0s; complete runner wall including evidence hashing/compression and cleanup: 58.7s.

| Feature set | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| native_all | gbt | unrestricted | 0.7570 [0.7358, 0.7777] | 0.6681 | 0.8732 | 0.41 | 3.51/3.24/0.36 |
| native_all | gbt | many_to_one | 0.7570 [0.7358, 0.7777] | 0.6681 | 0.8732 | 0.41 | 3.51/3.24/0.36 |
| native_all | gbt | one_to_one | 0.7570 [0.7358, 0.7777] | 0.6681 | 0.8732 | 0.41 | 3.51/3.24/0.36 |
| idf_only | gbt | unrestricted | 0.7513 [0.7289, 0.7715] | 0.6507 | 0.8888 | 0.38 | 1.33/2.51/0.24 |
| idf_only | gbt | many_to_one | 0.7513 [0.7289, 0.7715] | 0.6507 | 0.8888 | 0.38 | 1.33/2.51/0.24 |
| idf_only | gbt | one_to_one | 0.7513 [0.7289, 0.7715] | 0.6507 | 0.8888 | 0.38 | 1.33/2.51/0.24 |
| scalar_fields | gbt | unrestricted | 0.7219 [0.7009, 0.7432] | 0.6068 | 0.8910 | 0.33 | 1.11/2.35/0.23 |
| scalar_fields | gbt | many_to_one | 0.7219 [0.7009, 0.7432] | 0.6068 | 0.8910 | 0.33 | 1.11/2.35/0.23 |
| scalar_fields | gbt | one_to_one | 0.7219 [0.7009, 0.7432] | 0.6068 | 0.8910 | 0.33 | 1.11/2.35/0.23 |

- Baseline nearest_neighbour: F1 0.6118, threshold 0.00, mean present-field Levenshtein.
- Baseline scalar_threshold: F1 0.6162, threshold 0.18, mean present-field Levenshtein.

## abt_buy

Run [20260920T010212Z-compact-abt_buy-86c5c4](../experiments/20260920T010212Z-compact-abt_buy-86c5c4/manifest.json); scope: supplied labelled pairs only. Preparation/Spark/output wall: 39.0s; complete runner wall including evidence hashing/compression and cleanup: 48.5s.

| Feature set | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| native_all | gbt | unrestricted | 0.6392 [0.5816, 0.6903] | 0.6316 | 0.6471 | 0.22 | 7.96/2.98/0.33 |
| idf_only | gbt | unrestricted | 0.6121 [0.5514, 0.6685] | 0.6629 | 0.5686 | 0.24 | 0.89/2.27/0.20 |
| scalar_fields | gbt | unrestricted | 0.5517 [0.4868, 0.6136] | 0.7652 | 0.4314 | 0.36 | 0.82/2.22/0.19 |

- Baseline nearest_neighbour: F1 0.3239, threshold 0.00, mean present-field Levenshtein.
- Baseline scalar_threshold: F1 0.3400, threshold 0.30, mean present-field Levenshtein.

## affiliations

Run [20260920T010302Z-compact-affiliations-1f09f2](../experiments/20260920T010302Z-compact-affiliations-1f09f2/manifest.json); scope: supplied labelled pairs only. Preparation/Spark/output wall: 39.3s; complete runner wall including evidence hashing/compression and cleanup: 48.2s.

| Feature set | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| native_all | gbt | unrestricted | 0.9395 [0.9292, 0.9485] | 0.9855 | 0.8975 | 0.64 | 3.17/3.26/0.31 |
| idf_only | gbt | unrestricted | 0.9395 [0.9290, 0.9485] | 0.9810 | 0.9013 | 0.58 | 0.70/2.62/0.24 |
| scalar_fields | gbt | unrestricted | 0.8654 [0.8458, 0.8818] | 0.9022 | 0.8314 | 0.70 | 0.64/2.55/0.20 |

- Baseline nearest_neighbour: F1 0.2264, threshold 0.00, mean present-field Levenshtein.
- Baseline scalar_threshold: F1 0.7600, threshold 0.26, mean present-field Levenshtein.

## amazon_google

Run [20260920T010352Z-compact-amazon_google-4acbe9](../experiments/20260920T010352Z-compact-amazon_google-4acbe9/manifest.json); scope: supplied labelled pairs only. Preparation/Spark/output wall: 32.9s; complete runner wall including evidence hashing/compression and cleanup: 42.0s.

| Feature set | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| native_all | gbt | unrestricted | 0.6339 [0.5880, 0.6789] | 0.5657 | 0.7209 | 0.27 | 2.06/3.01/0.30 |
| idf_only | gbt | unrestricted | 0.6358 [0.5874, 0.6804] | 0.5808 | 0.7023 | 0.29 | 0.77/2.46/0.23 |
| scalar_fields | gbt | unrestricted | 0.6506 [0.5969, 0.6990] | 0.6750 | 0.6279 | 0.31 | 0.64/2.25/0.21 |

- Baseline nearest_neighbour: F1 0.3306, threshold 0.00, mean present-field Levenshtein.
- Baseline scalar_threshold: F1 0.3315, threshold 0.60, mean present-field Levenshtein.

## walmart_amazon

Run [20260920T010436Z-compact-walmart_amazon-96b466](../experiments/20260920T010436Z-compact-walmart_amazon-96b466/manifest.json); scope: supplied labelled pairs only. Preparation/Spark/output wall: 37.5s; complete runner wall including evidence hashing/compression and cleanup: 47.2s.

| Feature set | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| native_all | gbt | unrestricted | 0.7824 [0.7318, 0.8293] | 0.8353 | 0.7358 | 0.30 | 3.47/3.09/0.32 |
| idf_only | gbt | unrestricted | 0.7771 [0.7246, 0.8257] | 0.8662 | 0.7047 | 0.34 | 1.17/2.40/0.23 |
| scalar_fields | gbt | unrestricted | 0.7582 [0.7062, 0.8072] | 0.8070 | 0.7150 | 0.34 | 0.97/2.32/0.22 |

- Baseline nearest_neighbour: F1 0.3018, threshold 0.00, mean present-field Levenshtein.
- Baseline scalar_threshold: F1 0.2763, threshold 0.61, mean present-field Levenshtein.

## dblp_acm

Run [20260920T010525Z-compact-dblp_acm-416b37](../experiments/20260920T010525Z-compact-dblp_acm-416b37/manifest.json); scope: supplied labelled pairs only. Preparation/Spark/output wall: 42.6s; complete runner wall including evidence hashing/compression and cleanup: 52.7s.

| Feature set | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| native_all | gbt | unrestricted | 0.9853 [0.9756, 0.9932] | 0.9820 | 0.9887 | 0.47 | 4.09/3.08/0.37 |
| native_all | gbt | many_to_one | 0.9864 [0.9779, 0.9938] | 0.9842 | 0.9887 | 0.47 | 4.09/3.08/0.37 |
| native_all | gbt | one_to_one | 0.9887 [0.9812, 0.9955] | 0.9821 | 0.9955 | 0.33 | 4.09/3.08/0.37 |
| idf_only | gbt | unrestricted | 0.9842 [0.9747, 0.9929] | 0.9776 | 0.9909 | 0.35 | 1.10/2.50/0.23 |
| idf_only | gbt | many_to_one | 0.9853 [0.9767, 0.9932] | 0.9798 | 0.9909 | 0.35 | 1.10/2.50/0.23 |
| idf_only | gbt | one_to_one | 0.9842 [0.9753, 0.9920] | 0.9819 | 0.9864 | 0.35 | 1.10/2.50/0.23 |
| scalar_fields | gbt | unrestricted | 0.9853 [0.9761, 0.9932] | 0.9798 | 0.9909 | 0.41 | 0.96/2.35/0.23 |
| scalar_fields | gbt | many_to_one | 0.9865 [0.9781, 0.9935] | 0.9820 | 0.9909 | 0.41 | 0.96/2.35/0.23 |
| scalar_fields | gbt | one_to_one | 0.9887 [0.9809, 0.9953] | 0.9865 | 0.9909 | 0.41 | 0.96/2.35/0.23 |

- Baseline nearest_neighbour: F1 0.5225, threshold 0.00, mean present-field Levenshtein.
- Baseline scalar_threshold: F1 0.9024, threshold 0.56, mean present-field Levenshtein.

## Macro validation results

Seven equally weighted corpora; FEBRL all/SSN-hidden split one vote. The diagnostic does not vote.
Within each trial, the best permitted validation policy is used. Macro intervals use 2,000 paired group resamples,
PCG64 seeded by SHA-256 of bootstrap seed 2026091902 and corpus name; FEBRL variants share entity draws.

| Configuration | Macro F1 [95% CI] | Paired change CI vs all native token features | Weighted feature/fit/score s |
|---|---|---|---:|
| idf_only | 0.8145 [0.8013, 0.8273] | [-0.0126, +0.0014] | 3.87 |
| native_all | 0.8201 [0.8067, 0.8325] | [+0.0000, +0.0000] | 7.49 |
| scalar_fields | 0.7909 [0.7762, 0.8053] | [-0.0408, -0.0187] | 3.57 |

Best point estimate: `native_all`. Simpler-choice recommendation: `idf_only`.
Every candidate-to-best paired interval is retained in the structured index. This is a validation recommendation; final model freeze and latency remain pending.

No models were promoted by this report. Each trial links to its composite MLflow model in the structured evidence.
The remaining retrieval/F1, final latency, scale and confirmation gates retain their separate requirements.
