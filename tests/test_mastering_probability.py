from copy import deepcopy
from dataclasses import asdict, replace
import json
import math
from pathlib import Path

import pytest

from lakematch.mastering.contracts import ContractError, DomainContract, SourceMapping, digest
from lakematch.mastering.match_contract import MatchBinding, MatchRuleset
from lakematch.mastering.match_evidence import compare_pair, implementation_digest as comparison_digest
from lakematch.mastering.probability import (
    DiagnosticPair, apply_calibration, calibration_metrics, implementation_digest,
    precision_lower_bound, preview_decision, score_band,
)
from lakematch.mastering.score_contract import (
    ArtifactRef, DataPartition, DecisionBands, PairScore, PlattCalibration, ProbabilityBinding,
    ScoreContext, definition,
)
from lakematch.mastering.survivorship_contract import MappingPin

FIXTURE = Path(__file__).resolve().parents[1] / "examples/mastering/company_pilot"


@pytest.fixture
def setup():
    domain = DomainContract.from_dict(json.loads((FIXTURE / "domain.json").read_text()))
    mappings = tuple(SourceMapping.from_dict(json.loads((FIXTURE / f"{name}_mapping.json").read_text()), domain)
                     for name in ("erp_vendor", "crm_account"))
    rules = MatchRuleset("unit_rules", 1, domain.domain_id, domain.version, domain.sha256,
        tuple(MappingPin(m.source_id, m.version, m.sha256) for m in mappings), comparison_digest())
    comparison = MatchBinding(rules, domain, mappings)
    # Hand-specified parameters and unrelated family IDs: no model fitting or
    # pilot-corpus observations occur in these numerical development checks.
    context = ScoreContext("unit_context", 1, ArtifactRef("unit_model", 1, digest("model")), "memory:unit-model",
        ArtifactRef("unit_features", 1, digest("features")), ("eq_legal_name", "eq_registration_id"),
        rules.sha256, digest("retrieval"), DataPartition("fit", digest("fit"), ("fit_1", "fit_2"), "sampled_training_pairs"))
    calibration = PlattCalibration("unit_calibration", 1, context.sha256,
        DataPartition("calibration", digest("calibration"), ("cal_1",), "complete_candidates"),
        1., 0., 1e-6, implementation_digest())
    bands = DecisionBands("unit_bands", 1, calibration.sha256,
        DataPartition("validation", digest("validation"), ("val_1", "val_2"), "complete_candidates"), .2, .8)
    binding = ProbabilityBinding(comparison, context, calibration, bands)
    records = [{"source_id": m.source_id, "source_key": str(i), "version": 1, "mapping_version": m.version,
        "mapping_sha256": m.sha256, "deleted": False, "values": {"record_kind": "legal_company",
            "legal_name": "Example company", "country": "FR", "registration_id": "123"}}
        for i, m in enumerate(mappings)]
    return binding, records


def evidence(setup):
    return compare_pair(setup[0].comparison, *setup[1], candidate_methods=["identifier", "name"])


def preview(setup, p):
    comparison = evidence(setup)
    return preview_decision(setup[0], comparison, PairScore(setup[0].context.sha256, comparison["evidence_sha256"], p))


def test_serialization_pins_order_model_and_detaches_definitions(setup):
    b, _ = setup
    assert ScoreContext.from_dict(definition(b.context)) == b.context
    assert PlattCalibration.from_dict(definition(b.calibration)) == b.calibration
    assert DecisionBands.from_dict(definition(b.bands)) == b.bands
    changed = replace(b.context, feature_order=tuple(reversed(b.context.feature_order)))
    assert changed.sha256 != b.context.sha256
    with pytest.raises(ContractError, match="score-context binding"):
        replace(b, context=changed)
    manifest = b.manifest()
    manifest["score_context"]["feature_order"].append("changed")
    assert len(b.context.feature_order) == 2
    assert manifest["authority"] == "unapproved_worker_preview"


@pytest.mark.parametrize("p", [0., .01, .25, .5, .9, 1.])
def test_identity_transform_and_explicit_clipping(setup, p):
    transform = apply_calibration(setup[0].calibration, p)
    expected = min(1 - 1e-6, max(1e-6, p))
    assert transform["probability"] == pytest.approx(expected, abs=1e-15)
    assert transform["input_probability"] == p
    assert transform["clipped_probability"] == expected
    assert transform["input_was_clipped"] == (p in (0, 1))


