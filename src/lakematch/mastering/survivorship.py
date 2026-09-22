"""Bounded scalar calculation over explicit trusted snapshots; never publishes."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .contracts import ContractError, digest, positive_version
from .identity_contract import MAX_MEMBERS, SourceRef, master_key, text_key
from .survivorship_contract import MAX_BYTES, MAX_DECISIONS, SurvivorshipBinding


class SurvivorshipConflict(ValueError):
    """An incomplete snapshot or conflicting/stale approval cannot be applied."""


def timestamp(value):
    try:
        if not isinstance(value, str) or "T" not in value:
            raise ValueError()
        result = datetime.fromisoformat(value)
        if result.utcoffset() is None:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError) as error:
        raise ContractError("Explicit timezone-aware timestamp required") from error


def micros(value):
    delta = value - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def implementation_hashes():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (Path(__file__), Path(__file__).with_name("survivorship_contract.py"),
             Path(__file__).with_name("contracts.py"))}


def value_error(field, rule, value):
    if value is None:
        return "null"
    if isinstance(value, str) and not value.strip():
        return "blank"
    try:
        field.validate(value)
    except ContractError:
        return "invalid_type"
    if rule.allowed_values and value not in rule.allowed_values:
        return "disallowed_value"
    return None


def _records(binding, identity, records, clock):
    policy = binding.policy
    if (identity.get("domain_id"), identity.get("domain_version"), identity.get("domain_sha256")) != (
            policy.domain_id, policy.domain_version, policy.domain_sha256):
        raise ContractError("Identity snapshot domain differs")
    master_key(identity.get("master_id"))
    positive_version(identity.get("revision"))
    if identity.get("state") != "active":
        raise SurvivorshipConflict("An active identity snapshot is required")
    members = identity.get("members")
    if not isinstance(members, list) or not 1 <= len(members) <= MAX_MEMBERS:
        raise ContractError("Identity requires 1–1000 members")
    try:
        expected = {SourceRef(**m) for m in members}
    except TypeError as error:
        raise ContractError("Invalid identity member") from error
    if len(expected) != len(members):
        raise SurvivorshipConflict("Duplicate identity member")
    identity["members"] = sorted(members, key=lambda m: (m["source_id"], m["source_key"]))
    pins = {p.source_id: p for p in policy.mappings}
    fields = {f.name for f in binding.domain.fields}
    mapped = {m.source_id: {f.target for f in m.fields} for m in binding.mappings}
    seen, result = set(), []
    keys = {"source_id", "source_key", "version", "mapping_version", "mapping_sha256", "updated_at",
            "deleted", "values", "assessments"}
    for record in records:
        if not isinstance(record, dict) or set(record) != keys:
            raise ContractError("Invalid source-version keys")
        ref = SourceRef(record["source_id"], record["source_key"])
        if ref in seen:
            raise SurvivorshipConflict("Duplicate current source version; supply one explicit snapshot")
        seen.add(ref)
        pin = pins.get(ref.source_id)
        positive_version(record["version"])
        positive_version(record["mapping_version"])
        if pin is None or (record["mapping_version"], record["mapping_sha256"]) != (pin.version, pin.sha256):
            raise ContractError("Source mapping version/digest differs")
        updated = timestamp(record["updated_at"])
        if updated > clock:
            raise ContractError("Source timestamp is after evaluation time")
        record["updated_at"] = updated.isoformat()
        values, assessments = record["values"], record["assessments"]
        if type(record["deleted"]) is not bool or not isinstance(values, dict) or not isinstance(assessments, dict):
            raise ContractError("Typed deletion flag, values and assessments required")
        if set(values) - fields or set(values) - mapped[ref.source_id] or set(assessments) != set(values):
            raise ContractError("Source values/assessments must use the declared mapping fields")
        if record["deleted"] and (values or assessments):
            raise ContractError("Tombstones must have empty values and assessments")
        for assessment in assessments.values():
            if not isinstance(assessment, dict) or set(assessment) != {"quality", "verified", "reference"}:
                raise ContractError("Explicit quality, verification and assessment reference required")
            if type(assessment["quality"]) is not int or not 0 <= assessment["quality"] <= 100:
                raise ContractError("Quality must be an integer in [0,100]")
            if type(assessment["verified"]) is not bool:
                raise ContractError("Verification must be boolean")
            text_key(assessment["reference"], "Assessment reference")
        result.append(record)
    if seen != expected:
        raise SurvivorshipConflict("Incomplete or foreign source snapshot; explicit tombstones required")
    return sorted(result, key=lambda r: (r["source_id"], r["source_key"]))


def _overrides(binding, identity, decisions, clock):
    active, history, seen = {}, [], set()
    fields = {f.name: f for f in binding.domain.fields}
    rules = {f.field: f for f in binding.policy.fields}
    keys = {"decision_id", "master_id", "identity_revision", "policy_sha256", "field", "value", "state",
            "proposed_by", "approved_by", "reason", "approved_at", "expires_at"}
    for decision in decisions:
        if not isinstance(decision, dict) or set(decision) != keys:
            raise ContractError("Invalid override decision keys")
        text_key(decision["decision_id"], "Decision ID")
        if decision["decision_id"] in seen:
            raise SurvivorshipConflict("Duplicate override decision")
        seen.add(decision["decision_id"])
        if decision["master_id"] != identity["master_id"] or decision["field"] not in fields:
            raise SurvivorshipConflict("Override belongs to another master or field")
        positive_version(decision["identity_revision"])
        state = decision["state"]
        if state not in {"approved", "pending", "revoked"}:
            raise ContractError("Unknown override state")
        excluded = None if state == "approved" else state
        if state == "approved":
            for key in ("proposed_by", "approved_by", "reason"):
                text_key(decision[key], key)
            if decision["approved_by"] == decision["proposed_by"]:
                raise SurvivorshipConflict("Override approval requires an independent actor")
            approved = timestamp(decision["approved_at"])
            decision["approved_at"] = approved.isoformat()
            if approved > clock:
                raise SurvivorshipConflict("Override is approved after evaluation time")
            if decision["expires_at"] is not None:
                expires = timestamp(decision["expires_at"])
                decision["expires_at"] = expires.isoformat()
                if expires <= approved:
                    raise ContractError("Override expiry must follow approval")
                if clock >= expires:
                    excluded = "expired"
            if excluded is None:
                if (decision["identity_revision"], decision["policy_sha256"]) != (
                        identity["revision"], binding.policy.sha256):
                    raise SurvivorshipConflict("Override approval pins a stale identity revision or policy")
                name = decision["field"]
                error = value_error(fields[name], rules[name], decision["value"])
                if error and not (error == "null" and not fields[name].required):
                    raise ContractError("Invalid approved override: " + error)
                if name in active:
                    raise SurvivorshipConflict("Multiple active approved overrides for one field")
                active[name] = decision
        history.append({"decision": decision, "excluded": excluded})
    return active, sorted(history, key=lambda d: d["decision"]["decision_id"])


def calculate(binding, identity, records, *, as_of, overrides=()):
    """Calculate from a complete trusted snapshot, preserving all value evidence."""
    if not isinstance(binding, SurvivorshipBinding):
        raise ContractError("Typed survivorship binding required")
    if not isinstance(records, (list, tuple)) or not 1 <= len(records) <= MAX_MEMBERS:
        raise ContractError("Expected 1–1000 source versions")
    if not isinstance(overrides, (list, tuple)) or len(overrides) > MAX_DECISIONS:
        raise ContractError("Expected at most 200 override decisions")
    if not isinstance(identity, dict):
        raise ContractError("Explicit identity snapshot required")
    # Canonical JSON detaches caller-owned mutable data and rejects NaN/objects.
    try:
        raw = json.dumps({"identity": identity, "records": records, "overrides": overrides},
                         ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
        if len(raw.encode()) > MAX_BYTES:
            raise ContractError("Survivorship request exceeds 4 MiB")
        request = json.loads(raw)
    except (TypeError, ValueError, RecursionError) as error:
        raise ContractError("Bounded JSON source and decision snapshots required") from error
    identity = request["identity"]
    clock = timestamp(as_of)
    records = _records(binding, identity, request["records"], clock)
    record_hashes = {(r["source_id"], r["source_key"]): digest(r) for r in records}
    active, overrides = _overrides(binding, identity, request["overrides"], clock)
    fields = {f.name: f for f in binding.domain.fields}
    rules = {f.field: f for f in binding.policy.fields}
    values, explanations, issues = {}, {}, []
    if all(r["deleted"] for r in records):
        issues.append({"reason": "no_live_sources"})
    for name in sorted(fields):
        field, rule = fields[name], rules[name]
        priorities = {s.source_id: s.priority for s in rule.sources}
        alternatives, eligible = [], []
        for record in records:
            source = {k: record[k] for k in ("source_id", "source_key", "version")}
            source["sha256"] = record_hashes[(record["source_id"], record["source_key"])]
            value = record["values"].get(name)
            excluded = None
            if record["deleted"]:
                excluded = "deleted"
            elif (binding.domain.identity_granularity == "legal_company"
                  and record["values"].get("record_kind") != "legal_company"):
                excluded = "ineligible_record_kind"
            elif name not in record["values"]:
                excluded = "missing"
            else:
                excluded = value_error(field, rule, value)
            assessment = record["assessments"].get(name)
            rank = None
            if excluded is None:
                age = micros(clock) - micros(timestamp(record["updated_at"]))
                if assessment["quality"] < rule.minimum_quality:
                    excluded = "below_minimum_quality"
                elif rule.maximum_age_seconds is not None and age > rule.maximum_age_seconds * 1000000:
                    excluded = "stale"
                else:
                    rank = [not assessment["verified"], priorities[record["source_id"]], -assessment["quality"],
                            -micros(timestamp(record["updated_at"])), record["source_id"], record["source_key"]]
            candidate = {"source": source, "value": value, "assessment": assessment, "excluded": excluded, "rank": rank}
            alternatives.append(candidate)
            if rank is not None:
                eligible.append(candidate)
        eligible.sort(key=lambda c: c["rank"])
        selected, reason, value = None, "no_eligible_value", None
        if name in active:
            decision = active[name]
            value, reason = decision["value"], "approved_override"
            selected = {"decision_id": decision["decision_id"], "sha256": digest(decision)}
        elif eligible:
            winner = eligible[0]
            value, selected, reason = winner["value"], winner["source"], "only_eligible_value"
            if len(eligible) > 1:
                criteria = ["verified", "source_priority", "quality", "freshness", "source_id", "source_key"]
                reason = next(criteria[i] for i, (a, b) in enumerate(zip(winner["rank"], eligible[1]["rank"])) if a != b)
        if value is None and field.required:
            issues.append({"field": name, "reason": "required_value_unavailable"})
        values[name] = value
        explanations[name] = {"winner": selected, "reason": reason, "value_sha256": digest(value),
                              "conflicting_values": len({digest(c["value"]) for c in eligible}) > 1,
                              "alternatives": alternatives}
    for group in binding.policy.coherence_groups:
        winners = {digest(explanations[n]["winner"]) for n in group if values[n] is not None}
        if len(winners) > 1:
            issues.append({"fields": list(group), "reason": "mixed_scalar_sources"})
    inputs = {"identity": identity, "records": records, "overrides": overrides, "as_of": clock.isoformat()}
    result = {"schema_version": 1, "status": "needs_review" if issues else "calculated",
              "master_id": identity["master_id"], "identity_revision": identity["revision"],
              "binding": binding.manifest(), "implementation_sha256": implementation_hashes(),
              "input_sha256": digest(inputs), "inputs": inputs, "values": values,
              "fields": explanations, "issues": issues}
    return {**result, "result_sha256": digest(result)}
