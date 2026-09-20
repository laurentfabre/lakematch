# Classifier, string and cardinality comparisons

Validation-only measurements under [CLASSIFIER_PLAN.md](CLASSIFIER_PLAN.md). Thresholds and policies are chosen on validation.
Intervals describe sampling uncertainty; they do not correct for model, threshold or policy selection optimism.
Supplied-pair tasks and full-universe FEBRL linkage have different evaluation scopes. Neither is confirmation evidence.

## febrl4_half_all

Run [20260920T003007Z-methods-febrl4-all-6f4870](../experiments/20260920T003007Z-methods-febrl4-all-6f4870/manifest.json); scope: closed-world transductive linkage. Preparation/Spark/output wall: 149.1s; complete runner wall including evidence hashing/compression and cleanup: 204.2s.

| String | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| levenshtein | gbt | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.59/3.73/0.51 |
| levenshtein | gbt | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.59/3.73/0.51 |
| levenshtein | gbt | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.59/3.73/0.51 |
| levenshtein | logistic_regression | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.62 | 3.59/3.32/0.46 |
| levenshtein | logistic_regression | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.62 | 3.59/3.32/0.46 |
| levenshtein | logistic_regression | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.62 | 3.59/3.32/0.46 |
| levenshtein | random_forest | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.55 | 3.59/3.16/0.44 |
| levenshtein | random_forest | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.55 | 3.59/3.16/0.44 |
| levenshtein | random_forest | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.55 | 3.59/3.16/0.44 |
| jaro_winkler | gbt | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.89/3.28/0.42 |
| jaro_winkler | gbt | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.89/3.28/0.42 |
| jaro_winkler | gbt | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.89/3.28/0.42 |
| jaro_winkler | logistic_regression | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.66 | 3.89/2.65/0.46 |
| jaro_winkler | logistic_regression | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.66 | 3.89/2.65/0.46 |
| jaro_winkler | logistic_regression | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.66 | 3.89/2.65/0.46 |
| jaro_winkler | random_forest | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.49 | 3.89/3.15/0.45 |
| jaro_winkler | random_forest | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.49 | 3.89/3.15/0.45 |
| jaro_winkler | random_forest | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.49 | 3.89/3.15/0.45 |
| both | gbt | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.84/3.31/0.45 |
| both | gbt | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.84/3.31/0.45 |
| both | gbt | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.84/3.31/0.45 |
| both | logistic_regression | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.62 | 3.84/2.93/0.46 |
| both | logistic_regression | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.62 | 3.84/2.93/0.46 |
| both | logistic_regression | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.62 | 3.84/2.93/0.46 |
| both | random_forest | one_to_one | 0.9990 [0.9969, 1.0000] | 0.9980 | 1.0000 | 0.20 | 3.84/3.15/0.50 |
| both | random_forest | many_to_one | 0.9990 [0.9969, 1.0000] | 0.9980 | 1.0000 | 0.20 | 3.84/3.15/0.50 |
| both | random_forest | unrestricted | 0.9980 [0.9949, 1.0000] | 0.9960 | 1.0000 | 0.20 | 3.84/3.15/0.50 |

- Baseline nearest_neighbour: F1 0.6667, threshold 0.00, IDF gram cosine.
- Baseline scalar_threshold: F1 1.0000, threshold 0.54, IDF gram cosine.

## febrl4_half_no_ssn

Run [20260920T003409Z-methods-febrl4-no_ssn-a7360f](../experiments/20260920T003409Z-methods-febrl4-no_ssn-a7360f/manifest.json); scope: closed-world transductive linkage. Preparation/Spark/output wall: 140.2s; complete runner wall including evidence hashing/compression and cleanup: 195.5s.

