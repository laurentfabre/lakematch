# Clusters and identity (ZR-4)

*Generated 2026-10-01T11:32:38 from `bench/results/clusters.json` by `bench/clusters.py`. Nothing below was typed by hand.*

## Contents

- [Methods](#methods)
- [Convergence](#convergence)
- [Stable ids](#stable-ids)
- [Incremental run](#incremental-run)

## Methods

Scored like the ZR-3 benchmark (default candidates, model on TRAIN pairs, threshold on VALID); the links at or above the threshold are clustered four ways. Metrics are on the clustering induced on TEST records (pairwise F1 over within-cluster pairs, and B-cubed F1); the winner is the highest mean **VALID** B-cubed F1.

| Method | FEBRL3 pairwise F1 · B-cubed F1 · largest · s | Splink historical_50k pairwise F1 · B-cubed F1 · largest · s | Mean VALID B-cubed F1 |
|---|---|---|---|
| **verified_merge** (winner, default) | 0.9982 · 0.9995 · 5 · 2.1 | 0.9111 · 0.9541 · 22 · 11.0 | 0.9761 |
| connected_components | 0.9927 · 0.9988 · 5 · 0.0 | 0.0076 · 0.7637 · 2458 · 1.3 | 0.8842 |
| center | 0.9680 · 0.9923 · 5 · 0.0 | 0.6071 · 0.8140 · 8 · 0.4 | 0.9078 |
| star | 0.9982 · 0.9995 · 5 · 0.0 | 0.8794 · 0.9391 · 26 · 0.5 | 0.9691 |

FEBRL3: 5,000 records, 2,000 gold clusters (largest 6), 6,553 links at p >= 0.14 · Splink historical_50k: 50,578 records, 5,156 gold clusters (largest 21), 227,551 links at p >= 0.58

## Convergence

Rule: verified_merge reaches a round with nothing left to propose before cluster.max_rounds. Passed: **True**.

- FEBRL3: 3 rounds, 3,000 merges, 8 vetoes, 28 representative pairs scored, converged True
- Splink historical_50k: 5 rounds, 42,962 merges, 4,114 vetoes, 28,234 representative pairs scored, converged True

## Stable ids

Two independent passes per corpus with `verified_merge`; the second pass's ids are carried from the first pass's crosswalk. Records whose `mdm_id` changed: **0**.

- FEBRL3: 2,000 entities, 0 changed, 0 log events, ids equal without history: True
- Splink historical_50k: 7,616 entities, 0 changed, 0 log events, ids equal without history: True

## Incremental run

1 % of the records held out of a base pass; the next pass adds them, deletes another 1 % and changes another 1 % (surname: two adjacent characters swapped). Identity is assigned from the base crosswalk and the log is reconciled (`identity.reconcile`). Reconciles: **True**.

- FEBRL3: +48 / −51 / ~67 records; events {'split': 2, 'create': 6, 'merge': 1, 'move': 1, 'retire': 4}; 6 surviving records changed id, every one explained: True
- Splink historical_50k: +519 / −509 / ~534 records; events {'merge': 352, 'split': 286, 'move': 147, 'create': 22, 'retire': 25}; 1520 surviving records changed id, every one explained: True
