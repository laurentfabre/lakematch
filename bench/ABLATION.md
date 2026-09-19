# Feature ablations on validation data

These are validation-selection measurements, not ZR-3 confirmation results. The confirmation seed and all confirmation/test scores remain untouched. The fixed configurations and sampling rules are in [ABLATION_PLAN.md](ABLATION_PLAN.md).

Every interval uses 2,000 paired anchor/group bootstrap resamples, seed 2026091902. Thresholds are independently selected on validation; the intervals describe sampling uncertainty and do not correct for threshold or feature selection optimism. Removing a family does not isolate its causal value because the GBT is refitted.

## febrl4_half_all

Run [`20260919T224028Z-ablation-febrl4-08728c`](../experiments/20260919T224028Z-ablation-febrl4-08728c/manifest.json); complete corpus-run wall time 118.65s. This includes all ablations and is not the single-run latency gate.

| Configuration | Validation F1 [95% CI] | Paired change CI vs native-all | Precision | Recall | Threshold | Feature / fit / score seconds |
|---|---|---|---:|---:|---:|---|
| native_all | 1.0000 [1.0000, 1.0000] | [0.0000, 0.0000] | 1.0000 | 1.0000 | 0.95 | 3.60 / 3.67 / 0.54 |
| without_field_families | 1.0000 [1.0000, 1.0000] | [0.0000, 0.0000] | 1.0000 | 1.0000 | 0.95 | 3.06 / 2.95 / 0.38 |
| without_idf | 1.0000 [1.0000, 1.0000] | [0.0000, 0.0000] | 1.0000 | 1.0000 | 0.95 | 2.87 / 2.97 / 0.39 |
| without_grams | 1.0000 [1.0000, 1.0000] | [0.0000, 0.0000] | 1.0000 | 1.0000 | 0.95 | 2.33 / 2.94 / 0.42 |
| without_monge | 1.0000 [1.0000, 1.0000] | [0.0000, 0.0000] | 1.0000 | 1.0000 | 0.95 | 2.36 / 2.90 / 0.40 |
| plus_jaro_winkler | 1.0000 [1.0000, 1.0000] | [0.0000, 0.0000] | 1.0000 | 1.0000 | 0.95 | 3.80 / 3.02 / 0.41 |
| plus_affine | 1.0000 [1.0000, 1.0000] | [0.0000, 0.0000] | 1.0000 | 1.0000 | 0.95 | 3.58 / 3.07 / 0.46 |
| without_address_fields | 1.0000 [1.0000, 1.0000] | [0.0000, 0.0000] | 1.0000 | 1.0000 | 0.95 | 2.49 / 2.96 / 0.39 |
| without_code_fields | 1.0000 [1.0000, 1.0000] | [0.0000, 0.0000] | 1.0000 | 1.0000 | 0.95 | 2.71 / 2.88 / 0.36 |
| without_date_fields | 1.0000 [1.0000, 1.0000] | [0.0000, 0.0000] | 1.0000 | 1.0000 | 0.95 | 3.10 / 3.12 / 0.42 |
| without_person_name_fields | 1.0000 [1.0000, 1.0000] | [0.0000, 0.0000] | 1.0000 | 1.0000 | 0.95 | 2.98 / 3.15 / 0.45 |

Precomputed candidates and training IDF are shared across variants; feature, fit and score times exclude that shared work and model preparation. Native variants' explain plans have no Python UDF evaluation. Optional similarities are explicitly outside that claim.

Validation candidate recall@5: **1.0000**. Projected join rows before/after cap: 71,355,234 / 17,252,022; final candidates 25,000. Both training endpoints are restricted to training records; validation retrieval uses the full unlabeled universe.

Baseline `nearest_neighbour`: F1 0.6667 [0.6376, 0.6962], threshold 0.00.

Baseline `cosine_threshold`: F1 1.0000 [1.0000, 1.0000], threshold 0.54.

Split: SHA-256 ranked whole truth entities 3000/1000/1000; independent namespaced partner-removal ranking. Duplicate/reversed pair keys removed: 0; conflicting keys excluded: 0. Shared records: `{}`.

## bpid

Run [`20260919T224228Z-ablation-bpid-67a740`](../experiments/20260919T224228Z-ablation-bpid-67a740/manifest.json); complete corpus-run wall time 84.69s. This includes all ablations and is not the single-run latency gate.