| String | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| levenshtein | gbt | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.32/3.72/0.51 |
| levenshtein | gbt | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.32/3.72/0.51 |
| levenshtein | gbt | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.32/3.72/0.51 |
| levenshtein | logistic_regression | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.27 | 3.32/3.19/0.40 |
| levenshtein | logistic_regression | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.27 | 3.32/3.19/0.40 |
| levenshtein | logistic_regression | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.27 | 3.32/3.19/0.40 |
| levenshtein | random_forest | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.45 | 3.32/3.05/0.40 |
| levenshtein | random_forest | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.45 | 3.32/3.05/0.40 |
| levenshtein | random_forest | unrestricted | 0.9990 [0.9969, 1.0000] | 0.9980 | 1.0000 | 0.45 | 3.32/3.05/0.40 |
| jaro_winkler | gbt | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.58/3.32/0.40 |
| jaro_winkler | gbt | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.58/3.32/0.40 |
| jaro_winkler | gbt | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.58/3.32/0.40 |
| jaro_winkler | logistic_regression | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.32 | 3.58/2.56/0.42 |
| jaro_winkler | logistic_regression | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.32 | 3.58/2.56/0.42 |
| jaro_winkler | logistic_regression | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.32 | 3.58/2.56/0.42 |
| jaro_winkler | random_forest | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.39 | 3.58/3.03/0.44 |
| jaro_winkler | random_forest | many_to_one | 0.9990 [0.9969, 1.0000] | 0.9980 | 1.0000 | 0.39 | 3.58/3.03/0.44 |
| jaro_winkler | random_forest | unrestricted | 0.9990 [0.9969, 1.0000] | 0.9980 | 1.0000 | 0.39 | 3.58/3.03/0.44 |
| both | gbt | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.37/3.27/0.45 |
| both | gbt | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.37/3.27/0.45 |
| both | gbt | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.95 | 3.37/3.27/0.45 |
| both | logistic_regression | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.30 | 3.37/2.70/0.46 |
| both | logistic_regression | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.30 | 3.37/2.70/0.46 |
| both | logistic_regression | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.30 | 3.37/2.70/0.46 |
| both | random_forest | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.43 | 3.37/3.18/0.46 |
| both | random_forest | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.43 | 3.37/3.18/0.46 |
| both | random_forest | unrestricted | 0.9990 [0.9963, 1.0000] | 1.0000 | 0.9980 | 0.45 | 3.37/3.18/0.46 |

- Baseline nearest_neighbour: F1 0.6667, threshold 0.00, IDF gram cosine.
- Baseline scalar_threshold: F1 1.0000, threshold 0.46, IDF gram cosine.

## febrl4_half_no_ssn_dob

Run [20260920T003727Z-methods-febrl4-no_ssn_dob-5509e3](../experiments/20260920T003727Z-methods-febrl4-no_ssn_dob-5509e3/manifest.json); scope: closed-world transductive linkage. Preparation/Spark/output wall: 133.0s; complete runner wall including evidence hashing/compression and cleanup: 184.5s.