def test_nontrivial_transform_monotonic_and_numerically_stable(setup):
    calibration = replace(setup[0].calibration, coefficient=2., intercept=math.log(3))
    assert apply_calibration(calibration, .5)["probability"] == pytest.approx(.75)
    # logit(.25) = -log(3), so sigmoid(2*logit(.25)+log(3)) = .25.
    assert apply_calibration(calibration, .25)["probability"] == pytest.approx(.25)
    values = [apply_calibration(calibration, p)["probability"] for p in (0, .1, .5, .9, 1)]
    assert values == sorted(values)
    for intercept, expected in ((-1000, 0.), (1000, 1.)):
        saturated = replace(calibration, coefficient=0., intercept=intercept)
        assert apply_calibration(saturated, .5)["probability"] == expected


@pytest.mark.parametrize("p,band", [(0., "reject"), (math.nextafter(.2, 0), "reject"), (.2, "review"),
    (math.nextafter(.2, 1), "review"), (math.nextafter(.8, 0), "review"), (.8, "accept"), (1., "accept")])
def test_exact_band_boundaries(setup, p, band):
    assert score_band(setup[0].bands, p) == band


@pytest.mark.parametrize("p,band", [(.1, "reject"), (.5, "review"), (.99, "accept"), (None, "review")])
def test_proposed_bands_never_authorize_automatic_actions(setup, p, band):
    result = preview(setup, p)
    assert result["decision"]["proposed_band"] == band
    assert result["decision"]["route"] == "review"
    assert result["decision"]["auto_merge_eligible"] is False
    assert result["qualification"] == "development_preview_only"
    assert result["result_sha256"] == digest({k: v for k, v in result.items() if k != "result_sha256"})
    if p is None:
        assert result["transform"] is result["decision"]["numerical_band"] is None
        assert result["decision"]["reason"] == "missing_model_probability"


@pytest.mark.parametrize("change,veto", [({"registration_id": "different"}, "identifier_conflict"),
    ({"country": "DE"}, "different_jurisdictions"), ({"legal_name": None}, "incomplete_identity")])
def test_conflicts_veto_even_maximum_scores(setup, change, veto):
    setup[1][0]["values"].update(change)
    result = preview(setup, 1.)
    assert result["decision"]["numerical_band"] == "accept"
    assert result["decision"]["proposed_band"] == "review"
    assert veto in result["decision"]["vetoes"]
    assert result["decision"]["reason"] == "deterministic_conflict"


def test_granularity_deletion_self_and_same_source_rules_cannot_be_bypassed(setup):
    b, records = setup
    branch = deepcopy(records)
    branch[0]["values"]["record_kind"] = "branch"
    assert preview((b, branch), 1.)["decision"]["route"] == "exclude"
    deleted = deepcopy(records)
    deleted[0].update(deleted=True, values={})
    assert preview((b, deleted), 1.)["decision"]["route"] == "exclude"
    assert preview((b, [records[0], records[0]]), 1.)["decision"]["route"] == "exclude"
    duplicate = deepcopy(records[0])
    duplicate["source_key"] = "another-key"
    result = preview((b, [records[0], duplicate]), 1.)
    assert result["decision"]["proposed_band"] == "review"
    assert "same_source_duplicate" in result["decision"]["vetoes"]


def test_stale_scores_and_tampered_evidence_are_rejected(setup):
    b, records = setup
    comparison = evidence(setup)
    score = PairScore(b.context.sha256, comparison["evidence_sha256"], .99)
    for field in ("score_context_sha256", "comparison_sha256"):
        with pytest.raises(ContractError, match="belongs to another"):
            preview_decision(b, comparison, replace(score, **{field: "0" * 64}))
    for change in (True, 0):
        counterfeit = deepcopy(comparison)
        counterfeit["decision"]["auto_merge_eligible"] = change
        with pytest.raises(ContractError, match="does not replay"):
            preview_decision(b, counterfeit, score)
    counterfeit = deepcopy(comparison)
    counterfeit["fields"]["country"]["comparison"] = "differ"
    counterfeit["evidence_sha256"] = digest({k: v for k, v in counterfeit.items() if k != "evidence_sha256"})
    with pytest.raises(ContractError, match="does not replay"):
        preview_decision(b, counterfeit, replace(score, comparison_sha256=counterfeit["evidence_sha256"]))
    records[0]["version"] = 2
    with pytest.raises(ContractError, match="another comparison"):
        preview_decision(b, evidence(setup), score)


