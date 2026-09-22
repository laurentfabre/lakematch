"""Unqualified score-band previews; no fitting, model loading or remote services."""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path

from .contracts import ContractError, digest
from .identity_contract import sha256_key
from .match_evidence import compare_pair
from .score_contract import PairScore, PlattCalibration, ProbabilityBinding, definition, finite

MAX_PAIR_BYTES = 256 * 1024
MAX_METRIC_ROWS = 100_000
MAX_METRIC_BYTES = 16 * 1024 * 1024
VETOES = frozenset({"incomplete_identity", "different_jurisdictions", "identifier_conflict", "same_source_duplicate"})


def implementation_digest():
    paths = [Path(__file__), *(Path(__file__).with_name(n) for n in
             ("score_contract.py", "contracts.py", "identity_contract.py"))]
    return digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})


def apply_calibration(calibration, probability):
    """Apply explicit supplied parameters; their empirical fitness is unverified."""
    if not isinstance(calibration, PlattCalibration):
        raise ContractError("Typed calibration definition required")
    if calibration.implementation_sha256 != implementation_digest():
        raise ContractError("Probability implementation changed; issue new artifact versions")
    finite(probability, "Raw model probability", 0, 1)
    clipped = min(1 - calibration.clip_epsilon, max(calibration.clip_epsilon, probability))
    logit = math.log(clipped) - math.log1p(-clipped)
    z = calibration.coefficient * logit + calibration.intercept
    # Both branches avoid exponent overflow, including saturated coefficients.
    p = 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))
    return {"probability": p, "input_probability": probability,
            "clipped_probability": clipped, "input_was_clipped": clipped != probability}


def score_band(bands, probability):
    """Pure numerical band: reject is strict; accept is inclusive."""
    from .score_contract import DecisionBands
    if not isinstance(bands, DecisionBands):
        raise ContractError("Typed decision-band policy required")
    finite(probability, "Transformed probability", 0, 1)
    if probability < bands.reject_below:
        return "reject"
    return "accept" if probability >= bands.accept_at_least else "review"