| String | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| levenshtein | gbt | one_to_one | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.9980 | 0.89 | 2.94/3.54/0.45 |
| levenshtein | gbt | many_to_one | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.9980 | 0.89 | 2.94/3.54/0.45 |
| levenshtein | gbt | unrestricted | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.9980 | 0.89 | 2.94/3.54/0.45 |
| levenshtein | logistic_regression | one_to_one | 0.9980 [0.9949, 1.0000] | 0.9980 | 0.9980 | 0.21 | 2.94/3.01/0.42 |
| levenshtein | logistic_regression | many_to_one | 0.9980 [0.9949, 1.0000] | 0.9980 | 0.9980 | 0.21 | 2.94/3.01/0.42 |
| levenshtein | logistic_regression | unrestricted | 0.9980 [0.9949, 1.0000] | 0.9980 | 0.9980 | 0.21 | 2.94/3.01/0.42 |
| levenshtein | random_forest | one_to_one | 0.9879 [0.9806, 0.9942] | 1.0000 | 0.9760 | 0.59 | 2.94/2.95/0.41 |
| levenshtein | random_forest | many_to_one | 0.9879 [0.9806, 0.9942] | 1.0000 | 0.9760 | 0.59 | 2.94/2.95/0.41 |
| levenshtein | random_forest | unrestricted | 0.9879 [0.9806, 0.9942] | 1.0000 | 0.9760 | 0.59 | 2.94/2.95/0.41 |
| jaro_winkler | gbt | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.92 | 3.26/3.17/0.43 |
| jaro_winkler | gbt | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.92 | 3.26/3.17/0.43 |
| jaro_winkler | gbt | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.92 | 3.26/3.17/0.43 |
| jaro_winkler | logistic_regression | one_to_one | 0.9980 [0.9949, 1.0000] | 0.9980 | 0.9980 | 0.22 | 3.26/2.46/0.40 |
| jaro_winkler | logistic_regression | many_to_one | 0.9970 [0.9931, 1.0000] | 0.9960 | 0.9980 | 0.22 | 3.26/2.46/0.40 |
| jaro_winkler | logistic_regression | unrestricted | 0.9970 [0.9931, 1.0000] | 0.9960 | 0.9980 | 0.22 | 3.26/2.46/0.40 |
| jaro_winkler | random_forest | one_to_one | 0.9919 [0.9859, 0.9970] | 1.0000 | 0.9840 | 0.49 | 3.26/3.04/0.43 |
| jaro_winkler | random_forest | many_to_one | 0.9919 [0.9859, 0.9970] | 1.0000 | 0.9840 | 0.49 | 3.26/3.04/0.43 |
| jaro_winkler | random_forest | unrestricted | 0.9919 [0.9859, 0.9970] | 1.0000 | 0.9840 | 0.49 | 3.26/3.04/0.43 |
| both | gbt | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.91 | 3.07/3.18/0.36 |
| both | gbt | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.91 | 3.07/3.18/0.36 |
| both | gbt | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 1.0000 | 0.91 | 3.07/3.18/0.36 |
| both | logistic_regression | one_to_one | 0.9980 [0.9949, 1.0000] | 0.9980 | 0.9980 | 0.22 | 3.07/2.45/0.42 |
| both | logistic_regression | many_to_one | 0.9980 [0.9949, 1.0000] | 0.9980 | 0.9980 | 0.22 | 3.07/2.45/0.42 |
| both | logistic_regression | unrestricted | 0.9980 [0.9949, 1.0000] | 0.9980 | 0.9980 | 0.22 | 3.07/2.45/0.42 |
| both | random_forest | one_to_one | 0.9950 [0.9902, 0.9990] | 1.0000 | 0.9900 | 0.39 | 3.07/2.90/0.41 |
| both | random_forest | many_to_one | 0.9950 [0.9902, 0.9990] | 1.0000 | 0.9900 | 0.39 | 3.07/2.90/0.41 |
| both | random_forest | unrestricted | 0.9940 [0.9885, 0.9980] | 0.9980 | 0.9900 | 0.39 | 3.07/2.90/0.41 |

- Baseline nearest_neighbour: F1 0.6667, threshold 0.00, IDF gram cosine.
- Baseline scalar_threshold: F1 0.9990, threshold 0.42, IDF gram cosine.

## bpid

Run [20260920T004035Z-methods-bpid-87b963](../experiments/20260920T004035Z-methods-bpid-87b963/manifest.json); scope: supplied labelled pairs only. Preparation/Spark/output wall: 110.6s; complete runner wall including evidence hashing/compression and cleanup: 139.6s.

