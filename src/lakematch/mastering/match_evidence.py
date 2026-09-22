"""Bounded field comparisons and deterministic suggestions; never auto-merges."""
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from .contracts import ContractError, digest, positive_version
from .identity_contract import SourceRef
from .match_contract import FIELDS, METHODS, MatchBinding

MAX_BYTES = 64 * 1024
MAX_CHARS = 2048
SUFFIXES = frozenset({"sas", "sa", "limited", "ltd", "gmbh", "bv", "sl", "llc", "inc", "plc"})
REASONS = {
    "deleted_source": "A deleted source is not eligible for a new identity decision.",
    "same_source_record": "These are versions of the same source record, not two identities to merge.",
    "ineligible_granularity": "A branch or family cannot be merged into a legal-company master.",
    "incomplete_identity": "Record kind, legal name or country is missing or invalid.",
    "different_jurisdictions": "The records declare different legal jurisdictions; review the source values.",
    "identifier_conflict": "Registration identifiers disagree in the same jurisdiction; resolve the conflict first.",
    "same_source_duplicate": "Distinct records in one source need explicit duplicate review.",
    "identifier_agreement": "Registration identifiers agree in the same jurisdiction; uniqueness is unverified.",
    "name_agreement": "Normalized names agree; name agreement alone does not establish identity.",
    "insufficient_evidence": "No stronger deterministic identity rule applies.",
}


