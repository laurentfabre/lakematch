# ZR-3 method comparison plan

This plan was declared before method sweeps; confirmation remains unscored.
The seed, partitions, corpus weighting, bootstrap and simpler-choice rule remain
those in `PROTOCOL.md`. ZR-2 reports are validation evidence for feature families,
not held-out or candidate-method comparisons.

Iteration 1 will compare the five specified retrievers at the same maximum of
five candidates per left record and a 100,000-pair driver budget. Report actual
pair counts, validation candidate recall, raw join cardinality before frequency
filtering, cardinality after filtering and before top-k, and timing. A method
returning fewer pairs is not credited with having used the full budget.

The finite methods are gram top-k (q=3, cap=400), learned blocking, field blocks,
MinHash LSH (128,000 hash dimensions, four hash tables, seed 0) and the deduplicated
union of gram top-k and field blocks. Field blocks use separate exact keys for
every field, person-name soundex keys, date-year keys, and three-character
organisation/title/address prefixes. Missing values
never generate keys. Learned blocking chooses up to three rules from those same
keys by uncovered positive training-pair coverage divided by estimated join cost
after the frequency cap;
fit sees both endpoints in training only. Its selected rules are persisted.
MinHash fitting is a job action and is not offered inside a declarative flow.
All methods enforce a 50-million-row pre-top-k join ceiling after hot-key filtering.

Alternative methods rank retrieved pairs by exact unweighted gram-set cosine.
Gram top-k retains its IDF-weighted cosine. Union deduplicates the top-k output of
each child, then reranks with the unweighted score and keeps at most k pairs.
These are complete retrieval configurations; any gain includes those ranking
differences. The raw pre-cap join volume is reported; the guard applies to the
retained join volume before top-k.

Comparisons score validation anchors against the full unlabelled universe and
are explicitly transductive. Record-disjoint retrieval gets a separate report.
The same fitted retrievers also query the validation-only universe, excluding
canonical records present on either training side; report every exclusion and
mark a scope unavailable if no labelled positive remains. FEBRL blocker fitting
uses all training records, including unmatched anchors. Supplied-pair tasks use
the records occurring in training pairs. Fit once, then reuse unchanged state in
both scopes. Persist models, plans and validation candidates in a checksummed archive.
For supplied-pair corpora, candidate recall is measured on labelled positives;
unlabelled retrieved pairs are not silently treated as negatives. Classifier
comparisons retain the declared supplied-pair task as a separate evaluation.

After retrieval diagnostics, compare GBT (20 rounds, depth 3), logistic regression
(20 iterations) and random forest (20 trees, depth 3), all with seed 0. String
configurations are Levenshtein, optional Jaro-Winkler and both. Keep the ZR-2
native token features and per-type feature removals as their separately reported
ablations. Compare each supported cardinality policy only where corpus truth
permits it. Always show nearest-neighbour and a tuned scalar-threshold baseline.
Each retrieval corpus run (five methods in both scopes) has a 900-second envelope,
one active local experiment. Iteration 1 has nine runs: the seven selection
corpora, FEBRL SSN-hidden and FEBRL SSN+DOB-hidden (diagnostic); total wall ceiling
135 minutes, zero remote or live-labelling spend. Stop on the first infrastructure
failure, retain it, and diagnose before continuing the declared sequence.

Iteration 1 harness amendment after the first BPID run: gram top-k was rejected at
83,426,093 retained join rows (limit 50,000,000). This is a measured infeasible
configuration, not grounds to raise the limit. Record budget rejections and
continue other methods; paired deltas are unavailable when the reference is
rejected. Repeat the unchanged nine configurations under the corrected harness
at 480 seconds per corpus. Including the four original attempts, the maximum
declared wall allowance is 132 minutes, within the original 135-minute ceiling.
Preserve the original results and failure; no tuning factors or labels change.

Seven selection corpora have equal macro weight: FEBRL4, BPID, Abt-Buy,
Amazon-Google, Walmart-Amazon, DBLP-ACM and Leipzig Affiliations. FEBRL all-fields
and SSN-hidden split that corpus's weight equally. Original FEBRL and hidden
SSN+DOB are diagnostics. Clustering comparisons and the synthetic scale ladder
remain separate required work. No corpus is dropped after seeing its result.

Before confirmation, freeze every selected method, pipeline, feature order,
threshold, cardinality policy and label digest in MLflow. The local latency gate
uses the complete 5,000-left/2,500-right universe and includes Spark startup,
outputs and cleanup. Both all-fields and SSN-hidden must meet their existing
quality gates and finish below 60 seconds. A failure remains a failure; neither
the seed nor the timing boundary changes to obtain acceptance.