| String | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| levenshtein | gbt | unrestricted | 0.7570 [0.7358, 0.7777] | 0.6681 | 0.8732 | 0.41 | 3.52/3.17/0.34 |
| levenshtein | gbt | many_to_one | 0.7570 [0.7358, 0.7777] | 0.6681 | 0.8732 | 0.41 | 3.52/3.17/0.34 |
| levenshtein | gbt | one_to_one | 0.7570 [0.7358, 0.7777] | 0.6681 | 0.8732 | 0.41 | 3.52/3.17/0.34 |
| levenshtein | logistic_regression | unrestricted | 0.7199 [0.6970, 0.7409] | 0.5965 | 0.9077 | 0.34 | 3.52/2.49/0.31 |
| levenshtein | logistic_regression | many_to_one | 0.7199 [0.6970, 0.7409] | 0.5965 | 0.9077 | 0.34 | 3.52/2.49/0.31 |
| levenshtein | logistic_regression | one_to_one | 0.7199 [0.6970, 0.7409] | 0.5965 | 0.9077 | 0.34 | 3.52/2.49/0.31 |
| levenshtein | random_forest | unrestricted | 0.7062 [0.6829, 0.7278] | 0.6189 | 0.8220 | 0.41 | 3.52/2.17/0.28 |
| levenshtein | random_forest | many_to_one | 0.7062 [0.6829, 0.7278] | 0.6189 | 0.8220 | 0.41 | 3.52/2.17/0.28 |
| levenshtein | random_forest | one_to_one | 0.7062 [0.6829, 0.7278] | 0.6189 | 0.8220 | 0.41 | 3.52/2.17/0.28 |
| jaro_winkler | gbt | unrestricted | 0.7488 [0.7272, 0.7697] | 0.6658 | 0.8554 | 0.42 | 3.55/2.54/0.27 |
| jaro_winkler | gbt | many_to_one | 0.7488 [0.7272, 0.7697] | 0.6658 | 0.8554 | 0.42 | 3.55/2.54/0.27 |
| jaro_winkler | gbt | one_to_one | 0.7488 [0.7272, 0.7697] | 0.6658 | 0.8554 | 0.42 | 3.55/2.54/0.27 |
| jaro_winkler | logistic_regression | unrestricted | 0.7172 [0.6940, 0.7391] | 0.6085 | 0.8732 | 0.36 | 3.55/1.84/0.27 |
| jaro_winkler | logistic_regression | many_to_one | 0.7172 [0.6940, 0.7391] | 0.6085 | 0.8732 | 0.36 | 3.55/1.84/0.27 |
| jaro_winkler | logistic_regression | one_to_one | 0.7172 [0.6940, 0.7391] | 0.6085 | 0.8732 | 0.36 | 3.55/1.84/0.27 |
| jaro_winkler | random_forest | unrestricted | 0.7071 [0.6838, 0.7280] | 0.6095 | 0.8420 | 0.40 | 3.55/2.16/0.29 |
| jaro_winkler | random_forest | many_to_one | 0.7071 [0.6838, 0.7280] | 0.6095 | 0.8420 | 0.40 | 3.55/2.16/0.29 |
| jaro_winkler | random_forest | one_to_one | 0.7071 [0.6838, 0.7280] | 0.6095 | 0.8420 | 0.40 | 3.55/2.16/0.29 |
| both | gbt | unrestricted | 0.7556 [0.7337, 0.7757] | 0.6678 | 0.8699 | 0.41 | 3.45/2.65/0.27 |
| both | gbt | many_to_one | 0.7556 [0.7337, 0.7757] | 0.6678 | 0.8699 | 0.41 | 3.45/2.65/0.27 |
| both | gbt | one_to_one | 0.7556 [0.7337, 0.7757] | 0.6678 | 0.8699 | 0.41 | 3.45/2.65/0.27 |
| both | logistic_regression | unrestricted | 0.7173 [0.6941, 0.7388] | 0.6092 | 0.8721 | 0.36 | 3.45/1.95/0.28 |
| both | logistic_regression | many_to_one | 0.7173 [0.6941, 0.7388] | 0.6092 | 0.8721 | 0.36 | 3.45/1.95/0.28 |
| both | logistic_regression | one_to_one | 0.7173 [0.6941, 0.7388] | 0.6092 | 0.8721 | 0.36 | 3.45/1.95/0.28 |
| both | random_forest | unrestricted | 0.7229 [0.7010, 0.7435] | 0.6082 | 0.8910 | 0.39 | 3.45/2.19/0.29 |
| both | random_forest | many_to_one | 0.7229 [0.7010, 0.7435] | 0.6082 | 0.8910 | 0.39 | 3.45/2.19/0.29 |
| both | random_forest | one_to_one | 0.7229 [0.7010, 0.7435] | 0.6082 | 0.8910 | 0.39 | 3.45/2.19/0.29 |

