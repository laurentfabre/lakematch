# Method selection — validation checkpoint

The classifier factorial completed all 81 fits on nine corpus configurations. All runs passed and preserved their composite MLflow models, predictions, plans and Spark event metrics. [Detailed comparison](CLASSIFIERS.md); [run index](methods_index.json). These are validation selection results. Subsequent frozen confirmation is reported separately in BENCHMARKS.md.

Select **Levenshtein + GBT**, with 20 iterations, depth 3 and seed 0. This selection follows the predeclared seven-corpus macro weighting and portability requirement. Levenshtein remains the native default; optional UDF similarities remain available.

| Configuration | Macro validation F1 | Paired change 95% CI vs Levenshtein/GBT |
|---|---:|---|
| levenshtein__gbt | 0.8201 | [+0.0000, +0.0000] |
| levenshtein__logistic_regression | 0.8008 | [-0.0308, -0.0087] |
| levenshtein__random_forest | 0.8003 | [-0.0306, -0.0095] |
| jaro_winkler__gbt | 0.8203 | [-0.0069, +0.0072] |
| both__gbt | 0.8230 | [-0.0025, +0.0086] |

The logistic-regression and random-forest intervals exclude zero in the negative direction. The Jaro-Winkler alternatives do not establish a gain. Wall-time comparisons include execution-order warmup effects; the native-plan requirement independently excludes a UDF-only default. These are validation selection scores, with threshold/policy selection optimism, not confirmation claims.

FEBRL all/SSN-hidden split one corpus vote; the SSN+DOB-hidden diagnostic does not vote. BPID and Affiliations use their frozen disjoint grouping; product/citation results retain the supplied-pair task and reported official-split shared-record caveats. Unlabelled retrieved pairs were never treated as negatives.

The full candidate/scoring comparison selected MinHash as the only method with feasible training and retrieval on every corpus; see CANDIDATES.md. This does not establish statistical superiority over methods with missing or budget-rejected outcomes. [Retrieval measurements](RETRIEVAL.md) retain all 90 method/scope outcomes and BPID budget rejections. The completed [compact-feature comparison](COMPACT_FEATURES.md) selects `idf_token_cosine` alone alongside the typed field features. It reached macro F1 0.8145 versus 0.8201 for all three token families; its paired change interval [-0.0126, +0.0014] includes zero. Weighted feature/fit/score time was 3.87s versus 7.49s. Under the predeclared simpler-choice rule, retain IDF only. This inconclusive difference is not proof of equivalence. Removing all token families caused a clear loss (macro 0.7909; paired interval entirely negative).

Shipped defaults now match the validation selections: MinHash, Levenshtein, IDF token cosine and GBT; verified merge uses the measured 30-round envelope. The eight frozen models retain their fully specified configurations, as checked by the [static config proof](config_defaults_compatibility.json). Dynamic replay and final integration acceptance remain pending. The scale ladder passed through 100,000 records and failed at one million with heap exhaustion; it is not being retried. This default adoption changes no accepted model pointer or UC alias.
