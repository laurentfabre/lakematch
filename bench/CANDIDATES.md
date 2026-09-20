# Candidate selection across seven corpora

FEBRL is closed-world linkage. Other rows are retrieval-filtered supplied-pair validation: unknown pairs remain unknown and missing positives remain false negatives. Official shared-record caveats remain in each corpus manifest.
All methods use k=5, at most 100,000 final pairs and 50 million retained join rows. [Plan](CANDIDATE_PAIRS_PLAN.md).

| Corpus | Method | Validation F1 | Recall@5 | Policy | Threshold | Status |
|---|---|---:|---:|---|---:|---|
| febrl4_half_all | gram_topk | 1.0000 | 1.0000 | one_to_one | 0.95 | completed |
| febrl4_half_all | learned_blocker | 0.9990 | 0.9980 | one_to_one | 0.84 | completed |
| febrl4_half_all | minhash_lsh | 0.9889 | 0.9780 | one_to_one | 0.28 | completed |
| febrl4_half_all | field_blocks | 1.0000 | 1.0000 | one_to_one | 0.87 | completed |
| febrl4_half_all | union | 1.0000 | 1.0000 | one_to_one | 0.70 | completed |
| febrl4_half_no_ssn | gram_topk | 1.0000 | 1.0000 | one_to_one | 0.95 | completed |
| febrl4_half_no_ssn | learned_blocker | 0.9940 | 0.9900 | one_to_one | 0.35 | completed |
| febrl4_half_no_ssn | minhash_lsh | 0.9869 | 0.9780 | one_to_one | 0.85 | completed |
| febrl4_half_no_ssn | field_blocks | 1.0000 | 1.0000 | one_to_one | 0.61 | completed |
| febrl4_half_no_ssn | union | 1.0000 | 1.0000 | one_to_one | 0.61 | completed |
| bpid | gram_topk | — | — | — | — | budget_rejected: Pre-top-k join budget exceeded: {'join_rows_before_cap': 636719883, 'join_rows_after_cap': 83426093, 'dropped_grams': 520}; limit=50000000 |
| bpid | learned_blocker | 0.4211 | 0.3270 | unrestricted | 0.21 | completed |
| bpid | minhash_lsh | 0.5794 | 0.5539 | unrestricted | 0.31 | completed |
| bpid | field_blocks | 0.6021 | 0.6218 | unrestricted | 0.38 | completed |
| bpid | union | — | — | — | — | budget_rejected: Pre-top-k join budget exceeded: {'join_rows_before_cap': 636969711, 'join_rows_after_cap': 83675921, 'dropped_grams': 520}; limit=50000000 |
| abt_buy | gram_topk | 0.8835 | 0.9902 | unrestricted | 0.45 | completed |
| abt_buy | learned_blocker | 0.2982 | 0.2206 | unrestricted | 0.11 | completed |
| abt_buy | minhash_lsh | 0.6000 | 0.6225 | unrestricted | 0.20 | completed |
| abt_buy | field_blocks | 0.7799 | 0.9314 | unrestricted | 0.25 | completed |
| abt_buy | union | 0.7799 | 0.9461 | unrestricted | 0.22 | completed |
| amazon_google | gram_topk | 0.7155 | 0.9767 | unrestricted | 0.38 | completed |
| amazon_google | learned_blocker | 0.5355 | 0.5674 | unrestricted | 0.15 | completed |
| amazon_google | minhash_lsh | 0.6856 | 0.8512 | unrestricted | 0.21 | completed |
| amazon_google | field_blocks | 0.5623 | 0.6093 | unrestricted | 0.23 | completed |
| amazon_google | union | 0.7154 | 0.9674 | unrestricted | 0.25 | completed |
| walmart_amazon | gram_topk | 0.7762 | 0.9896 | unrestricted | 0.43 | completed |
| walmart_amazon | learned_blocker | 0.6644 | 0.5751 | unrestricted | 0.24 | completed |
| walmart_amazon | minhash_lsh | 0.6624 | 0.7254 | unrestricted | 0.47 | completed |
| walmart_amazon | field_blocks | 0.7742 | 0.9637 | unrestricted | 0.32 | completed |
| walmart_amazon | union | 0.7666 | 0.9689 | unrestricted | 0.37 | completed |
| dblp_acm | gram_topk | 0.9966 | 1.0000 | one_to_one | 0.64 | completed |
| dblp_acm | learned_blocker | 0.9943 | 0.9955 | one_to_one | 0.91 | completed |
| dblp_acm | minhash_lsh | 0.9851 | 0.9751 | one_to_one | 0.73 | completed |
| dblp_acm | field_blocks | 0.9966 | 1.0000 | one_to_one | 0.65 | completed |
| dblp_acm | union | 0.9966 | 1.0000 | one_to_one | 0.71 | completed |
| affiliations | gram_topk | 0.3892 | 0.2417 | unrestricted | 0.13 | completed |
| affiliations | learned_blocker | — | — | — | — | training_unavailable: Retrieved labelled training pairs do not contain both classes |
| affiliations | minhash_lsh | 0.3594 | 0.2195 | unrestricted | 0.12 | completed |
| affiliations | field_blocks | — | — | — | — | training_unavailable: Retrieved labelled training pairs do not contain both classes |
| affiliations | union | 0.3798 | 0.2347 | unrestricted | 0.95 | completed |