- Baseline nearest_neighbour: F1 0.6118, threshold 0.00, mean present-field Levenshtein.
- Baseline scalar_threshold: F1 0.6162, threshold 0.18, mean present-field Levenshtein.

## abt_buy

Run [20260920T004259Z-methods-abt_buy-6099bc](../experiments/20260920T004259Z-methods-abt_buy-6099bc/manifest.json); scope: supplied labelled pairs only. Preparation/Spark/output wall: 86.0s; complete runner wall including evidence hashing/compression and cleanup: 114.6s.

| String | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| levenshtein | gbt | unrestricted | 0.6392 [0.5816, 0.6903] | 0.6316 | 0.6471 | 0.22 | 7.86/2.92/0.30 |
| levenshtein | logistic_regression | unrestricted | 0.5943 [0.5385, 0.6483] | 0.5727 | 0.6176 | 0.21 | 7.86/2.30/0.24 |
| levenshtein | random_forest | unrestricted | 0.6016 [0.5441, 0.6562] | 0.6514 | 0.5588 | 0.20 | 7.86/1.91/0.24 |
| jaro_winkler | gbt | unrestricted | 0.6158 [0.5570, 0.6700] | 0.6402 | 0.5931 | 0.22 | 8.39/2.30/0.22 |
| jaro_winkler | logistic_regression | unrestricted | 0.5787 [0.5196, 0.6343] | 0.6000 | 0.5588 | 0.25 | 8.39/1.50/0.22 |
| jaro_winkler | random_forest | unrestricted | 0.5932 [0.5330, 0.6478] | 0.6384 | 0.5539 | 0.21 | 8.39/1.71/0.22 |
| both | gbt | unrestricted | 0.6279 [0.5732, 0.6791] | 0.5973 | 0.6618 | 0.19 | 8.30/2.30/0.22 |
| both | logistic_regression | unrestricted | 0.5855 [0.5294, 0.6416] | 0.6209 | 0.5539 | 0.27 | 8.30/1.56/0.24 |
| both | random_forest | unrestricted | 0.6006 [0.5394, 0.6576] | 0.6855 | 0.5343 | 0.22 | 8.30/1.77/0.21 |

- Baseline nearest_neighbour: F1 0.3239, threshold 0.00, mean present-field Levenshtein.
- Baseline scalar_threshold: F1 0.3400, threshold 0.30, mean present-field Levenshtein.

## affiliations

Run [20260920T004459Z-methods-affiliations-3f2df5](../experiments/20260920T004459Z-methods-affiliations-3f2df5/manifest.json); scope: supplied labelled pairs only. Preparation/Spark/output wall: 75.6s; complete runner wall including evidence hashing/compression and cleanup: 103.5s.

| String | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| levenshtein | gbt | unrestricted | 0.9395 [0.9292, 0.9485] | 0.9855 | 0.8975 | 0.64 | 3.26/3.29/0.30 |
| levenshtein | logistic_regression | unrestricted | 0.9312 [0.9203, 0.9408] | 0.9670 | 0.8980 | 0.56 | 3.26/2.43/0.25 |
| levenshtein | random_forest | unrestricted | 0.9396 [0.9292, 0.9488] | 0.9790 | 0.9032 | 0.44 | 3.26/2.14/0.25 |
| jaro_winkler | gbt | unrestricted | 0.9393 [0.9289, 0.9484] | 0.9800 | 0.9018 | 0.41 | 3.56/2.57/0.20 |
| jaro_winkler | logistic_regression | unrestricted | 0.9309 [0.9195, 0.9408] | 0.9679 | 0.8966 | 0.57 | 3.56/1.75/0.24 |
| jaro_winkler | random_forest | unrestricted | 0.9392 [0.9288, 0.9483] | 0.9805 | 0.9013 | 0.56 | 3.56/1.90/0.20 |
| both | gbt | unrestricted | 0.9388 [0.9284, 0.9478] | 0.9785 | 0.9023 | 0.48 | 3.33/2.57/0.22 |
| both | logistic_regression | unrestricted | 0.9315 [0.9210, 0.9410] | 0.9623 | 0.9027 | 0.54 | 3.33/1.93/0.29 |
| both | random_forest | unrestricted | 0.9398 [0.9294, 0.9490] | 0.9805 | 0.9023 | 0.47 | 3.33/1.98/0.22 |

