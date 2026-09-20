# Native convergence correction — ZR-4 iteration 4

Iteration 3 completed FEBRL3 but failed on historical_50k: minimum-label propagation
had not reached a fixed point after the declared 30 rounds. Retain run
`20260920T010851Z-cluster-historical_50k-e76bf6`. Its classifier threshold was 0.20,
with validation pair precision 0.9761 and recall 0.5121; this does not establish
clustering quality. No clustering default is selected from a partial comparison.

Hypothesis: following each vertex's updated parent label once per round reduces
long-path convergence time while preserving connected components and their
minimum-ID labels. Each parent is a vertex from the same component and labels
decrease monotonically. Require an observed unchanged round before success.
Continue to use owned tables at round boundaries and the existing 30-round cap.
Preserve the round trace in every nonconvergence exception and save scored edges
before starting any clusterer, including when a later method fails.

Verify two disconnected 32-vertex paths plus an isolated vertex within eight
rounds, with exact expected minimum IDs and table cleanup. Then repeat both
native corpus comparisons with unchanged scientific parameters and budgets from
CLUSTER_PLAN.md: two sequential runs, 900 seconds each / 30 minutes total.
Splink is unaffected and retains its existing successful evidence.
The incremental identity experiment follows native selection.

Iteration 4's eight regression tests passed, but the full FEBRL3 run then failed
while center clustering built a broadcast table: the 1 GB JVM heap was exhausted.
The round outputs were truncated, but the initial remaining-vertex relation still
carried the complete cached feature/IDF preparation lineage into repeated joins.
Run `20260920T011350Z-cluster-febrl3-40aea9` retains that failure; all owned tables
were removed and the process group terminated.

Iteration 5 additionally materializes the validated ID-only vertex relation into
an owned table before graph processing. Repeat the same bounded corpus comparison
and scientific settings, without increasing memory, candidate or round limits.
The incremental experiment is now iteration 6. Stop further clustering sweeps at
the campaign's eight-iteration cap if acceptance remains unresolved.
