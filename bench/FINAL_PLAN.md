# ZR-3 iteration 7 — frozen confirmation and bounded scale

Declared before confirmation scoring. Iterations 1–6 are complete, including the
retained iteration-4 heap failure. One final iteration remains after this one.

Hypothesis: the only complete feasible validation choice, MinHash with native
Levenshtein, IDF token cosine and GBT, meets both frozen FEBRL quality gates and
the 60-second fresh-process limit. Validation F1 is 0.9889 all-field and 0.9869
without SSN. MinHash's seven-corpus macro F1 is 0.6942. This is not evidence that
it statistically beats the infeasible alternatives. Affiliations provides only
one class after field/learned retrieval; gram/union exceed BPID's join budget.

Freeze all eight immutable MLflow model URIs, complete configs, corpus manifests,
selection-report hashes and execution-source hashes in `bench/freeze.json` before
any held-out labels are scored. No retraining, threshold search, new seed or
model/alias promotion. Retain every failed acceptance gate. Table materialization
is the sole execution setting change; it does not alter matching semantics.

Run all-field and SSN-hidden FEBRL through the normal `run --save-scores` CLI in
fresh processes, on the complete 5,000-left/2,500-right record universe. Time from
before process launch through Spark stop, output and cleanup. Score the existing
validation and reserved confirmation anchors separately, after global cardinality.
Targets: confirmation F1 >= 0.97 / 0.96 and process wall time < 60 seconds each.
Report candidate loss, classifier/decision loss, baseline F1 and paired intervals,
and positive-link missingness, differing-name, Unicode and multi-value slices.

Then score BPID, Abt-Buy, Amazon-Google, Walmart-Amazon, DBLP-ACM and Affiliations
on their existing `test` or `confirmation` partition. Preserve supplied-pair
evaluation and shared-record caveats; never infer negatives from unknown pairs.
Nearest-neighbour and cosine baselines use the previously selected thresholds.
Use 2,000 group bootstrap draws, seed 2026091902, as in the frozen protocol.

Run 1,000 -> 10,000 -> 100,000 -> 1,000,000 total synthetic records, with equal
sides, seeded SHA-256 exact duplicates and a separate 400-record training namespace.
This ladder measures bounded work and cap-induced candidate loss, not realistic
corruption accuracy. Use four hash tables, cap 400, k=5, final pair budget N/2*5,
50 million retained pre-top-k rows, unchanged local[2] and default JVM memory.
The smallest tier also runs 2,000 indistinguishable hot-key records. Collect actual
join cardinalities before/after caps, recall, shuffle, skew, throughput, elapsed
time and owned-resource cleanup. Stop higher tiers on a resource/timeout/budget
failure, retaining the measured limit; do not raise memory or pair budgets.

One Spark process group at a time. Finite maximum: two linkage runs at 300s,
six supplied-pair runs at 420s, and four scale tiers at 600/600/900/1800s: 7,020s
total timeout envelope plus runner cleanup. External network denied by the OS;
zero remote/live-labelling spend. Baseline original-FEBRL and prior clustering
results remain explicitly historical/development measurements until refreshed.
The runner seals outputs, verifies process-group termination and appends the
ledger. No default changes while measured processes are running.
