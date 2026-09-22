"""Portable, unqualified probability contracts; separate from v1 engine config."""
from dataclasses import asdict, dataclass
import math

from .contracts import ContractError, digest, identifier, positive_version
from .identity_contract import sha256_key, text_key
from .match_contract import MatchBinding

MAX_FAMILIES = 10_000
MAX_FEATURES = 256


def finite(value, label, low, high):
    if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
        raise ContractError(f"{label} must be a finite number in [{low}, {high}]")


def schema(value):
    if type(value) is not int or value != 1:
        raise ContractError("Unsupported probability schema_version")


def definition(value):
    # JSON-shaped, detached definitions are safe to hand to artifact writers.
    import json
    return json.loads(json.dumps(asdict(value), ensure_ascii=False, allow_nan=False))


@dataclass(frozen=True)
class ArtifactRef:
    id: str
    version: int
    sha256: str

    def __post_init__(self):
        identifier(self.id)
        positive_version(self.version)
        sha256_key(self.sha256)


@dataclass(frozen=True)
class DataPartition:
    role: str
    snapshot_sha256: str
    family_ids: tuple[str, ...]
    population: str

    def __post_init__(self):
        if not isinstance(self.role, str) or self.role not in {"fit", "calibration", "validation"}:
            raise ContractError("Only fit/calibration/validation partitions are supported")
        sha256_key(self.snapshot_sha256)
        if not isinstance(self.family_ids, tuple) or not 1 <= len(self.family_ids) <= MAX_FAMILIES:
            raise ContractError("Partition requires 1–10000 declared family IDs")
        for family in self.family_ids:
            text_key(family, "Family ID", 128)
        if tuple(sorted(set(self.family_ids))) != self.family_ids:
            raise ContractError("Family IDs must be unique and sorted")
        allowed = {"sampled_training_pairs", "complete_candidates"} if self.role == "fit" else {"complete_candidates"}
        if not isinstance(self.population, str) or self.population not in allowed:
            raise ContractError("Calibration/validation require declared complete candidate populations")

    @classmethod
    def from_dict(cls, value):
        try:
            if not isinstance(value["family_ids"], (list, tuple)):
                raise ContractError("Explicit family-ID sequence required")
            return cls(**{**value, "family_ids": tuple(value["family_ids"])})
        except (TypeError, KeyError) as error:
            raise ContractError("Invalid partition definition") from error


@dataclass(frozen=True)
class ScoreContext:
    context_id: str
    version: int
    model: ArtifactRef
    model_uri: str
    feature_contract: ArtifactRef
    feature_order: tuple[str, ...]
    ruleset_sha256: str
    retrieval_execution_sha256: str
    fitting: DataPartition
    output_scale: str = "positive_class_probability"
    positive_label: int = 1
    schema_version: int = 1

    def __post_init__(self):
        schema(self.schema_version)
        identifier(self.context_id)
        positive_version(self.version)
        if not isinstance(self.model, ArtifactRef) or not isinstance(self.feature_contract, ArtifactRef):
            raise ContractError("Typed model and feature artifact references required")
        text_key(self.model_uri, "Model URI", 2048)
        sha256_key(self.ruleset_sha256)
        sha256_key(self.retrieval_execution_sha256)
        if (not isinstance(self.feature_order, tuple) or not 1 <= len(self.feature_order) <= MAX_FEATURES):
            raise ContractError("Explicit order of 1–256 model features required")
        for name in self.feature_order:
            text_key(name, "Feature name", 128)
        if len(set(self.feature_order)) != len(self.feature_order):
            raise ContractError("Duplicate feature names")
        if not isinstance(self.fitting, DataPartition) or self.fitting.role != "fit":
            raise ContractError("Model fitting partition required")
        if self.output_scale != "positive_class_probability" or type(self.positive_label) is not int or self.positive_label != 1:
            raise ContractError("Only positive-label-1 probabilities are supported; retrieval ranks are not probabilities")

    @classmethod
    def from_dict(cls, value):
        try:
            if "schema_version" not in value:
                raise ContractError("Explicit score-context schema_version required")
            if not isinstance(value["feature_order"], (list, tuple)):
                raise ContractError("Explicit feature-order sequence required")
            return cls(**{**value, "model": ArtifactRef(**value["model"]),
                          "feature_contract": ArtifactRef(**value["feature_contract"]),
                          "feature_order": tuple(value["feature_order"]),
                          "fitting": DataPartition.from_dict(value["fitting"])})
        except (TypeError, KeyError) as error:
            raise ContractError("Invalid score-context definition") from error

    @property
    def sha256(self):
        return digest(asdict(self))