def implementation_digest():
    paths = (Path(__file__), *(Path(__file__).with_name(n) for n in
              ("match_contract.py", "contracts.py", "identity_contract.py", "survivorship_contract.py")))
    return digest({"files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                   "unicode_database": unicodedata.unidata_version})


def _normal(field, value):
    if field == "country":
        # Never silently turn a full-width/confusable code into a jurisdiction.
        return value.strip().upper() if re.fullmatch(r"[A-Za-z]{2}", value.strip()) else None
    if field == "registration_id":
        if not re.fullmatch(r"[A-Za-z0-9\s./-]+", value):
            return None
        return re.sub(r"[^a-z0-9]", "", value.casefold()) or None
    if field == "record_kind":
        return value if value in {"legal_company", "branch", "family"} else None
    # Preserve non-Latin letters. ASCII-dropping retrieval normalization is not
    # an identity comparator; these algorithms intentionally have distinct IDs.
    text = unicodedata.normalize("NFKD", value).casefold()
    text = "".join(c for c in text if not unicodedata.combining(c))
    tokens = "".join(c if c.isalnum() else " " for c in text).split()
    if field == "legal_name":
        while tokens and tokens[-1] in SUFFIXES:
            tokens.pop()
    return " ".join(tokens) or None


def _value(record, field):
    values = record["values"]
    raw = values.get(field)
    normal = None
    if record["deleted"]:
        state = "deleted"
    elif field not in values:
        state = "missing"
    elif raw is None:
        state = "null"
    elif not isinstance(raw, str):
        state = "invalid_type"
    elif not raw.strip():
        state = "blank"
    else:
        normal = _normal(field, raw)
        state = "present" if normal else "invalid_format"
    return {"value": raw, "state": state, "normalized": normal}


def _record(binding, record):
    keys = {"source_id", "source_key", "version", "mapping_version", "mapping_sha256", "deleted", "values"}
    if not isinstance(record, dict) or set(record) != keys:
        raise ContractError("Explicit bounded comparison source-version keys required")
    SourceRef(record["source_id"], record["source_key"])
    positive_version(record["version"])
    positive_version(record["mapping_version"])
    mapping = next((m for m in binding.mappings if m.source_id == record["source_id"]), None)
    if mapping is None or (record["mapping_version"], record["mapping_sha256"]) != (mapping.version, mapping.sha256):
        raise ContractError("Comparison source mapping version/digest differs")
    if type(record["deleted"]) is not bool or not isinstance(record["values"], dict):
        raise ContractError("Typed deletion flag and source values required")
    if set(record["values"]) - {f.target for f in mapping.fields}:
        raise ContractError("Comparison values must use declared mapping fields")
    if record["deleted"] and record["values"]:
        raise ContractError("Comparison tombstones must have empty values")
    for value in record["values"].values():
        if value is not None and type(value) not in (str, int, float, bool):
            raise ContractError("Comparison accepts scalar values only")
        if isinstance(value, str) and len(value) > MAX_CHARS:
            raise ContractError("Comparison value exceeds 2048 characters")
    return record


def compare_pair(binding, left, right, *, candidate_methods):
    """Explain one supplied pair. Inputs are trusted mapped snapshots, not HTTP.

    Evidence carries no authenticated approval and no calibrated probability.
    Candidate methods are provenance only. The result cannot allocate or merge IDs.
    """
    if not isinstance(binding, MatchBinding):
        raise ContractError("Typed comparison binding required")
    binding.check_implementation()
    if (not isinstance(candidate_methods, (list, tuple)) or not 1 <= len(candidate_methods) <= 4
            or any(not isinstance(m, str) or m not in METHODS for m in candidate_methods)
            or len(set(candidate_methods)) != len(candidate_methods)):
        raise ContractError("Expected 1–4 unique declared candidate methods")
    try:
        raw = json.dumps([left, right], ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
        if len(raw.encode()) > MAX_BYTES:
            raise ContractError("Comparison request exceeds 64 KiB")
        records = [_record(binding, r) for r in json.loads(raw)]
    except (TypeError, ValueError, RecursionError) as error:
        if isinstance(error, ContractError):
            raise
        raise ContractError("Bounded JSON source snapshots required") from error
    records.sort(key=lambda r: (r["source_id"], r["source_key"], r["version"]))
    a, b = records
    hashes = [digest(r) for r in records]
    same_ref = (a["source_id"], a["source_key"]) == (b["source_id"], b["source_key"])
    if same_ref and a["version"] == b["version"] and hashes[0] != hashes[1]:
        raise ContractError("Changed content under the same source version")
    fields = {}
    for field in FIELDS:
        av, bv = _value(a, field), _value(b, field)
        usable = av["state"] == bv["state"] == "present"
        fields[field] = {"left": av, "right": bv,
                         "comparison": ("agree" if av["normalized"] == bv["normalized"] else "differ") if usable else "unavailable",
                         "raw_equal": av["value"] == bv["value"] if usable else None}
    def agrees(field):
        return fields[field]["comparison"] == "agree"
    def differs(field):
        return fields[field]["comparison"] == "differ"
    kind = fields["record_kind"]
    flags = {
        "deleted_source": a["deleted"] or b["deleted"],
        "same_source_record": same_ref,
        "ineligible_granularity": any(kind[s]["normalized"] in {"branch", "family"} for s in ("left", "right")),
        "incomplete_identity": any(fields[f][s]["state"] != "present" for f in ("record_kind", "legal_name", "country") for s in ("left", "right")),
        "different_jurisdictions": differs("country"),
        "identifier_conflict": agrees("country") and differs("registration_id"),
        "same_source_duplicate": a["source_id"] == b["source_id"] and not same_ref,
        "identifier_agreement": agrees("country") and agrees("registration_id"),
        "name_agreement": agrees("legal_name"),
        "insufficient_evidence": True,
    }
    triggered = [r for r in binding.ruleset.precedence if flags[r]]
    winner = triggered[0]
    excluded = winner in {"deleted_source", "same_source_record", "ineligible_granularity"}
    # An identifier collision is possible even when the name agrees. No rule
    # here is promoted to automatic acceptance without representative evidence.
    suggestion = "match" if winner == "identifier_agreement" else "unsure"
    if winner == "different_jurisdictions":
        suggestion = "no_match"
    if excluded:
        suggestion = "not_applicable"
    result = {"schema_version": 1, "pair_id": digest([{**{k: r[k] for k in ("source_id", "source_key", "version")},
                                                       "sha256": h} for r, h in zip(records, hashes)]),
              "binding": binding.manifest(), "records": records, "record_sha256": hashes,
              "candidate_methods": sorted(candidate_methods), "fields": fields,
              "rules": [{"rule_id": r, "selected": r == winner, "reason": REASONS[r]} for r in triggered],
              "decision": {"rule_id": winner, "suggestion": suggestion,
                           "route": "exclude" if excluded else "review", "reason": REASONS[winner],
                           "auto_merge_eligible": False},
              "model": None, "calibration": None, "probability": None,
              "qualification": "development_preview_only"}
    result["evidence_sha256"] = digest(result)
    return result
