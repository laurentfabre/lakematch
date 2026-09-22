# Company comparison evidence — LM-014 foundation

Status: **local development foundation; unqualified for automatic decisions**.
LF-B remains at 8/8 experiments. No new corpus evaluation, calibration or model
training was performed for this increment. The existing Spark feature, matcher,
decision, configuration and historical model contracts are unchanged.

`mastering.match_contract.MatchRuleset` pins the legal-company domain, source
mapping versions/digests, comparison implementation, Unicode database,
normalization and rule precedence. `MatchBinding` checks the definitions and
implementation when created and again before each comparison. Definitions can
round-trip through JSON. These are worker previews, not registry approvals;
durable rule approval/promotion remains part of the later integration.

`mastering.match_evidence.compare_pair(binding, left, right,
candidate_methods=[...], pair_origin="retrieval_candidate")` accepts exactly two
mapped source snapshots. Each has
`source_id`, `source_key`, `version`, `mapping_version`, `mapping_sha256`,
`deleted` and `values`. Unknown envelope/field names, mapping drift, nonfinite
values and oversized input are rejected. When both inputs claim the same
source/key/version, differing content is rejected. The stateless comparator
cannot detect version reuse across separate calls; durable source history must
enforce that invariant before invoking it.
The service never mutates its inputs, writes records, allocates IDs or publishes.

The output contains the two detached snapshots and their hashes, a stable pair
ID, the versioned rule definition, pair origin/retrieval-method provenance, seven field
comparisons, all triggered rules and the selected rule. Reversing the pair or
candidate-method order produces the same evidence. `left` and `right` in the
result use canonical source/key/version order, not the caller's display order.
The evidence checksum covers the complete result. Candidate methods are supplied
by the trusted worker; the comparator does not prove retrieval occurred.

For two directly selected records, use `pair_origin="explicit_comparison"` and
`candidate_methods=[]`. This makes no retrieval claim. Retrieved candidates still
require one to four unique supported methods. Changing origin changes the evidence
hash; probability replay must preserve it. Origin cannot override comparison rules.

The current algorithm is `company_pair_evidence_v2`, with evidence schema 2;
the ruleset definition format remains schema 1. Earlier v1 algorithms and changed
implementation pins are rejected by the current worker, not silently reinterpreted.
Historic reports remain tied to their original source revisions. No previously
fitted or approved model depends on this development comparator.

## Field comparisons

For record kind, legal name, country, registration ID, address, city and postcode,
retain the actual mapped value and the comparison-normalized value separately.
Distinguish **missing, null, blank, invalid type, invalid format and deleted**.
Two absent/invalid values never become an agreement. Parent/family references
remain source context and are not matching features.

Comparison normalization retains non-Latin letters, removes combining accents,
case-folds names/addresses and removes an explicit small set of trailing legal
suffixes from names. Country codes require two ASCII letters; this checks syntax,
not ISO membership. Registration identifiers retain leading zeroes and allow
ASCII letters/digits plus whitespace and `.-/` separators. They are scoped to the
declared country. This does not verify identifier validity, uniqueness or legal
status. Unicode database changes alter the implementation pin.

This normalization has its own version and intentionally does not replace the
frozen retrieval normalizer or claim parity with Spark model features.

## Deterministic precedence

| Priority | Condition | Preview result |
|---|---|---|
| 1 | Deleted source | Exclude from new matching |
| 2 | Same source key, including another version | Exclude self-comparison |
| 3 | Branch/family record | Exclude at legal-company granularity |
| 4 | Missing/invalid kind, name or country | Review |
| 5 | Different countries | Suggest no match; review the source evidence |
| 6 | Different identifiers in the same country | Review; agreement cannot override the conflict |
| 7 | Distinct keys in the same source | Explicit duplicate review |
| 8 | Identifier and country agreement | Suggest match; review because uniqueness is unverified |
| 9 | Name agreement | Review; names alone do not establish identity |
| 10 | No stronger evidence | Review |

Every eligible suggestion has `route=review` and `auto_merge_eligible=false`.
`probability`, `model` and `calibration` are explicitly null. Neither a rule
agreement nor a candidate block is a calibrated score or a merge command.

Limits: one pair, ten mapping pins, 2,048 characters per input scalar, 64 KiB pair
JSON and four declared retrieval methods (zero for explicit comparisons). This
is not a batch or public HTTP API.

## Synthetic app projection

The APX **Golden records** screen now shows a comparison for each of its six
companies in each of two publications. The build tool invokes the real comparator
on the existing fixture's source snapshots, with explicit origin and no retrieval
methods. The schema-2 demo bundle carries a typed display projection: seven raw
and normalized field comparisons, source versions, triggered/selected rules,
review/exclusion reasons and original evidence/ruleset digests. The full worker
evidence is reproducible with the pinned build source; the display projection
is not itself the payload hashed by `evidence_sha256`.

The Python 3.11 app checks the package checksum, schema, source/version/value
correspondence, unique fields and selected-rule consistency. It never imports
the Python 3.12 comparator. The build's `--check` verifies exact projection parity
and runs in the local commit hook for comparator changes. This establishes the
packaged fixture's provenance, not authentication of arbitrary live input.

The screen distinguishes unchanged values, normalized agreements, differences
and unavailable comparisons. It shows identifier conflicts, deleted sources,
historical snapshots and all triggered rule reasons. Every score is explicitly
absent. Memberships are predefined; there is no merge action, candidate discovery
or model-quality claim. [Screenshots and development evidence](../../reports/lakefusion-comparison-ui-20260922/README.md)
retain the observed behavior. Live adapters, domain grants and full acceptance
remain separate gates.

## Remaining decision-band work

The separate [probability foundation](PROBABILITY.md) now pins feature order,
model, calibrator, ruleset, declared fitting/calibration/validation family sets
and evidence hashes. It applies supplied coefficients and explicit band
boundaries, preserves conflict vetoes and keeps every eligible result in review.
Analytical Brier/reliability and precision-bound helpers are implemented. These
contracts do not establish score origin, complete populations or fitted quality.

There are still no active production thresholds. Fit the calibrator without
confirmation exposure and choose thresholds from the approved error/precision
contract. Report Brier score, reliability bins, precision bounds, acceptance
coverage, rejected positives and review burden on the declared populations;
no universal 0.5 default is implied.

The [protocol](PROTOCOL.md) still requires a one-sided 95% precision lower bound
of at least 99.5% with independent family sampling. Candidate misses remain false
negatives. Model-specific explanations and their fidelity checks come after
actual value comparisons. Model/feature parity, durable rule approval, workflow
authorization, live comparison UI integration and quality acceptance remain open.

Development checks are in `tests/test_mastering_match_evidence.py`; the
[development plan](../../bench/lakefusion/MATCH_EVIDENCE_PLAN.md) and
[checkpoint](../../bench/lakefusion/PHASE_B.md) explain their limited scope.
