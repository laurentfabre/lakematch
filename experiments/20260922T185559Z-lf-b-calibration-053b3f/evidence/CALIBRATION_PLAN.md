# LF-B slot 11 — one fixed company model and calibration

Declared before reading fitting or calibration results. LF-B uses 10/12 slots;
this run occupies slot 11. The single diagnosed follow-up has already been used.
No alternative fit, retry, hyperparameter search or confirmation release is
included. Slot 12 is a fitting-free replay, conditional on a selected passing
validation policy and successful finite-resource execution.

## Hypothesis and partitions

One regularized logistic model over actual field comparisons, calibrated against
the complete candidate population, can produce useful proposed bands while the
existing deterministic conflict rules retain review authority. Keep the selected
`identifier_name` retrieval with its current normalization/ranking and limits.
The model never consumes retrieval ranks, routing keys, source identity, family,
truth, partition, parent references or corruption stratum as features.

The original 10,000-family 60/20/20 assignment is unchanged. Rank the 6,000
development families by `rank(20260927, "lf-b-fit-calibration", family)`:

| Role | Families | Source rows | Population |
|---|---:|---:|---|
| Fit | First 4,000 development families | 16,000 | 48,000 sampled pairs |
| Calibration | Remaining 2,000 development families | 8,000 | All retained ERP→CRM candidates within these families |
| Validation / threshold selection | Original 2,000 validation families | 8,000 | All retained ERP→CRM candidates and every known positive, including retrieval misses |
| Confirmation | Original 2,000 confirmation families | Not materialized | No access or release |

Both endpoints of every fitting pair must belong to the fitting subset. Run the
frozen generator's `training_pairs` function on fitting truth only, keeping its
20260926 negative stream: all 8,000 positives, one sibling negative and four
distinct other-family negatives per ERP anchor. This is a new, declared subset
of development; the original 72,000-pair artifact stays untouched. The committed
`calibration-inputs-v1.json` contains all three explicit family lists, dependency
and source hashes, fixed parameters and independent analysis seeds. Preparation
uses family-assignment metadata only, not source rows or fit outcomes.

## Fixed model and calibration

Use the existing actual-value comparison normalizer. The ordered 11 features are
six nonmissing normalized agreements (name, country, identifier, street, city,
postcode), name-token Jaccard, name-trigram Jaccard, street-trigram Jaccard,
identifier unavailable and identifier disagreement. Empty comparisons score zero;
identifier leading zeros are retained. Model inputs are six allowlisted strings
or null; extra metadata keys fail. No customer-data feature claim is implied.

Fit one logistic regression: mean binary log loss plus `0.001 * sum(w²)/2`, no
class weights, unpenalized intercept, no feature scaling. Initial parameters are
zero. SciPy L-BFGS-B has coefficient/intercept bounds [-1000,1000], `maxiter=300`,
`maxfun=1000`, `maxls=30`, `ftol=1e-12`, `gtol=1e-8`. Nonconvergence fails; it does
not trigger another model. NumPy 2.5.3 and SciPy 1.18.1 are pinned in the existing
environment lock and the optional `calibration` extra.

Fit one Platt transform on complete calibration candidates, retaining all their
labels and natural candidate prevalence. Input is the logit of model probability
clipped to [1e-6,1-1e-6]. The same optimizer minimizes mean binary log loss plus
`0.0001 * slope²/2`; slope is bounded [0,1000] and intercept [-1000,1000]. This
nondecreasing transform cannot invert the classifier. Training-pair precision
does not qualify any gate. There is no calibration selection using validation.

Persist coefficients as inspectable JSON, bound through the existing
`ScoreContext`, `PlattCalibration` and `DecisionBands` contracts to actual source
snapshots, family lists, retrieval, rules and features. Compare NumPy fitted
probabilities against portable scalar inference for every fitting pair, at
absolute tolerance 1e-12. All actual worker routes remain review; registry
promotion, automatic merge execution and deployed APIs are outside this run.

## Finite threshold selection and uncertainty

Evaluate accept thresholds **[0.9, 0.95, 0.975, 0.99, 0.995, 0.999, 1.0]** only.
Conflict/incomplete-identity vetoes always propose review. If provisional accepts
share either ERP or CRM key, all those ambiguous candidates propose review.
No truth or family metadata participates in that scoring/cardinality policy.

For each threshold, sort accepted pair IDs by `digest([20260928, pair_id])` and
greedily audit edges whose endpoint families have not appeared in the audit.
This is label-blind, with at most one decision touching each family; cross-family
false matches cannot reuse a family through their CRM endpoint. Report sample
size, errors and one-sided Clopper–Pearson bounds. Select the lowest threshold
whose lower bound reaches 99.5% at confidence `1 - 0.05/7`. This Bonferroni
adjustment covers selection across all seven predeclared thresholds. Also report
the nominal 95% bound for comparison. If none passes, select **no acceptance**;
never substitute a convenient threshold or claim zero accepted pairs prove
precision. The audit estimates the declared family-disjoint sampling population,
not pair-weighted whole-workload precision or arbitrary customer accuracy.

From reject thresholds **[0, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1]**, select the
highest boundary rejecting zero retrieved validation positives after conflict
vetoes. Reject is strict; accept is inclusive. This is an observed selection
condition, not a general false-rejection guarantee. Missing candidates remain
false negatives and unresolved anchors regardless of threshold.

Report raw/calibrated Brier score and ten-bin reliability/ECE on the complete
candidate population, candidate recall, cap losses, accepted errors/precision,
acceptance coverage, accepted recall, rejected positives, proposed review pairs,
and unresolved ERP anchors. Break retrieval and decision outcomes out by each
frozen corruption stratum. Produce 200 ERP-family bootstrap replicates using
NumPy seed 20260929 and percentile 95% intervals for whole-workload ratios.
Those intervals are descriptive: candidates may connect different families.
Actual automatic execution stays disabled even if the selection bound passes.

Validation was previously used to select retrieval. Neither this evaluation nor
slot 12's replay is an independent confirmation. Final quality qualification,
customer representativeness, production policy approval and optional AI benefit
remain open. The synthetic integration fixture is not quality evidence.

## Bounds, verification and evidence

Use `tools/experiment.py`, phase LF-B, kind `lf-b-calibration`, outer timeout
**900 seconds**. Each retrieval is bounded at 120 seconds, 50 candidates/ERP
record, 2 million retained pairs and 20 million posting visits. Fit/evaluation
diagnostic arrays are capped at 100,000 rows; measured process peak RSS must be
at most **4 GiB**. This is a measured memory gate, not an OS reservation. No
Spark, database, service, cloud resource or AI call starts. Single-thread BLAS
environment variables are set before launching the Python process.

Before execution, commit implementation, this plan, input manifest and analytical
tests. Unit fixtures use unrelated seeds and test contracts and arithmetic;
they do not open campaign sources. Verify the 15 frozen Phase A files and every
declared input before/after evaluation. Refuse uncommitted bound files, a wrong
ledger count, changed dependencies or an already-materialized confirmation file.
No result file is overwritten. The runner retains terminal failure and owned
process cleanup; any failed run consumes its slot.

Store the model and compact report in `bench/lakefusion/`; bulk scored pairs go
to ignored `data/lakefusion/calibration-v1/` with hashes. The report separately
records execution completion, validation selection and unachieved confirmation.
Exit zero means the declared calculation completed, not production acceptance.
If a policy passes, commit model/report hashes in a replay freeze before slot 12.
Replay must reload the JSON model, recompute every validation candidate/score,
diagnostic and band with unchanged source hashes, and match the original digest
exactly. It performs no fitting, calibration fitting or threshold search.
