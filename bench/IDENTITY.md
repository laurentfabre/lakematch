# Incremental identity evidence

Fixed validation-only mutations under [IDENTITY_PLAN.md](IDENTITY_PLAN.md), using the selected verified-merge models and frozen thresholds.
Each run recomputes unchanged input, applies the mutation, and repeats changed input. The reporter independently replays every journal row and reconstructs every cluster event.

| Corpus | Records | Added / changed / deleted | Stable original IDs | Exact replay | Idempotent repeat | Wall s |
|---|---:|---|---|---|---|---:|
| febrl3 | 1,050 | 10 / 10 / 10 | pass | pass | pass | 98.45 |
| historical_50k | 10,082 | 100 / 100 / 100 | pass | pass | pass | 347.68 |

Event counts (merge/split/rekey may coexist):

- `febrl3`: `{"merge": 10, "rekey": 13, "retired": 3, "split": 8}`; [20260920T012627Z-identity-febrl3-7c613f](../experiments/20260920T012627Z-identity-febrl3-7c613f/manifest.json).
- `historical_50k`: `{"merge": 121, "rekey": 7, "retired": 4, "split": 114}`; [20260920T012807Z-identity-historical_50k-03f0a3](../experiments/20260920T012807Z-identity-historical_50k-03f0a3/manifest.json).

Canonical-key additions/deletions may legitimately rekey identities; those changes are journalled. This measures validation partitions, not the full 50,578-record historical source. Durable CLI publication/recovery and the remaining phase verifiers retain their own requirements.