def test_retry_and_reversed_pair_stability_without_input_mutation(setup):
    b, records = setup
    original = deepcopy(records)
    first = preview(setup, .9)
    assert first == preview(setup, .9)
    assert first == preview((b, list(reversed(records))), .9)
    first["comparison"]["records"][0]["values"]["legal_name"] = "Altered response"
    assert records == original
    assert preview(setup, .9)["comparison"]["records"][0]["values"]["legal_name"] == "Example company"


def test_declared_split_overlap_or_reused_snapshot_cannot_bind(setup):
    b, _ = setup
    for partition, message in ((replace(b.calibration.calibration, family_ids=("fit_1",)), "disjoint"),
                               (replace(b.calibration.calibration, snapshot_sha256=b.context.fitting.snapshot_sha256), "distinct")):
        cal = replace(b.calibration, calibration=partition)
        with pytest.raises(ContractError, match=message):
            replace(b, calibration=cal, bands=replace(b.bands, calibration_sha256=cal.sha256))
    with pytest.raises(ContractError, match="disjoint"):
        replace(b, bands=replace(b.bands, validation=replace(b.bands.validation, family_ids=("cal_1",))))


def test_implementation_and_policy_drift_are_explicit(setup, monkeypatch):
    b, _ = setup
    with pytest.raises(ContractError, match="ruleset binding"):
        replace(b, context=replace(b.context, ruleset_sha256="0" * 64))
    with pytest.raises(ContractError, match="Band calibration binding"):
        replace(b, bands=replace(b.bands, calibration_sha256="0" * 64))
    monkeypatch.setattr("lakematch.mastering.probability.implementation_digest", lambda: "0" * 64)
    with pytest.raises(ContractError, match="implementation changed"):
        preview(setup, .5)
    with pytest.raises(ContractError, match="implementation changed"):
        apply_calibration(b.calibration, .5)


@pytest.mark.parametrize("value", [True, -1, 2, float("nan"), float("inf"), "0.9", 10**1000])
def test_invalid_scores_do_not_turn_into_confident_decisions(setup, value):
    with pytest.raises(ContractError):
        PairScore(setup[0].context.sha256, "0" * 64, value)
    with pytest.raises(ContractError):
        apply_calibration(setup[0].calibration, value)


@pytest.mark.parametrize("change", [{"coefficient": -1}, {"coefficient": float("nan")}, {"intercept": float("inf")},
    {"clip_epsilon": 0}, {"clip_epsilon": .5}, {"schema_version": True}, {"algorithm": "implicit"}, {"unknown": 1}])
def test_calibration_definition_is_strict(setup, change):
    with pytest.raises(ContractError):
        PlattCalibration.from_dict({**definition(setup[0].calibration), **change})


@pytest.mark.parametrize("change", [{"reject_below": .8}, {"accept_at_least": .1}, {"reject_below": True},
    {"accept_at_least": float("nan")}, {"schema_version": 2}])
def test_band_definition_is_strict(setup, change):
    with pytest.raises(ContractError):
        DecisionBands.from_dict({**definition(setup[0].bands), **change})


@pytest.mark.parametrize("change", [{"feature_order": "one"}, {"feature_order": ["same", "same"]},
    {"feature_order": []}, {"positive_label": True}, {"positive_label": 0}, {"output_scale": "retrieval_rank"}, {"version": 0}])
def test_feature_and_score_contract_is_strict(setup, change):
    with pytest.raises(ContractError):
        ScoreContext.from_dict({**definition(setup[0].context), **change})


@pytest.mark.parametrize("change", [{"family_ids": "abc"}, {"family_ids": ["b", "a"]}, {"family_ids": ["a", "a"]},
    {"role": "confirmation"}, {"role": []}, {"population": "sampled_training_pairs"}, {"population": []}])
def test_partition_requires_explicit_disjointness_inputs(setup, change):
    with pytest.raises(ContractError):
        DataPartition.from_dict({**definition(setup[0].calibration.calibration), **change})