def preview_decision(binding, comparison, score):
    """Bind a worker score to exact, replayable comparison evidence; never merge."""
    if not isinstance(binding, ProbabilityBinding) or not isinstance(score, PairScore):
        raise ContractError("Typed probability binding and pair score required")
    binding.check_implementation()
    try:
        raw = json.dumps(comparison, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        if len(raw.encode()) > MAX_PAIR_BYTES:
            raise ContractError("Comparison evidence exceeds 256 KiB")
        evidence = json.loads(raw)
        if not isinstance(evidence, dict) or not isinstance(evidence.get("records"), list) or len(evidence["records"]) != 2:
            raise ContractError("Two-record comparison evidence required")
        actual = compare_pair(binding.comparison, *evidence["records"], candidate_methods=evidence["candidate_methods"])
        if digest(evidence) != digest(actual):
            raise ContractError("Comparison evidence does not replay with its pinned inputs")
    except (KeyError, TypeError, ValueError, RecursionError) as error:
        if isinstance(error, ContractError):
            raise
        raise ContractError("Bounded comparison evidence required") from error
    if score.score_context_sha256 != binding.context.sha256:
        raise ContractError("Pair score belongs to another model/feature context")
    if score.comparison_sha256 != evidence["evidence_sha256"]:
        raise ContractError("Pair score belongs to another comparison snapshot")
    transform = None if score.probability is None else apply_calibration(binding.calibration, score.probability)
    numerical = None if transform is None else score_band(binding.bands, transform["probability"])
    vetoes = [r["rule_id"] for r in evidence["rules"] if r["rule_id"] in VETOES]
    if evidence["decision"]["route"] == "exclude":
        proposed, route, reason = "exclude", "exclude", evidence["decision"]["rule_id"]
    elif vetoes:
        proposed, route, reason = "review", "review", "deterministic_conflict"
    elif transform is None:
        proposed, route, reason = "review", "review", "missing_model_probability"
    else:
        proposed, route, reason = numerical, "review", "unqualified_probability_policy"
    result = {"schema_version": 1, "comparison": evidence, "score": asdict(score),
              "contracts": {"score_context_sha256": binding.context.sha256, "model": definition(binding.context.model),
                            "feature_contract": definition(binding.context.feature_contract),
                            "calibration_sha256": binding.calibration.sha256, "bands_sha256": binding.bands.sha256},
              "transform": transform, "decision": {"numerical_band": numerical, "proposed_band": proposed,
                  "route": route, "reason": reason, "vetoes": vetoes, "auto_merge_eligible": False},
              "qualification": "development_preview_only"}
    result["result_sha256"] = digest(result)
    return result


@dataclass(frozen=True)
class DiagnosticPair:
    pair_id: str
    label: int
    raw_probability: float
    transformed_probability: float

    def __post_init__(self):
        sha256_key(self.pair_id)
        if type(self.label) is not int or self.label not in {0, 1}:
            raise ContractError("Diagnostic label must be integer 0 or 1")
        finite(self.raw_probability, "Raw diagnostic probability", 0, 1)
        finite(self.transformed_probability, "Transformed diagnostic probability", 0, 1)


def calibration_metrics(rows, *, bins=10):
    """Brier, reliability bins and ECE for supplied scored pairs only.

    No completeness, representative sampling, group independence or retrieval
    recall is inferred. This helper cannot qualify a production quality gate.
    """
    if type(bins) is not int or not 2 <= bins <= 20:
        raise ContractError("Use 2–20 equal-width reliability bins")
    if not isinstance(rows, (list, tuple)) or not 1 <= len(rows) <= MAX_METRIC_ROWS:
        raise ContractError("Diagnostics require 1–100000 scored pairs")
    if any(not isinstance(r, DiagnosticPair) for r in rows):
        raise ContractError("Typed diagnostic pairs required")
    if len({r.pair_id for r in rows}) != len(rows):
        raise ContractError("Duplicate diagnostic pair IDs")
    encoded = json.dumps([asdict(r) for r in rows], separators=(",", ":"), allow_nan=False)
    if len(encoded.encode()) > MAX_METRIC_BYTES:
        raise ContractError("Diagnostic input exceeds 16 MiB")
    ordered = sorted(rows, key=lambda r: r.pair_id)
    def metrics(attribute):
        buckets = [[] for _ in range(bins)]
        for r in ordered:
            p = getattr(r, attribute)
            buckets[min(bins - 1, int(p * bins))].append((p, r.label))
        reliability = []
        for i, bucket in enumerate(buckets):
            mean = math.fsum(p for p, _ in bucket) / len(bucket) if bucket else None
            rate = math.fsum(y for _, y in bucket) / len(bucket) if bucket else None
            reliability.append({"lower_inclusive": i / bins, "upper": (i + 1) / bins,
                                "upper_inclusive": i == bins - 1, "count": len(bucket),
                                "mean_probability": mean, "observed_positive_rate": rate})
        return {"brier": math.fsum((getattr(r, attribute) - r.label) ** 2 for r in ordered) / len(ordered),
                "ece": math.fsum(abs(b["mean_probability"] - b["observed_positive_rate"]) * b["count"]
                                 for b in reliability if b["count"]) / len(ordered), "reliability": reliability}
    return {"schema_version": 1, "scope": "supplied_scored_pairs_only", "quality_qualified": False,
            "pairs": len(rows), "positive_labels": sum(r.label for r in rows),
            "raw": metrics("raw_probability"), "transformed": metrics("transformed_probability")}


def precision_lower_bound(successes, trials, *, confidence=.95):
    """One-sided Clopper–Pearson bound; callers must establish independence.

    Counts alone cannot prove the sampling/selection requirements. Zero trials
    return None, not a passing bound. At most 10,000 independent observations.
    """
    if type(trials) is not int or not 0 <= trials <= 10_000 or type(successes) is not int or not 0 <= successes <= trials:
        raise ContractError("Expected integer counts with 0 <= successes <= trials <= 10000")
    finite(confidence, "Confidence", .5, 1)
    if confidence in {.5, 1}:
        raise ContractError("Confidence must be strictly between .5 and 1")
    if trials == 0:
        return None
    if successes == 0:
        return 0.
    alpha = 1 - confidence
    if successes == trials:
        return math.exp(math.log(alpha) / trials)
    # Invert P(Binomial(n,p) >= k) = alpha below the observed k/n. Terms
    # decrease throughout this tail, so a recurrence avoids huge binomials.
    k, n = successes, trials
    log_combination = math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    low, high = 0., k / n
    for _ in range(64):
        p = (low + high) / 2
        start = log_combination + k * math.log(p) + (n - k) * math.log1p(-p)
        term, tail_factor = 1., 1.
        for j in range(k, n):
            term *= (n - j) * p / ((j + 1) * (1 - p))
            tail_factor += term
        tail = math.exp(start) * tail_factor
        if tail < alpha:
            low = p
        else:
            high = p
    return low
