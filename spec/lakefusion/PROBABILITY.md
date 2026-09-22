# Probability and decision-band previews — LM-014

Status: **local development foundation; unqualified for automatic decisions**.
The worker can apply an explicitly supplied probability transform and describe
reject/review/accept bands for one scored comparison. Every eligible result still
routes to review. No pilot model or calibrator was fitted, no production threshold
was selected, and no matching-quality gate passed in this increment.

This extends the [actual-value comparison contract](MATCH_EVIDENCE.md) without
changing the existing Spark engine, historical models or v1 configuration.
LF-B remains **8/8 experiments**. The [development plan](../../bench/lakefusion/PROBABILITY_PLAN.md)
and [check evidence](../../bench/lakefusion/PHASE_B.md) describe the permitted scope.

## Contracts and binding

The immutable definitions live in `lakematch.mastering.score_contract`.
`ScoreContext`, `PlattCalibration` and `DecisionBands` carry an explicit schema
version, definition ID/version and a content digest. Their `from_dict` methods
require schema version 1; `definition()` returns a detached JSON-shaped value.
Changing a model, feature order, partition, coefficient, threshold or dependency
changes the relevant digest and invalidates dependent bindings.

| Contract | Required information |
|---|---|
| `ArtifactRef` | Artifact ID, version and SHA-256 digest |
| `DataPartition` | Role, snapshot digest, sorted unique family IDs and declared pair population |
| `ScoreContext` | Model reference/URI, feature reference/order, ruleset and retrieval-execution digests, fitting partition, positive-label-1 probability scale |
| `PlattCalibration` | Score-context digest, calibration partition, algorithm, explicit coefficients and clipping epsilon, implementation digest |
| `DecisionBands` | Calibration digest, validation partition, explicit reject and accept boundaries |
| `ProbabilityBinding` | Comparison binding plus the linked score, calibration and band definitions |
| `PairScore` | Exact score-context and comparison-evidence digests, raw probability or explicit `None` |

Partition roles are `fit`, `calibration` and `validation`; confirmation is not
supported here. Fitting may declare sampled training pairs or complete candidate
pairs. Calibration and validation must declare complete candidate populations.
Binding rejects overlapping family lists and reused snapshot digests across the
three partitions. A retrieval rank is not accepted as a probability scale.

These declarations are **trusted worker metadata**. The helper does not load the
model, verify artifact bytes at a URI, recompute features, execute retrieval,
inspect partition contents or establish that a population is complete. It cannot
prove the origin or truth of a supplied score. A later evaluator must validate
these claims against immutable source/artifact manifests. Family disjointness
also does not establish statistical independence among pairs within a family.

The probability implementation pin covers `probability.py`, `score_contract.py`,
`contracts.py` and `identity_contract.py`. The separate comparison binding checks
its own implementation, normalization and domain/mapping dependencies. Changed
implementation pins require new bound definitions before execution.

## Transform and exact boundaries

`probability.apply_calibration(calibration, p)` implements `platt_logit_v1`:

```text
p_clipped = min(1 - epsilon, max(epsilon, p))
q = sigmoid(coefficient * logit(p_clipped) + intercept)
```

All parameters must be supplied. The coefficient is in [0, 1000], the intercept
in [-1000, 1000], and epsilon in [1e-12, 1e-3]. The nonnegative coefficient makes
the transform nondecreasing. The implementation avoids exponential overflow and
returns the original, clipped and transformed probabilities, plus whether input
clipping occurred. Finite probabilities in [0, 1] are required; booleans, numeric
strings, NaN and infinities are rejected. Numerical saturation can produce 0 or 1.
The class name describes the transform, not evidence of a fitted calibration.

`score_band(bands, q)` uses these boundaries, with `reject_below < accept_at_least`:

| Condition | Numerical band |
|---|---|
| `q < reject_below` | `reject` |
| `reject_below <= q < accept_at_least` | `review` |
| `q >= accept_at_least` | `accept` |

The test thresholds 0.2 and 0.8 are analytical examples only. There are no default
production thresholds or threshold-search routines.

## Preview routing and evidence