def test_evidence_and_partition_limits(setup):
    comparison = evidence(setup)
    score = PairScore(setup[0].context.sha256, comparison["evidence_sha256"], .5)
    comparison["extra"] = "x" * (256 * 1024)
    with pytest.raises(ContractError, match="256 KiB"):
        preview_decision(setup[0], comparison, score)
    with pytest.raises(ContractError, match="10000"):
        replace(setup[0].context.fitting, family_ids=("a",) * 10001)
    with pytest.raises(ContractError, match="256"):
        replace(setup[0].context, feature_order=("a",) * 257)


def diagnostic_rows():
    return [DiagnosticPair(digest(i), label, raw, transformed) for i, (label, raw, transformed) in enumerate(
        [(0, 0., 0.), (1, .25, .75), (0, .75, .25), (1, 1., 1.)])]


def test_brier_reliability_and_empty_bins_match_hand_calculation():
    rows = diagnostic_rows()
    result = calibration_metrics(rows, bins=4)
    assert result == calibration_metrics(list(reversed(rows)), bins=4)
    assert result["raw"]["brier"] == .28125
    assert result["transformed"]["brier"] == .03125
    assert result["raw"]["ece"] == .375
    assert result["transformed"]["ece"] == .125
    assert result["raw"]["reliability"][2]["count"] == 0
    assert result["raw"]["reliability"][2]["mean_probability"] is None
    assert result["raw"]["reliability"][3]["count"] == 2
    assert result["raw"]["reliability"][3]["upper_inclusive"] is True
    assert result["pairs"] == 4 and result["positive_labels"] == 2
    assert result["quality_qualified"] is False
    assert result["scope"] == "supplied_scored_pairs_only"


def test_diagnostics_refuse_duplicates_bad_labels_and_unbounded_input(monkeypatch):
    row = diagnostic_rows()[0]
    for rows in ([], [row] * 100001, [row, row], [asdict(row)]):
        with pytest.raises(ContractError):
            calibration_metrics(rows)
    for label in (True, -1, 2, "1"):
        with pytest.raises(ContractError):
            replace(row, label=label)
    for bins in (True, 1, 21):
        with pytest.raises(ContractError):
            calibration_metrics([row], bins=bins)
    monkeypatch.setattr("lakematch.mastering.probability.MAX_METRIC_BYTES", 1)
    with pytest.raises(ContractError, match="16 MiB"):
        calibration_metrics([row])


@pytest.mark.parametrize("successes,trials,expected", [(0, 0, None), (0, 5, 0.), (1, 1, .05),
    (1, 2, 1 - math.sqrt(.95)), (2, 2, math.sqrt(.05)), (1, 3, 1 - .95**(1/3)),
    (5, 10, .222441101008129), (9, 10, .6058366975634952),
    # Large-n references independently checked with scipy.stats.beta.ppf(.05, k, n-k+1).
    (1, 10000, 5.1293162837673e-06), (100, 10000, .008420198936739018),
    (5000, 10000, .49172650440373994), (9999, 10000, .9995257023408346)])
def test_exact_one_sided_precision_bound(successes, trials, expected):
    actual = precision_lower_bound(successes, trials)
    assert actual is None if expected is None else actual == pytest.approx(expected, rel=0, abs=1e-12)


def test_independent_count_requirement_is_numerical_not_a_quality_claim():
    # These are mathematical counts, not 600 observations or an achieved gate.
    assert precision_lower_bound(10, 10) < .75
    assert precision_lower_bound(597, 597) < .995
    assert precision_lower_bound(598, 598) >= .995
    assert precision_lower_bound(599, 600) < .995
    assert precision_lower_bound(600, 600) == pytest.approx(.05**(1/600))
    assert precision_lower_bound(600, 600, confidence=.99) < precision_lower_bound(600, 600)


@pytest.mark.parametrize("args", [(True, 2), (1, True), (-1, 2), (3, 2), (1, 10001), (1, 2.0)])
def test_precision_count_validation(args):
    with pytest.raises(ContractError):
        precision_lower_bound(*args)


@pytest.mark.parametrize("confidence", [True, .5, 1, float("nan"), float("inf")])
def test_precision_confidence_validation(confidence):
    with pytest.raises(ContractError):
        precision_lower_bound(1, 2, confidence=confidence)
