# Compact native feature selection — ZR-3 iteration 3

Declared before these experiments. The ZR-2 removal ablations suggest that some
token features add cost without a clear paired improvement. Separate removals
do not establish that a combined removal preserves quality, so measure it.

Compare exactly three configurations: all native token features
(`idf_token_cosine`, `gram_overlap`, `monge_elkan_token`); `idf_token_cosine` alone;
and no multi-token features. Keep typed field families, Levenshtein, embeddings
off, the estimator chosen from the completed ZR-3 classifier factorial, 20
iterations/trees, depth 3 and seed 0. No candidate, field-type or threshold-grid
search is added. Repeat the all-feature reference in the same run.

Use the nine corpus configurations, splits, training endpoint restrictions,
evaluation scopes, eligible cardinalities and fixed threshold grid from
[CLASSIFIER_PLAN.md](CLASSIFIER_PLAN.md). Full-universe FEBRL retrieval remains
gram-top-k at k=5, with 100,000 final pairs and 50 million retained join rows.
Supplied-pair tasks stay supplied-pair tasks. Confirmation remains unscored.

Choose by seven-corpus macro validation F1 under [PROTOCOL.md](PROTOCOL.md),
with FEBRL all/SSN-hidden sharing one vote and the diagnostic excluded. Use
2,000 paired entity/group resamples and shared FEBRL draws. Retain the cheaper
feature set when its paired difference from the best point estimate includes
zero, subject to the fixed FEBRL gates. Check the direct candidate-to-best
interval, not only each candidate's interval against the reference.

Report feature/fit/score cost, logged composite model size, complete run time,
native explain plans and whole-application Spark event metrics. IDF preparation
is shared in this controlled comparison; an IDF-free winner would omit that
stage in a subsequent full latency measurement. These costs do not establish
the startup-inclusive 60-second acceptance gate.

Nine sequential runs, 600 seconds per corpus, 90-minute total ceiling, zero
remote/live-label spend. Each run trains and logs three models. Stop the sweep
on a failure, preserve it, and diagnose before any changed experiment.