- Baseline nearest_neighbour: F1 0.2264, threshold 0.00, mean present-field Levenshtein.
- Baseline scalar_threshold: F1 0.7600, threshold 0.26, mean present-field Levenshtein.

## amazon_google

Run [20260920T004648Z-methods-amazon_google-96dc91](../experiments/20260920T004648Z-methods-amazon_google-96dc91/manifest.json); scope: supplied labelled pairs only. Preparation/Spark/output wall: 68.7s; complete runner wall including evidence hashing/compression and cleanup: 96.7s.

| String | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| levenshtein | gbt | unrestricted | 0.6339 [0.5880, 0.6789] | 0.5657 | 0.7209 | 0.27 | 2.08/3.08/0.32 |
| levenshtein | logistic_regression | unrestricted | 0.6562 [0.6067, 0.7026] | 0.6309 | 0.6837 | 0.32 | 2.08/2.27/0.28 |
| levenshtein | random_forest | unrestricted | 0.6112 [0.5629, 0.6575] | 0.5232 | 0.7349 | 0.17 | 2.08/1.95/0.31 |
| jaro_winkler | gbt | unrestricted | 0.6343 [0.5894, 0.6802] | 0.5607 | 0.7302 | 0.25 | 2.25/2.41/0.23 |
| jaro_winkler | logistic_regression | unrestricted | 0.6510 [0.6052, 0.6947] | 0.5627 | 0.7721 | 0.24 | 2.25/1.59/0.23 |
| jaro_winkler | random_forest | unrestricted | 0.6145 [0.5680, 0.6588] | 0.5304 | 0.7302 | 0.21 | 2.25/1.77/0.24 |
| both | gbt | unrestricted | 0.6349 [0.5880, 0.6795] | 0.5536 | 0.7442 | 0.24 | 1.97/2.39/0.20 |
| both | logistic_regression | unrestricted | 0.6559 [0.6076, 0.7009] | 0.5806 | 0.7535 | 0.27 | 1.97/1.71/0.23 |
| both | random_forest | unrestricted | 0.6038 [0.5585, 0.6481] | 0.4783 | 0.8186 | 0.16 | 1.97/1.83/0.24 |

- Baseline nearest_neighbour: F1 0.3306, threshold 0.00, mean present-field Levenshtein.
- Baseline scalar_threshold: F1 0.3315, threshold 0.60, mean present-field Levenshtein.

## walmart_amazon

Run [20260920T004831Z-methods-walmart_amazon-26c55c](../experiments/20260920T004831Z-methods-walmart_amazon-26c55c/manifest.json); scope: supplied labelled pairs only. Preparation/Spark/output wall: 80.0s; complete runner wall including evidence hashing/compression and cleanup: 108.7s.

| String | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| levenshtein | gbt | unrestricted | 0.7824 [0.7318, 0.8293] | 0.8353 | 0.7358 | 0.30 | 3.41/3.05/0.33 |
| levenshtein | logistic_regression | unrestricted | 0.7172 [0.6606, 0.7706] | 0.8200 | 0.6373 | 0.31 | 3.41/2.35/0.28 |
| levenshtein | random_forest | unrestricted | 0.7572 [0.7003, 0.8094] | 0.8562 | 0.6788 | 0.18 | 3.41/2.01/0.25 |
| jaro_winkler | gbt | unrestricted | 0.8128 [0.7660, 0.8541] | 0.8398 | 0.7876 | 0.28 | 3.49/2.44/0.25 |
| jaro_winkler | logistic_regression | unrestricted | 0.7154 [0.6589, 0.7655] | 0.7500 | 0.6839 | 0.26 | 3.49/1.72/0.25 |
| jaro_winkler | random_forest | unrestricted | 0.7934 [0.7423, 0.8389] | 0.8471 | 0.7461 | 0.16 | 3.49/1.95/0.23 |
| both | gbt | unrestricted | 0.8128 [0.7656, 0.8543] | 0.8398 | 0.7876 | 0.27 | 3.44/2.48/0.26 |
| both | logistic_regression | unrestricted | 0.7143 [0.6613, 0.7627] | 0.7035 | 0.7254 | 0.23 | 3.44/1.78/0.25 |
| both | random_forest | unrestricted | 0.7636 [0.7102, 0.8099] | 0.7656 | 0.7617 | 0.12 | 3.44/2.08/0.25 |

