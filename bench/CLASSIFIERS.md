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


Missing compatible completed runs: febrl4-no_ssn, febrl4-no_ssn_dob, bpid, abt_buy, affiliations, amazon_google, walmart_amazon, dblp_acm.

No models were promoted by this report. Each trial links to its composite MLflow model in the structured evidence.
The remaining retrieval/F1, final latency, scale and confirmation gates retain their separate requirements.
