# Retrieval and scoring — ZR-3 iteration 4

After the classifier and compact-feature comparisons choose their validation
winners, compare all five candidate methods with that fixed Levenshtein scoring
pipeline on FEBRL4-half-unmatched all-fields, SSN-hidden and SSN+DOB-hidden.
Use GBT/LR/RF as selected, 20 iterations/trees, depth 3 and seed 0. Train a separate
classifier for each method on its retrieved training pairs. Fit supervised
blocking and feature IDF only on training records. Candidate IDF may use the
complete unlabelled universe, as declared in the evaluation protocol.

Budgets remain k=5, 100,000 final pairs and 50 million retained join rows.
Field blocks use the predeclared type-derived rules; union combines gram and
field blocks and re-ranks at the same k. Score complete validation candidate
sets, retaining missing true links in false negatives. Report all three supported
cardinality policies and select thresholds on the fixed 0.00–1.00 grid. Bootstrap
all 1,000 validation anchors, including unmatched anchors with no retrieved pair.
Both endpoints of every consumed training pair must belong to training.
Confirmation anchors receive retrieval scores only, never classifier predictions.

Each method logs its frozen composite, IDF and any fitted retriever state. No
accepted pointer or alias is promoted here. Compare F1, candidate recall and
resource/timing observations. The all-fields and SSN-hidden variants carry equal
weight; SSN+DOB-hidden remains a diagnostic. Paired intervals use seed 2026091902
and 2,000 anchor draws. Retain the simpler/cheaper method for an inconclusive
difference, subject to the fixed FEBRL F1 gates. The separate seven-corpus
retrieval comparison still constrains general default selection; these three
closed-world tasks do not establish full-universe F1 on sampled-pair corpora.

Three sequential runs, 900 seconds per corpus, 45-minute total allowance,
zero remote/live-label spend. This is a validation comparison. A subsequent
fresh-process run with a frozen model must measure complete input, retrieval,
scoring, output and cleanup under 60 seconds; shared-session stage timings cannot
substitute for that gate. Final confirmation waits until selection and freeze.

## Iteration 5 — truncate reused logical plans

Iteration 4 failed before its first estimator fit: run
`20260920T013426Z-linkage-all-3f9753` exhausted Java heap in
`QueryExecution.explainString` while validating the training labels. Cached
IDF-enriched inputs, retrieved pairs and feature vectors retained duplicated
logical plans. No model or validation score was accepted.

Hypothesis: owned table boundaries on those three reusable relations prevent
plan expansion. The same Materializer path already passed the clustering
comparison. Keep all data, models, seeds, pair budgets, Java memory and 900-second
run limits unchanged. Repeat the three sequential configurations; confirm table
cleanup on each terminal path. This changes execution boundaries only.
