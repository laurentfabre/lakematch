# Retrieval and classifier validation

Closed-world FEBRL half-unmatched tasks under [LINKAGE_PLAN.md](LINKAGE_PLAN.md). Confirmation is unscored.
All methods retrieve the complete 5,000-left / 2,500-right universe. Training pairs have both endpoints in training; only validation anchors receive classifier scores.
Intervals are conditional on the validation-selected threshold and policy; they do not adjust for selection optimism.

| Variant | Retriever | Policy | F1 [95% CI] | Recall@5 | Threshold | Retrieval s | Feature/fit s |
|---|---|---|---|---:|---:|---:|---:|
| all | gram_topk | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.95 | 33.73 | 5.52 |
| all | gram_topk | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.95 | 33.73 | 5.52 |
| all | gram_topk | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.95 | 33.73 | 5.52 |
| all | learned_blocker | one_to_one | 0.9990 [0.9963, 1.0000] | 0.9980 | 0.84 | 1.65 | 3.64 |
| all | learned_blocker | many_to_one | 0.9990 [0.9963, 1.0000] | 0.9980 | 0.84 | 1.65 | 3.64 |
| all | learned_blocker | unrestricted | 0.9990 [0.9963, 1.0000] | 0.9980 | 0.84 | 1.65 | 3.64 |
| all | minhash_lsh | one_to_one | 0.9889 [0.9821, 0.9950] | 0.9780 | 0.28 | 11.81 | 4.48 |
| all | minhash_lsh | many_to_one | 0.9889 [0.9821, 0.9950] | 0.9780 | 0.28 | 11.81 | 4.48 |
| all | minhash_lsh | unrestricted | 0.9889 [0.9821, 0.9950] | 0.9780 | 0.28 | 11.81 | 4.48 |
| all | field_blocks | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.87 | 8.52 | 4.55 |
| all | field_blocks | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.87 | 8.52 | 4.55 |
| all | field_blocks | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.87 | 8.52 | 4.55 |
| all | union | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.70 | 47.47 | 4.58 |
| all | union | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.70 | 47.47 | 4.58 |
| all | union | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.70 | 47.47 | 4.58 |
| no_ssn | gram_topk | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.95 | 28.76 | 5.26 |
| no_ssn | gram_topk | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.95 | 28.76 | 5.26 |
| no_ssn | gram_topk | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.95 | 28.76 | 5.26 |
| no_ssn | learned_blocker | one_to_one | 0.9940 [0.9888, 0.9981] | 0.9900 | 0.35 | 1.57 | 3.78 |
| no_ssn | learned_blocker | many_to_one | 0.9940 [0.9888, 0.9981] | 0.9900 | 0.35 | 1.57 | 3.78 |
| no_ssn | learned_blocker | unrestricted | 0.9940 [0.9888, 0.9981] | 0.9900 | 0.35 | 1.57 | 3.78 |
| no_ssn | minhash_lsh | one_to_one | 0.9869 [0.9794, 0.9932] | 0.9780 | 0.85 | 10.79 | 4.29 |
| no_ssn | minhash_lsh | many_to_one | 0.9869 [0.9794, 0.9932] | 0.9780 | 0.85 | 10.79 | 4.29 |
| no_ssn | minhash_lsh | unrestricted | 0.9869 [0.9794, 0.9932] | 0.9780 | 0.85 | 10.79 | 4.29 |
| no_ssn | field_blocks | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.61 | 7.71 | 4.24 |
| no_ssn | field_blocks | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.61 | 7.71 | 4.24 |
| no_ssn | field_blocks | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.61 | 7.71 | 4.24 |
| no_ssn | union | one_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.61 | 40.27 | 4.33 |
| no_ssn | union | many_to_one | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.61 | 40.27 | 4.33 |
| no_ssn | union | unrestricted | 1.0000 [1.0000, 1.0000] | 1.0000 | 0.61 | 40.27 | 4.33 |
| no_ssn_dob | gram_topk | one_to_one | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.89 | 23.56 | 4.88 |
| no_ssn_dob | gram_topk | many_to_one | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.89 | 23.56 | 4.88 |
| no_ssn_dob | gram_topk | unrestricted | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.89 | 23.56 | 4.88 |
| no_ssn_dob | learned_blocker | one_to_one | 0.9879 [0.9807, 0.9941] | 0.9820 | 0.93 | 1.71 | 3.76 |
| no_ssn_dob | learned_blocker | many_to_one | 0.9869 [0.9796, 0.9934] | 0.9820 | 0.93 | 1.71 | 3.76 |
| no_ssn_dob | learned_blocker | unrestricted | 0.9869 [0.9796, 0.9934] | 0.9820 | 0.93 | 1.71 | 3.76 |
| no_ssn_dob | minhash_lsh | one_to_one | 0.9879 [0.9810, 0.9940] | 0.9780 | 0.57 | 9.32 | 3.99 |
| no_ssn_dob | minhash_lsh | many_to_one | 0.9879 [0.9810, 0.9940] | 0.9780 | 0.57 | 9.32 | 3.99 |
| no_ssn_dob | minhash_lsh | unrestricted | 0.9879 [0.9810, 0.9940] | 0.9780 | 0.57 | 9.32 | 3.99 |
| no_ssn_dob | field_blocks | one_to_one | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.94 | 5.61 | 4.04 |
| no_ssn_dob | field_blocks | many_to_one | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.94 | 5.61 | 4.04 |
| no_ssn_dob | field_blocks | unrestricted | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.94 | 5.61 | 4.04 |
| no_ssn_dob | union | one_to_one | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.94 | 34.39 | 3.94 |
| no_ssn_dob | union | many_to_one | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.94 | 34.39 | 3.94 |
| no_ssn_dob | union | unrestricted | 0.9990 [0.9969, 1.0000] | 1.0000 | 0.94 | 34.39 | 3.94 |

Stage costs share Spark startup and preparation; these measurements do not establish the 60-second end-to-end gate.
The seven-corpus retrieval findings and classifier/feature macro comparison remain necessary to choose general defaults. No default or model is promoted by this report.

- `all`: [20260920T013615Z-linkage-all-f5b121](../experiments/20260920T013615Z-linkage-all-f5b121/manifest.json).
- `no_ssn`: [20260920T013914Z-linkage-no_ssn-963e3e](../experiments/20260920T013914Z-linkage-no_ssn-963e3e/manifest.json).
- `no_ssn_dob`: [20260920T014157Z-linkage-no_ssn_dob-e29437](../experiments/20260920T014157Z-linkage-no_ssn_dob-e29437/manifest.json).
