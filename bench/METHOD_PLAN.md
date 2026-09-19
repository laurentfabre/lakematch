# ZR-3 method comparison plan

This is a predeclared plan; no method sweep or confirmation scoring has run.
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
union of gram top-k and field blocks. Field blocks use separate available exact
code keys, name soundex keys and three-character text prefixes. Missing values
never generate keys. Learned blocking chooses up to three rules from those same
keys by uncovered positive training-pair coverage divided by estimated join cost;
fit sees both endpoints in training only. Its selected rules are persisted.
MinHash fitting is a job action and is not offered inside a declarative flow.
All methods enforce a 50-million-row pre-top-k join ceiling, including hot keys.

Comparisons score validation anchors against the full unlabelled universe and
are explicitly transductive. Record-disjoint retrieval gets a separate report.
For supplied-pair corpora, candidate recall is measured on labelled positives;
unlabelled retrieved pairs are not silently treated as negatives. Classifier
comparisons retain the declared supplied-pair task as a separate evaluation.

After retrieval diagnostics, compare GBT (20 rounds, depth 3), logistic regression
(20 iterations) and random forest (20 trees, depth 3), all with seed 0. String
configurations are Levenshtein, optional Jaro-Winkler and both. Keep the ZR-2
native token features and per-type feature removals as their separately reported
ablations. Compare each supported cardinality policy only where corpus truth
permits it. Always show nearest-neighbour and a tuned scalar-threshold baseline.
Each corpus/method run has a 900-second envelope, one active local experiment.

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
