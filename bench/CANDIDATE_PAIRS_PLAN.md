# ZR-3 iteration 6 — candidate effects on the six supplied-pair corpora

The FEBRL comparison measures closed-world linkage. It cannot determine a
seven-corpus candidate default by itself. Hypothesis: fitting the selected
Levenshtein/IDF-only/GBT classifier on each retriever's labelled training pairs
will reveal which feasible retriever preserves the highest macro validation F1.

Run BPID, Abt-Buy, Amazon-Google, Walmart-Amazon, DBLP-ACM and Affiliations, each
with gram top-k, learned blocker, MinHash, field blocks and gram/field union.
Keep k=5, 100,000 candidate pairs, 50-million retained join rows, 20 GBT iterations,
depth 3, seed 0, corpus seed 2026091901 and bootstrap seed 2026091902. No budget
increase or extra rule search. Fit learned state and IDF from labelled training
records only. Use the previously declared type-derived field-block rules.

Only supplied training labels enter classifier fitting. Only supplied validation
pairs receive classifier scores. Unlabelled pairs remain unknown; exact held-out
test/confirmation pairs never receive scores. Missing retrieved validation
positives are false negatives. This is retrieval-filtered **supplied-pair F1**,
not full-universe precision. Preserve official-split shared-record caveats and
entity-disjoint partitions as frozen; no resplitting. Compare every compatible
cardinality policy on the same fixed threshold grid, with 2,000 paired group
bootstrap draws. Include nearest-neighbour and cosine-threshold diagnostics.

Retain budget rejection or single-class-training outcomes as unavailable, not
zero F1. A method unavailable on a corpus is ineligible as a universal default;
never silently omit that corpus from its macro. Combine these six corpus votes
with half-votes for the all-field and SSN-hidden FEBRL linkage results. The
SSN+DOB-hidden configuration is diagnostic. Pick the simpler/lower-cost feasible
method if its paired F1 interval against the best includes zero and it satisfies
the FEBRL validation gates. Record per-corpus exceptions separately.

Six sequential local runs, 900 seconds each, at most 90 minutes total. One Spark
experiment at a time, offline after preparation, zero remote/live-label spend.
All reusable weighted records, candidates and feature vectors use owned table
boundaries, following the measured lineage fix. Do not score final confirmation
until the candidate, classifier, features and policies are frozen.
