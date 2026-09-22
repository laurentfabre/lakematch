"""Portable company features and JSON linear scores; no decision authority."""
from dataclasses import asdict, dataclass
import hashlib
import math
from pathlib import Path

from .contracts import ContractError, digest
from .match_evidence import _normal, implementation_digest as comparison_digest
from .retrieval import FEATURES

FIELD_ORDER = ("legal_name", "country", "registration_id", "address_line1", "city", "postal_code")
FEATURE_ORDER = tuple("agree_" + f for f in FIELD_ORDER) + (
    "name_token_jaccard", "name_trigram_jaccard", "street_trigram_jaccard",
    "identifier_unavailable", "identifier_conflict",
)


def feature_contract():
    return {"schema_version": 1, "algorithm": "company_linear_features_v1",
            "fields": list(FIELD_ORDER), "feature_order": list(FEATURE_ORDER),
            "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "comparison_implementation_sha256": comparison_digest(),
            "missing_agreement": False, "source_keys_are_features": False}


def normalize_features(values):
    if not isinstance(values, dict) or set(values) != FEATURES:
        raise ContractError("Only the six allowlisted matching fields are accepted")
    if any(v is not None and (not isinstance(v, str) or len(v) > 2048) for v in values.values()):
        raise ContractError("Matching fields must be bounded strings or null")
    return {f: _normal(f, v) if v and v.strip() else None for f, v in values.items()}


def _jaccard(a, b):
    return len(a & b) / len(a | b) if a or b else 0.


def _trigrams(value):
    return {value[i:i+3] for i in range(len(value)-2)} if value else set()


def pair_features(left, right):
    """Only normalized field comparisons enter the model, never routing/truth."""
    a, b = normalize_features(left), normalize_features(right)
    agreements = [float(a[f] is not None and a[f] == b[f]) for f in FIELD_ORDER]
    return tuple(agreements + [
        _jaccard(set((a['legal_name'] or '').split()), set((b['legal_name'] or '').split())),
        _jaccard(_trigrams(a['legal_name']), _trigrams(b['legal_name'])),
        _jaccard(_trigrams(a['address_line1']), _trigrams(b['address_line1'])),
        float(a['registration_id'] is None or b['registration_id'] is None),
        float(a['registration_id'] is not None and b['registration_id'] is not None
              and a['registration_id'] != b['registration_id']),
    ])


def sigmoid(value):
    return 1 / (1 + math.exp(-value)) if value >= 0 else math.exp(value) / (1 + math.exp(value))


@dataclass(frozen=True)
class LinearProbabilityModel:
    coefficients: tuple[float, ...]
    intercept: float
    feature_sha256: str
    schema_version: int = 1

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ContractError("Unsupported linear model schema")
        if not isinstance(self.coefficients, tuple) or len(self.coefficients) != len(FEATURE_ORDER):
            raise ContractError("Coefficients must follow the fixed feature order")
        if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1000
               for v in (*self.coefficients, self.intercept)):
            raise ContractError("Finite bounded linear parameters required")
        if self.feature_sha256 != digest(feature_contract()):
            raise ContractError("Model feature implementation differs")

    def probability(self, features):
        if len(features) != len(FEATURE_ORDER) or any(type(v) not in (int, float)
                or not math.isfinite(v) or not 0 <= v <= 1 for v in features):
            raise ContractError("Expected a finite feature vector in the fixed order")
        return sigmoid(self.intercept + math.fsum(w*x for w, x in zip(self.coefficients, features)))

    def definition(self):
        return {**asdict(self), "coefficients": list(self.coefficients)}

    @classmethod
    def from_dict(cls, value):
        try:
            if 'schema_version' not in value:
                raise ContractError("Explicit linear model schema required")
            return cls(**{**value, "coefficients": tuple(value['coefficients'])})
        except (TypeError, KeyError) as error:
            raise ContractError("Invalid linear model definition") from error