Complete feasible macro comparison selects `minhash_lsh` under the predeclared paired-interval and simpler-method rule.
The intervals describe validation selection, not an equivalence test or untouched confirmation result.

| Method | Macro F1 [95% CI] | Paired change CI vs best | Weighted method s |
|---|---|---|---:|
| minhash_lsh | 0.6942 [0.6777848452954797, 0.7098322649929033] | [+0.0000, +0.0000] | 26.31 |

`minhash_lsh` is the only complete feasible method. This is a feasibility-based selection, not evidence of statistical superiority over the unavailable alternatives. A self-comparison interval of [0, 0] has no comparative meaning.

Macro gives each corpus one vote; FEBRL all/SSN-hidden split its vote. Paired intervals use 2,000 namespaced PCG64 group draws, seed derived from 2026091902/candidate_macro/corpus. Infeasible methods are not assigned zero and no corpus is omitted to make their macro complete.

This selection used no confirmation scores and promoted no model. Subsequent held-out measurements are reported in BENCHMARKS.md. Shared-session stage costs do not establish the local 60-second gate.

- `febrl4_half_all`: [20260920T013615Z-linkage-all-f5b121](../experiments/20260920T013615Z-linkage-all-f5b121/manifest.json).
- `febrl4_half_no_ssn`: [20260920T013914Z-linkage-no_ssn-963e3e](../experiments/20260920T013914Z-linkage-no_ssn-963e3e/manifest.json).
- `bpid`: [20260920T014910Z-candidate-pairs-bpid-bc7216](../experiments/20260920T014910Z-candidate-pairs-bpid-bc7216/manifest.json).
- `abt_buy`: [20260920T015129Z-candidate-pairs-abt_buy-0f895a](../experiments/20260920T015129Z-candidate-pairs-abt_buy-0f895a/manifest.json).
- `amazon_google`: [20260920T015258Z-candidate-pairs-amazon_google-d98504](../experiments/20260920T015258Z-candidate-pairs-amazon_google-d98504/manifest.json).
- `walmart_amazon`: [20260920T015417Z-candidate-pairs-walmart_amazon-6f1bfa](../experiments/20260920T015417Z-candidate-pairs-walmart_amazon-6f1bfa/manifest.json).
- `dblp_acm`: [20260920T015634Z-candidate-pairs-dblp_acm-96087b](../experiments/20260920T015634Z-candidate-pairs-dblp_acm-96087b/manifest.json).
- `affiliations`: [20260920T015946Z-candidate-pairs-affiliations-1f940b](../experiments/20260920T015946Z-candidate-pairs-affiliations-1f940b/manifest.json).
