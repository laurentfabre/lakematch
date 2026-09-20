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

Missing compatible completed comparisons: bpid, abt_buy, amazon_google, walmart_amazon, dblp_acm, affiliations.

Macro gives each corpus one vote; FEBRL all/SSN-hidden split its vote. Paired intervals use 2,000 namespaced PCG64 group draws, seed derived from 2026091902/candidate_macro/corpus. Infeasible methods are not assigned zero and no corpus is omitted to make their macro complete.

No confirmation scores or model promotion. Shared-session stage costs do not establish the local 60-second gate.

- `febrl4_half_all`: [20260920T013615Z-linkage-all-f5b121](../experiments/20260920T013615Z-linkage-all-f5b121/manifest.json).
- `febrl4_half_no_ssn`: [20260920T013914Z-linkage-no_ssn-963e3e](../experiments/20260920T013914Z-linkage-no_ssn-963e3e/manifest.json).