- Baseline nearest_neighbour: F1 0.3018, threshold 0.00, mean present-field Levenshtein.
- Baseline scalar_threshold: F1 0.2763, threshold 0.61, mean present-field Levenshtein.

## dblp_acm

Run [20260920T005027Z-methods-dblp_acm-8ca1eb](../experiments/20260920T005027Z-methods-dblp_acm-8ca1eb/manifest.json); scope: supplied labelled pairs only. Preparation/Spark/output wall: 93.5s; complete runner wall including evidence hashing/compression and cleanup: 122.1s.

| String | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |
|---|---|---|---|---:|---:|---:|---|
| levenshtein | gbt | unrestricted | 0.9853 [0.9756, 0.9932] | 0.9820 | 0.9887 | 0.47 | 4.06/3.13/0.36 |
| levenshtein | gbt | many_to_one | 0.9864 [0.9779, 0.9938] | 0.9842 | 0.9887 | 0.47 | 4.06/3.13/0.36 |
| levenshtein | gbt | one_to_one | 0.9887 [0.9812, 0.9955] | 0.9821 | 0.9955 | 0.33 | 4.06/3.13/0.36 |
| levenshtein | logistic_regression | unrestricted | 0.9830 [0.9729, 0.9913] | 0.9841 | 0.9819 | 0.71 | 4.06/2.50/0.26 |
| levenshtein | logistic_regression | many_to_one | 0.9841 [0.9753, 0.9916] | 0.9863 | 0.9819 | 0.71 | 4.06/2.50/0.26 |
| levenshtein | logistic_regression | one_to_one | 0.9865 [0.9781, 0.9933] | 0.9799 | 0.9932 | 0.45 | 4.06/2.50/0.26 |
| levenshtein | random_forest | unrestricted | 0.9831 [0.9735, 0.9916] | 0.9754 | 0.9909 | 0.42 | 4.06/2.08/0.25 |
| levenshtein | random_forest | many_to_one | 0.9842 [0.9755, 0.9921] | 0.9776 | 0.9909 | 0.42 | 4.06/2.08/0.25 |
| levenshtein | random_forest | one_to_one | 0.9865 [0.9785, 0.9934] | 0.9820 | 0.9909 | 0.42 | 4.06/2.08/0.25 |
| jaro_winkler | gbt | unrestricted | 0.9865 [0.9779, 0.9942] | 0.9756 | 0.9977 | 0.41 | 4.23/2.47/0.23 |
| jaro_winkler | gbt | many_to_one | 0.9877 [0.9802, 0.9945] | 0.9778 | 0.9977 | 0.41 | 4.23/2.47/0.23 |
| jaro_winkler | gbt | one_to_one | 0.9910 [0.9843, 0.9967] | 0.9843 | 0.9977 | 0.41 | 4.23/2.47/0.23 |
| jaro_winkler | logistic_regression | unrestricted | 0.9841 [0.9747, 0.9923] | 0.9841 | 0.9841 | 0.69 | 4.23/1.72/0.23 |
| jaro_winkler | logistic_regression | many_to_one | 0.9852 [0.9770, 0.9928] | 0.9864 | 0.9841 | 0.69 | 4.23/1.72/0.23 |
| jaro_winkler | logistic_regression | one_to_one | 0.9876 [0.9797, 0.9942] | 0.9821 | 0.9932 | 0.52 | 4.23/1.72/0.23 |
| jaro_winkler | random_forest | unrestricted | 0.9831 [0.9732, 0.9917] | 0.9776 | 0.9887 | 0.50 | 4.23/1.89/0.23 |
| jaro_winkler | random_forest | many_to_one | 0.9842 [0.9755, 0.9921] | 0.9798 | 0.9887 | 0.50 | 4.23/1.89/0.23 |
| jaro_winkler | random_forest | one_to_one | 0.9875 [0.9799, 0.9944] | 0.9864 | 0.9887 | 0.50 | 4.23/1.89/0.23 |
| both | gbt | unrestricted | 0.9865 [0.9779, 0.9942] | 0.9756 | 0.9977 | 0.39 | 4.12/2.46/0.26 |
| both | gbt | many_to_one | 0.9877 [0.9802, 0.9945] | 0.9778 | 0.9977 | 0.39 | 4.12/2.46/0.26 |
| both | gbt | one_to_one | 0.9910 [0.9843, 0.9967] | 0.9843 | 0.9977 | 0.39 | 4.12/2.46/0.26 |
| both | logistic_regression | unrestricted | 0.9830 [0.9733, 0.9914] | 0.9819 | 0.9841 | 0.70 | 4.12/1.68/0.23 |
| both | logistic_regression | many_to_one | 0.9841 [0.9752, 0.9921] | 0.9841 | 0.9841 | 0.70 | 4.12/1.68/0.23 |
| both | logistic_regression | one_to_one | 0.9865 [0.9781, 0.9933] | 0.9799 | 0.9932 | 0.47 | 4.12/1.68/0.23 |
| both | random_forest | unrestricted | 0.9830 [0.9730, 0.9917] | 0.9841 | 0.9819 | 0.57 | 4.12/1.94/0.25 |
| both | random_forest | many_to_one | 0.9841 [0.9752, 0.9920] | 0.9863 | 0.9819 | 0.57 | 4.12/1.94/0.25 |
| both | random_forest | one_to_one | 0.9865 [0.9785, 0.9933] | 0.9799 | 0.9932 | 0.31 | 4.12/1.94/0.25 |