| Configuration | Validation F1 [95% CI] | Paired change CI vs native-all | Precision | Recall | Threshold | Feature / fit / score seconds |
|---|---|---|---:|---:|---:|---|
| native_all | 0.7570 [0.7358, 0.7777] | [0.0000, 0.0000] | 0.6681 | 0.8732 | 0.41 | 3.49 / 3.15 / 0.38 |
| without_field_families | 0.7492 [0.7261, 0.7692] | [-0.0193, 0.0027] | 0.6423 | 0.8988 | 0.38 | 2.87 / 2.47 / 0.26 |
| without_idf | 0.7471 [0.7247, 0.7670] | [-0.0208, 0.0006] | 0.6579 | 0.8643 | 0.41 | 2.76 / 2.38 / 0.25 |
| without_grams | 0.7564 [0.7340, 0.7773] | [-0.0108, 0.0094] | 0.6794 | 0.8532 | 0.42 | 1.89 / 2.32 / 0.25 |
| without_monge | 0.7546 [0.7335, 0.7745] | [-0.0134, 0.0085] | 0.6544 | 0.8910 | 0.39 | 2.25 / 2.24 / 0.24 |
| plus_jaro_winkler | 0.7556 [0.7337, 0.7757] | [-0.0097, 0.0059] | 0.6678 | 0.8699 | 0.41 | 3.56 / 2.38 / 0.27 |
| plus_affine | 0.7520 [0.7293, 0.7727] | [-0.0181, 0.0084] | 0.6830 | 0.8365 | 0.42 | 5.44 / 2.37 / 0.24 |
| without_address_fields | 0.7333 [0.7091, 0.7548] | [-0.0413, -0.0071] | 0.6770 | 0.7998 | 0.44 | 1.85 / 2.27 / 0.25 |
| without_code_fields | 0.7157 [0.6932, 0.7359] | [-0.0624, -0.0208] | 0.6152 | 0.8554 | 0.37 | 2.16 / 2.20 / 0.22 |
| without_date_fields | 0.7303 [0.7081, 0.7506] | [-0.0403, -0.0129] | 0.6322 | 0.8643 | 0.39 | 2.75 / 2.26 / 0.27 |
| without_person_name_fields | 0.7316 [0.7088, 0.7530] | [-0.0397, -0.0118] | 0.6295 | 0.8732 | 0.36 | 2.74 / 2.31 / 0.26 |

Precomputed candidates and training IDF are shared across variants; feature, fit and score times exclude that shared work and model preparation. Native variants' explain plans have no Python UDF evaluation. Optional similarities are explicitly outside that claim.

Supplied labeled-pair evaluation: candidate recall is not applicable. Unlabeled pairs are never silently treated as negatives.

Baseline `mean_levenshtein_threshold`: F1 0.6162 [0.5941, 0.6366], threshold 0.18.

Split: record_components. Duplicate/reversed pair keys removed: 0; conflicting keys excluded: 0. Shared records: `{"confirmation/train": 0, "confirmation/valid": 0, "train/valid": 0}`.

## abt_buy

Run [`20260919T224353Z-ablation-abt_buy-9f9d5c`](../experiments/20260919T224353Z-ablation-abt_buy-9f9d5c/manifest.json); complete corpus-run wall time 120.62s. This includes all ablations and is not the single-run latency gate.

| Configuration | Validation F1 [95% CI] | Paired change CI vs native-all | Precision | Recall | Threshold | Feature / fit / score seconds |
|---|---|---|---:|---:|---:|---|
| native_all | 0.6392 [0.5816, 0.6903] | [0.0000, 0.0000] | 0.6316 | 0.6471 | 0.22 | 7.91 / 2.95 / 0.31 |
| without_field_families | 0.6150 [0.5594, 0.6698] | [-0.0677, 0.0157] | 0.6077 | 0.6225 | 0.23 | 7.27 / 2.18 / 0.21 |
| without_idf | 0.6168 [0.5566, 0.6728] | [-0.0766, 0.0299] | 0.7923 | 0.5049 | 0.35 | 7.37 / 2.19 / 0.21 |
| without_grams | 0.6221 [0.5617, 0.6774] | [-0.0464, 0.0114] | 0.6541 | 0.5931 | 0.23 | 2.33 / 2.09 / 0.21 |
| without_monge | 0.6458 [0.5889, 0.6975] | [-0.0159, 0.0285] | 0.6351 | 0.6569 | 0.21 | 5.98 / 2.07 / 0.19 |
| plus_jaro_winkler | 0.6279 [0.5732, 0.6791] | [-0.0313, 0.0092] | 0.5973 | 0.6618 | 0.19 | 8.39 / 2.14 / 0.22 |
| plus_affine | 0.6392 [0.5844, 0.6895] | [-0.0224, 0.0234] | 0.6316 | 0.6471 | 0.21 | 20.33 / 2.10 / 0.21 |
| embedding_on | 0.6282 [0.5736, 0.6819] | [-0.0460, 0.0231] | 0.5939 | 0.6667 | 0.21 | 7.92 / 2.27 / 0.25 |
| without_number_fields | 0.6346 [0.5766, 0.6874] | [-0.0286, 0.0180] | 0.6226 | 0.6471 | 0.21 | 7.37 / 2.02 / 0.18 |
| without_title_fields | 0.2077 [0.1841, 0.2312] | [-0.4824, -0.3789] | 0.1159 | 0.9951 | 0.10 | 0.64 / 1.95 / 0.19 |

Precomputed candidates and training IDF are shared across variants; feature, fit and score times exclude that shared work and model preparation. Native variants' explain plans have no Python UDF evaluation. Optional similarities are explicitly outside that claim.

