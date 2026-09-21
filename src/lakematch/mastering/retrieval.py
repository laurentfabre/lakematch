"""Bounded portable company candidate unions; retrieval rank is not match probability.

The legacy Spark v1 engine and its frozen replay contracts are unchanged.
Only feature projections enter retrieval. Truth is consumed by an evaluator later.
"""
from collections import defaultdict
from dataclasses import dataclass
import re
import time
import unicodedata

FEATURES = frozenset({"legal_name", "country", "registration_id", "address_line1", "city", "postal_code"})
ALTERNATIVES = {
    "identifier": ("identifier",),
    "identifier_name": ("identifier", "name"),
    "identifier_name_tokens": ("identifier", "name", "tokens"),
    "identifier_name_tokens_trigrams": ("identifier", "name", "tokens", "trigrams"),
}
SUFFIXES = {"sas", "sa", "limited", "ltd", "gmbh", "bv", "sl", "llc", "inc", "plc"}


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class Limits:
    per_left: int = 50
    pairs: int = 2_000_000
    posting_visits: int = 20_000_000
    seconds: float = 900
    input_rows_per_source: int = 20_000

    def __post_init__(self):
        for name, ceiling in (("per_left", 50), ("pairs", 2_000_000), ("posting_visits", 20_000_000),
                              ("input_rows_per_source", 20_000)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f"{name} exceeds the frozen finite envelope")
        if type(self.seconds) not in (int, float) or not 0 < self.seconds <= 900:
            raise ValueError("seconds must be in (0, 900]")


def normalize(value):
    ascii_text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().casefold()
    return " ".join(re.findall(r"[a-z0-9]+", ascii_text))


def _normal_features(row):
    if set(row) != {"record_id", "features"} or not isinstance(row["record_id"], str) or not row["record_id"].strip():
        raise ValueError("Expected opaque routing ID and an explicit feature object")
    features = row["features"]
    if not isinstance(features, dict) or set(features) != FEATURES:
        raise ValueError("Only the frozen company feature projection is accepted")
    if any(value is not None and not isinstance(value, str) for value in features.values()):
        raise ValueError("Company features must be strings or null")
    if any(not features.get(name) or not features[name].strip() for name in ("legal_name", "country")):
        raise ValueError("Name and country are required")
    if any(len(value or "") > 2048 for value in features.values()):
        raise ValueError("Feature exceeds 2048 characters")
    name = normalize(features["legal_name"]).split()
    while name and name[-1] in SUFFIXES:
        name.pop()
    name = " ".join(name)
    return {"name": name, "tokens": frozenset(name.split()),
            "trigrams": frozenset(name[i:i+3] for i in range(max(0, len(name)-2))),
            "identifier": re.sub(r"[^a-z0-9]", "", normalize(features["registration_id"])),
            "country": normalize(features["country"]), "address": normalize(features["address_line1"]),
            "postal": normalize(features["postal_code"])}


def _overlap(a, b):
    return len(a & b) / len(a | b) if a or b else 0.


def _rank(a, b):
    # Retrieval priorities only. Never expose these numbers as calibrated scores.
    same_id = bool(a["identifier"]) and (a["country"], a["identifier"]) == (b["country"], b["identifier"])
    same_name = bool(a["name"]) and a["name"] == b["name"]
    same_address = bool(a["address"]) and (a["address"], a["postal"]) == (b["address"], b["postal"])
    return (2 * same_id + same_name + _overlap(a["tokens"], b["tokens"]) +
            _overlap(a["trigrams"], b["trigrams"]) + .2 * same_address + .1 * (a["country"] == b["country"]))


def retrieve(left, right, alternative="identifier_name_tokens", limits=Limits()):
    """Return per-anchor retained candidates and truncation evidence.

    A whole-run pair/posting/time cap raises instead of dropping unseen anchors.
    The per-anchor top-k cap records its pre-cap candidates for recall diagnosis.
    """
    if alternative not in ALTERNATIVES:
        raise ValueError("Undeclared retrieval alternative")
    if max(len(left), len(right)) > limits.input_rows_per_source:
        raise BudgetExceeded("Source row limit exceeded")
    started = time.monotonic()
    methods = ALTERNATIVES[alternative]
    indexes = {method: defaultdict(list) for method in methods}
    right_features = {}
    for row in right:
        key, value = row["record_id"], _normal_features(row)
        if key in right_features:
            raise ValueError("Duplicate right source key")
        right_features[key] = value
        for method in methods:
            if method == "identifier":
                keys = [(value["country"], value["identifier"])] if value["identifier"] else []
            elif method == "name":
                keys = [value["name"]] if value["name"] else []
            elif method == "tokens":
                keys = [(value["country"], token) for token in value["tokens"]]
            else:
                keys = value["trigrams"]
            for term in keys:
                indexes[method][term].append(key)
    rows, seen, visits, pairs = [], set(), 0, 0
    for row in left:
        if time.monotonic() - started > limits.seconds:
            raise BudgetExceeded("Retrieval time limit exceeded")
        key, value = row["record_id"], _normal_features(row)
        if key in seen:
            raise ValueError("Duplicate left source key")
        seen.add(key)
        union = defaultdict(set)
        for method in methods:
            index = indexes[method]
            if method == "identifier":
                terms = [(value["country"], value["identifier"])] if value["identifier"] else []
            elif method == "name":
                terms = [value["name"]] if value["name"] else []
            else:
                terms = ([(value["country"], t) for t in value["tokens"]]
                         if method == "tokens" else list(value["trigrams"]))
                # Select among available postings, then use a stable tie break.
                terms = sorted((t for t in terms if t in index), key=lambda t: (len(index[t]), t))[:2 if method == "tokens" else 3]
            for term in terms:
                bucket = index.get(term, ())
                visits += len(bucket)
                if visits > limits.posting_visits:
                    raise BudgetExceeded("Pre-join posting budget exceeded")
                for candidate in bucket:
                    union[candidate].add(method)
        ordered = sorted(union, key=lambda candidate: (-_rank(value, right_features[candidate]), candidate))
        kept = ordered[:limits.per_left]
        pairs += len(kept)
        if pairs > limits.pairs:
            raise BudgetExceeded("Retained candidate-pair budget exceeded")
        rows.append({"left_id": key, "pre_cap_count": len(union), "truncated": len(union) > len(kept),
                     "candidates": [{"right_id": candidate, "methods": sorted(union[candidate])} for candidate in kept],
                     "dropped_right_ids": ordered[limits.per_left:]})
    if time.monotonic() - started > limits.seconds:
        raise BudgetExceeded("Retrieval time limit exceeded")
    return {"alternative": alternative, "rows": rows, "retained_pairs": pairs,
            "posting_visits": visits, "wall_seconds": time.monotonic() - started}