`preview_decision(binding, comparison, score)` replays the comparison from its
pinned source snapshots and declared candidate methods. Canonical content hashes
must match, including the original comparison digest; changing a field, decision,
source version or score context invalidates the input. This detects stale or
altered evidence, but does not authenticate its producer.
Replay also preserves the schema-2 comparison's explicit pair origin; a directly
selected pair cannot be relabelled as retrieved without consistent provenance.

The result separates three values:

- `numerical_band`: the transformed probability's band, or null for a missing score.
- `proposed_band`: the band after deterministic exclusions and conflict vetoes.
- `route`: the actual preview destination, always `review` for eligible pairs.

Deleted sources, comparisons of the same source key and branch/family records
retain the comparator's `exclude` route. Missing or invalid identity fields,
different jurisdictions, conflicting registration identifiers and distinct
keys within one source veto a numerical acceptance and propose review. A missing
probability also proposes review. Eligible numerical rejects remain review
previews until an approved decision policy exists.

Every result has `auto_merge_eligible=false` and
`qualification=development_preview_only`. It retains the complete comparison,
supplied score, contract references, transform, vetoes/reason and result digest.
Store the detached binding manifest with its referenced artifacts if replay is
needed; the preview does not persist them or resolve them from a registry.

## Diagnostic helpers

`calibration_metrics(rows, bins=10)` accepts unique `DiagnosticPair` rows, each
with a SHA-256 pair ID, integer 0/1 label and raw/transformed probabilities. It
reports Brier score (mean squared probability error), equal-width reliability
bins and expected calibration error (ECE), separately before and after transform.
ECE is the count-weighted absolute difference between each bin's mean probability
and observed positive rate. Empty bins have null means/rates; all bins are lower
inclusive and upper exclusive except the final bin, which includes 1. Rows are
sorted by pair ID and summed with `math.fsum` for order-independent diagnostics.

The output explicitly says `scope=supplied_scored_pairs_only` and
`quality_qualified=false`. The function trusts supplied transformed probabilities;
it does not link them to a calibration definition or independently transform them.
It cannot establish retrieval recall, representative sampling, population
completeness, acceptance coverage, review burden or rejected positives. Those
require a later evaluator that includes missing candidates and fixed truth.

`precision_lower_bound(successes, trials, confidence=0.95)` computes the one-sided
Clopper–Pearson lower bound for independent Bernoulli observations. Zero trials
return null; zero successes return 0. For all-success counts the result is
`(1 - confidence) ** (1 / trials)`; other counts use bounded binomial-tail inversion.
Confidence must be strictly between 0.5 and 1.

As a mathematical illustration, 598 error-free independent observations produce
a 95% lower bound at least 99.5%; 597 do not. This is **not 598 observed pilot
decisions**. Counts alone cannot satisfy the [protocol](PROTOCOL.md)'s sampling
and family-dependence requirements. The helper has no promotion authority.

## Bounds and remaining work

| Input or operation | Limit |
|---|---|
| Comparison evidence | One pair, 256 KiB serialized JSON; underlying source-pair limit remains 64 KiB |
| Feature order | 1–256 unique names |
| Declared families | 1–10,000 per partition |
| Diagnostic input | 1–100,000 unique pairs, at most 16 MiB serialized JSON |
| Reliability bins | 2–20 equal-width bins |
| Precision observations | 0–10,000 integer trials; at most 64 inversion steps |

All operations are in-process and have no database, model-loader or service
dependency. The definitions have no registry approval, authenticated API,
calibration fitter, threshold selector, campaign evaluator or promotion path.
Automatic merge execution is absent. Model/feature parity, calibration on declared
splits, matching-quality acceptance, live comparison UI, model-specific explanation
fidelity and workflow authorization remain open LM-014/integration work.
The synthetic APX comparison display is documented in [MATCH_EVIDENCE.md](MATCH_EVIDENCE.md);
it carries no model score or probability-band output.
The pending [experiment extension](../../bench/lakefusion/NEXT_EXPERIMENTS.md)
must be resolved before calibration or acceptance experiments.
