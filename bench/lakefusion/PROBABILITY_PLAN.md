# LM-014 probability and band contracts — development plan

Date: 2026-09-22. LF-B is **8/8**; the proposed extension is still pending.

Hypothesis: the comparator can accept a precisely identified model score, apply
a versioned probability transform and describe explicit reject/review/accept
bands without treating a numerical result as approved merge authority.

Implement separate immutable model/feature, calibration and band definitions.
Pin declared fitting/calibration/validation family sets and reject overlaps.
Require explicit coefficients, clipping and thresholds; do not introduce a
default production threshold. Retain deterministic exclusions and conflict
vetoes. Score results must reference the exact pair evidence and contracts.

Provide diagnostic Brier/reliability metrics and the one-sided exact binomial
lower-bound calculation for later evaluation. They are numerical helpers, not
the campaign evaluator, a sampling implementation or a release gate.

Bounds: one comparison at a time, 256 KiB comparison evidence, at most 256
feature names, 10,000 families per declared partition, 100,000 diagnostic rows
within 16 MiB, 20 reliability bins and 10,000 independent observations for the
binomial helper. Validate finite values and integer counts; refuse unsupported
schemas or changed implementation pins. Keep the original Spark engine intact.

Verification: analytical unit cases (identity transform, clipping, boundaries,
conflicting identifiers, stale evidence, disjoint family sets, hand-computed
Brier/reliability values and exact small-n binomial cases), then required
portable commit checks. Each test process has the existing 120-second limit.
No fitting, threshold search, corpus read, confirmation generation, database,
Spark session, remote call or campaign experiment is authorized by this plan.
No fitted artifact or achieved quality claim is produced.

Update the goal and Phase B evidence honestly; leave calibration/promotion and
acceptance gates open. The four user-refreshed scan reports remain untouched.
