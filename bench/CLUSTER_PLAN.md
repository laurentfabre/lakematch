# Clustering preparation and acceptance plan

Predeclared protocol; measured results are recorded separately from this plan.
The public corpus manifests are frozen under `data/bench/febrl3` and
`data/bench/historical_50k`. Whole truth entities are partitioned 60/20/20 by
namespaced SHA-256 ranking with seed 2026091901. Confirmation remains unscored.

FEBRL3 contains 5,000 records and 2,000 truth entities. The pinned Splink
`historical_50k` file actually contains **50,578 records and 5,156 entities**;
the corpus name is not an assertion that its row count is exactly 50,000.
Its source revision is `75876d806d9eff72072d21878150ee50a96d5f41`, with raw
checksums and licensing retained in `data/sources/clustering/manifest.json`.
No personal lake data is involved.

The comparison must implement and measure connected components, center, star and
verified merge on validation records, with deterministic ties and an explicit
convergence bound. Verified merge must re-score representatives and reject a
proposed merge on any representative-pair veto. Declare the precise center/star
and representative-selection rules before method execution. This preparation
does not choose or claim a clustering default.

The initial implementation uses undirected accepted edges and these fixed rules:

- Components propagate the minimum record ID until labels stop changing.
- Center ranks remaining vertices by mean incident probability; star ranks them
  by incident edge count. Both select local maxima, breaking ties by lower record
  ID, assign adjacent records to the highest-priority selected center, then remove
  assigned records and repeat. These are disjoint partitions.
- Verified merge proposes pairs of current clusters connected by an accepted
  edge. Re-score every cross-product of their minimum/maximum-ID representatives
  (up to four pairs). Missing, invalid or below-threshold scores veto the proposal.
  From approved proposals, merge mutually best partners by highest edge score,
  breaking ties by lower cluster ID. Repeat until no approved merge remains.

All rounds use owned tables through the runtime materializer to truncate logical
plans; cache alone caused a measured JVM heap failure on repeated self-joins.
No driver graph collection is required. Tables are dropped by the owning task.
The existing max-pairs budget bounds vertices, graph edges and verification pairs
separately. The max-rounds limit produces an explicit failure on nonconvergence.
Synthetic graph tests precede corpus measurements. The implementations and
identity journal are not yet wired into the normal end-to-end CLI.

Report pairwise precision/recall/F1 and B-cubed precision/recall/F1. Cluster metric
computation uses contingency counts, avoiding quadratic truth-pair enumeration.
Paired bootstrap resamples true-entity contributions with seed 2026091902 and
2,000 resamples. Cross-entity false positives contribute half to each endpoint's
truth entity. This quantifies uncertainty in fixed measured partitions; it does
not refit or recluster bootstrap datasets. Singletons remain in B-cubed metrics.

Splink is isolated from the engine in `.tools/splink-env`, pinned by
`bench/requirements-splink.lock`. Fit and tune only on the corresponding training
and validation partitions, record its blocking/comparison settings, and retain
model parameters and predictions. The historical blog figure is not a measured
result for this implementation or split.

The first Splink baseline is fixed before execution: DuckDB with two threads and
a 2 GB memory limit; exact comparisons for code fields, Levenshtein distances 1/2
for other fields; blocking on last-name-token prefix (four characters), birth year
or postcode. Missing keys produce no candidates. Fit the match prior and m-values
from training truth entities and u-values from at most one million sampled
training pairs, seed 0. A fresh Linker in a separate DuckDB connection/API scores
validation with frozen parameters. Verify every returned endpoint belongs to
validation before computing any metric. Sharing the API's SQL cache across
Linkers is forbidden: a retained failed baseline exposed training rows that way.
Reject before scoring if the summed blocking-join upper bound exceeds five
million; final predictions are capped at one million pairs. Select a connected-
components threshold on the 0.00–1.00 grid by validation pairwise F1, with ties
favoring the higher threshold. One run per corpus, 600 seconds each, 20-minute
total allowance, zero remote/live-label spend. This baseline has its own declared
blocking budget and is not an equal-budget retrieval comparison with k=5.

Identity canonical keys use the smallest stable member record ID within an
explicit entity namespace. An unchanged partition must reproduce every mdm_id.
Deleting that canonical member or adding a smaller key may rekey the identity;
record it. A full record-change journal must replay exactly to the current
crosswalk. Merge, split, rekey, created and retired cluster events are distinct,
and simultaneous merge/split events may coexist. Benchmark 1% additions, 1%
changes and 1% deletions, then repeat to prove idempotence; no successful identity
gate is claimed until that experiment runs.

ZR-4 iteration 1 compares the four Spark clustering methods on both validation
partitions. Use Levenshtein, all three native token families, embeddings off,
and the native estimator selected by the ZR-3 cross-corpus classifier comparison
(20 iterations/trees, depth 3, seed 0). This comparison isolates clustering and
does not retune the feature library. Field blocks use every configured field's
exact key plus the type-specific rules from `blocking.proposed_rules`. Each
partition is retrieved separately at k=6 including self; remove self and union
opposite orientations to obtain at most five outgoing nonself neighbours per
record. Bound each split at 500,000 directed final pairs and 50 million retained
pre-top-k join rows. Report coverage of all within-entity pairs; connectivity
can recover clusters even when direct pair recall is below one.

Feature IDF and the classifier fit training records/pairs only. For this dedupe
task, pair-level candidate metadata is unweighted gram cosine, rank=1 and gap=0
for every training, validation and representative pair. Re-scoring a requested
representative is independent of the other requested pairs. This contract is
explicitly different from directional two-source retrieval ranks.

Select one common classifier threshold on validation pairwise F1 using the fixed
0.00–1.00 grid, breaking ties toward the higher threshold; include every missing
truth pair in the false-negative count. All four clusterers receive exactly the
same scored graph and threshold. Compare validation cluster pairwise F1 with
equal corpus weights; B-cubed is a reported secondary metric. Connected components
is the paired reference and the simpler choice when the difference interval
includes zero. Baselines are connected components of the nearest-neighbour graph
and of a validation-tuned cosine-threshold graph. They share the candidate set.

Two sequential Spark corpus runs, 900 seconds each, 30-minute total ceiling,
zero remote/live-label spend. At most 30 rounds; each nonconverged method fails
explicitly. Splink's two independently bounded baselines use the earlier plan.
No confirmation scoring, identity acceptance or default promotion is implied by
finishing the comparison. The incremental identity experiment follows selection.