- Baseline nearest_neighbour: F1 0.5225, threshold 0.00, mean present-field Levenshtein.
- Baseline scalar_threshold: F1 0.9024, threshold 0.56, mean present-field Levenshtein.

## Macro validation results

Seven equally weighted corpora; FEBRL all/SSN-hidden split one vote. The diagnostic does not vote.
Within each trial, the best permitted validation policy is used. Macro intervals use 2,000 paired group resamples,
PCG64 seeded by SHA-256 of bootstrap seed 2026091902 and corpus name; FEBRL variants share entity draws.

| Configuration | Macro F1 [95% CI] | Paired change CI vs Levenshtein/GBT | Weighted feature/fit/score s |
|---|---|---|---:|
| both__gbt | 0.8230 [0.8099, 0.8348] | [-0.0025, +0.0086] | 6.89 |
| both__logistic_regression | 0.7987 [0.7840, 0.8121] | [-0.0321, -0.0107] | 6.23 |
| both__random_forest | 0.8024 [0.7884, 0.8154] | [-0.0276, -0.0080] | 6.44 |
| jaro_winkler__gbt | 0.8203 [0.8071, 0.8322] | [-0.0069, +0.0072] | 7.00 |
| jaro_winkler__logistic_regression | 0.7973 [0.7832, 0.8106] | [-0.0339, -0.0117] | 6.26 |
| jaro_winkler__random_forest | 0.8050 [0.7907, 0.8177] | [-0.0253, -0.0056] | 6.50 |
| levenshtein__gbt | 0.8201 [0.8067, 0.8325] | [+0.0000, +0.0000] | 7.50 |
| levenshtein__logistic_regression | 0.8008 [0.7855, 0.8139] | [-0.0308, -0.0087] | 6.76 |
| levenshtein__random_forest | 0.8003 [0.7858, 0.8132] | [-0.0306, -0.0095] | 6.43 |

No models were promoted by this report. Each trial links to its composite MLflow model in the structured evidence.
The remaining retrieval/F1, final latency, scale and confirmation gates retain their separate requirements.