Supplied labeled-pair evaluation: candidate recall is not applicable. Unlabeled pairs are never silently treated as negatives.

Baseline `mean_levenshtein_threshold`: F1 0.3400 [0.2965, 0.3826], threshold 0.30.

Split: official. Duplicate/reversed pair keys removed: 39; conflicting keys excluded: 13. Shared records: `{"test/train": 1307, "test/valid": 1041, "train/valid": 1300}`.

Local MiniLM preparation: 2,103 record-side inputs in **7.61s**; **362.0s per 100,000 records**, linearly extrapolated, not a measured 100,000-record throughput result. Empty values produce missing embeddings. The model snapshot and output vectors are content-hashed in the raw report.

## affiliations

Run [`20260919T224556Z-ablation-affiliations-e9f006`](../experiments/20260919T224556Z-ablation-affiliations-e9f006/manifest.json); complete corpus-run wall time 78.79s. This includes all ablations and is not the single-run latency gate.

| Configuration | Validation F1 [95% CI] | Paired change CI vs native-all | Precision | Recall | Threshold | Feature / fit / score seconds |
|---|---|---|---:|---:|---:|---|
| native_all | 0.9395 [0.9292, 0.9485] | [0.0000, 0.0000] | 0.9855 | 0.8975 | 0.64 | 3.28 / 3.29 / 0.35 |
| without_field_families | 0.9387 [0.9280, 0.9482] | [-0.0030, 0.0015] | 0.9805 | 0.9004 | 0.57 | 2.80 / 2.55 / 0.26 |
| without_idf | 0.8645 [0.8452, 0.8807] | [-0.0917, -0.0604] | 0.8737 | 0.8555 | 0.59 | 2.92 / 2.45 / 0.22 |
| without_grams | 0.9395 [0.9290, 0.9485] | [-0.0019, 0.0020] | 0.9810 | 0.9013 | 0.55 | 1.37 / 2.33 / 0.25 |
| without_monge | 0.9395 [0.9290, 0.9485] | [-0.0019, 0.0020] | 0.9810 | 0.9013 | 0.55 | 2.26 / 2.29 / 0.22 |
| plus_jaro_winkler | 0.9389 [0.9285, 0.9481] | [-0.0021, 0.0008] | 0.9825 | 0.8990 | 0.57 | 3.71 / 2.44 / 0.21 |
| plus_affine | 0.9445 [0.9344, 0.9531] | [0.0012, 0.0084] | 0.9754 | 0.9155 | 0.43 | 9.23 / 2.33 / 0.20 |
| embedding_on | 0.9429 [0.9331, 0.9515] | [-0.0004, 0.0074] | 0.9758 | 0.9122 | 0.58 | 3.58 / 2.53 / 0.32 |
| without_organisation_fields | 0.6951 [0.6651, 0.7216] | [-0.2751, -0.2159] | 0.5327 | 1.0000 | 0.59 | 0.30 / 1.65 / 0.18 |

Precomputed candidates and training IDF are shared across variants; feature, fit and score times exclude that shared work and model preparation. Native variants' explain plans have no Python UDF evaluation. Optional similarities are explicitly outside that claim.

Supplied labeled-pair evaluation: candidate recall is not applicable. Unlabeled pairs are never silently treated as negatives.

Baseline `mean_levenshtein_threshold`: F1 0.7600 [0.7387, 0.7805], threshold 0.26.

Split: released identity components 60/20/20, SHA-256 ranking. Duplicate/reversed pair keys removed: 145; conflicting keys excluded: 0. Shared records: `{"confirmation/train": 0, "confirmation/valid": 0, "train/valid": 0}`.

Local MiniLM preparation: 4,512 record-side inputs in **6.44s**; **142.7s per 100,000 records**, linearly extrapolated, not a measured 100,000-record throughput result. Empty values produce missing embeddings. The model snapshot and output vectors are content-hashed in the raw report.

## Interpretation and retained failures

Embedding features are **off by default** (`fields_of_type: []`): neither corpus's paired interval excludes zero in the positive direction. The optional offline MiniLM provider remains available for explicit selection. Its weights are pinned to the revision in the ablation plan.

Use the paired intervals to distinguish a measured improvement from an inconclusive difference. The full ZR-3 cross-corpus method comparison is still required before shipping benchmark winners. The original FEBRL corpus has historical development exposure, explicitly disclosed in the split manifest.

The first FEBRL attempt was canceled after a training-partition audit; its partial validation results are invalid for selection and remain archived. Two offline attempts failed before feature selection because Java dual-stack worker sockets were denied by macOS. A loopback probe isolated the cause; local Spark now uses IPv4, and the subsequent sweep asserts external network denial. Failures and cleanup results remain in the append-only run ledger.

All runs use public/synthetic corpora locally. Remote spend and live-label usage are zero for this sweep; this does not reconcile the earlier FEVM canary billing.