@dataclass(frozen=True)
class PlattCalibration:
    calibration_id: str
    version: int
    score_context_sha256: str
    calibration: DataPartition
    coefficient: float
    intercept: float
    clip_epsilon: float
    implementation_sha256: str
    algorithm: str = "platt_logit_v1"
    schema_version: int = 1

    def __post_init__(self):
        schema(self.schema_version)
        identifier(self.calibration_id)
        positive_version(self.version)
        sha256_key(self.score_context_sha256)
        sha256_key(self.implementation_sha256)
        if self.algorithm != "platt_logit_v1":
            raise ContractError("Unsupported probability transform")
        if not isinstance(self.calibration, DataPartition) or self.calibration.role != "calibration":
            raise ContractError("Calibration partition required")
        # A monotonic calibrator preserves the scorer's ordering. No implicit
        # coefficient, threshold or clipping choice is supplied by this contract.
        finite(self.coefficient, "Calibration coefficient", 0, 1000)
        finite(self.intercept, "Calibration intercept", -1000, 1000)
        finite(self.clip_epsilon, "Probability clipping epsilon", 1e-12, 1e-3)

    @classmethod
    def from_dict(cls, value):
        try:
            if "schema_version" not in value:
                raise ContractError("Explicit calibration schema_version required")
            return cls(**{**value, "calibration": DataPartition.from_dict(value["calibration"])})
        except (TypeError, KeyError) as error:
            raise ContractError("Invalid calibration definition") from error

    @property
    def sha256(self):
        return digest(asdict(self))


@dataclass(frozen=True)
class DecisionBands:
    policy_id: str
    version: int
    calibration_sha256: str
    validation: DataPartition
    reject_below: float
    accept_at_least: float
    schema_version: int = 1

    def __post_init__(self):
        schema(self.schema_version)
        identifier(self.policy_id)
        positive_version(self.version)
        sha256_key(self.calibration_sha256)
        if not isinstance(self.validation, DataPartition) or self.validation.role != "validation":
            raise ContractError("Band-selection validation partition required")
        finite(self.reject_below, "Reject boundary", 0, 1)
        finite(self.accept_at_least, "Accept boundary", 0, 1)
        if self.reject_below >= self.accept_at_least:
            raise ContractError("Reject boundary must be below accept boundary")

    @classmethod
    def from_dict(cls, value):
        try:
            if "schema_version" not in value:
                raise ContractError("Explicit band-policy schema_version required")
            return cls(**{**value, "validation": DataPartition.from_dict(value["validation"])})
        except (TypeError, KeyError) as error:
            raise ContractError("Invalid band-policy definition") from error

    @property
    def sha256(self):
        return digest(asdict(self))


@dataclass(frozen=True)
class ProbabilityBinding:
    comparison: MatchBinding
    context: ScoreContext
    calibration: PlattCalibration
    bands: DecisionBands

    def __post_init__(self):
        if not all(isinstance(v, t) for v, t in ((self.comparison, MatchBinding), (self.context, ScoreContext),
                (self.calibration, PlattCalibration), (self.bands, DecisionBands))):
            raise ContractError("Typed probability binding required")
        if self.context.ruleset_sha256 != self.comparison.ruleset.sha256:
            raise ContractError("Scoring ruleset binding differs")
        if self.calibration.score_context_sha256 != self.context.sha256:
            raise ContractError("Calibration score-context binding differs")
        if self.bands.calibration_sha256 != self.calibration.sha256:
            raise ContractError("Band calibration binding differs")
        partitions = (self.context.fitting, self.calibration.calibration, self.bands.validation)
        seen = set()
        for partition in partitions:
            if seen.intersection(partition.family_ids):
                raise ContractError("Fitting/calibration/validation families must be disjoint")
            seen.update(partition.family_ids)
        if len({p.snapshot_sha256 for p in partitions}) != 3:
            raise ContractError("Partition snapshots must be distinct")
        self.check_implementation()

    def check_implementation(self):
        from .probability import implementation_digest
        self.comparison.check_implementation()
        if self.calibration.implementation_sha256 != implementation_digest():
            raise ContractError("Probability implementation changed; issue new artifact versions")

    def manifest(self):
        return {"score_context": definition(self.context), "calibration": definition(self.calibration),
                "bands": definition(self.bands), "authority": "unapproved_worker_preview"}


@dataclass(frozen=True)
class PairScore:
    score_context_sha256: str
    comparison_sha256: str
    probability: float | None

    def __post_init__(self):
        sha256_key(self.score_context_sha256)
        sha256_key(self.comparison_sha256)
        if self.probability is not None:
            finite(self.probability, "Raw model probability", 0, 1)
