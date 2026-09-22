"""Portable, bounded golden-record snapshots and historical field explanations."""
from dataclasses import asdict
import json

from .contracts import ContractError, DomainContract, SourceMapping, digest, identifier, positive_version
from .identity_contract import master_key, sha256_key, text_key
from .survivorship import calculate, timestamp
from .survivorship_contract import SurvivorshipBinding, SurvivorshipPolicy

MAX_MASTERS = 100
MAX_SOURCES = 2000
MAX_ATTRIBUTES = 10000
MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024
TABLES = ("golden_records", "attribute_lineage", "source_versions", "memberships", "contracts")


class LineageConflict(ValueError):
    """Snapshot content, previous head or source/identity history conflicts."""


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def detached(value):
    try:
        raw = encode(value)
        if len(raw.encode()) > MAX_SNAPSHOT_BYTES:
            raise ContractError("Snapshot exceeds 32 MiB")
        return json.loads(raw)
    except (TypeError, ValueError, RecursionError) as error:
        raise ContractError("Bounded JSON snapshot required") from error


def _context(context):
    if not isinstance(context, dict) or set(context) != {"membership_basis", "ruleset", "configuration", "model"}:
        raise ContractError("Explicit membership, ruleset, configuration and model references required")
    if context["membership_basis"] not in {"synthetic_fixture_truth", "approved_identity_commands"}:
        raise ContractError("Unknown membership basis")
    for name in ("ruleset", "configuration", "model"):
        ref = context[name]
        if ref is None and name == "model":
            continue
        keys = {"uri", "version", "sha256"} if name == "model" else {"id", "version", "sha256"}
        if not isinstance(ref, dict) or set(ref) != keys:
            raise ContractError("Immutable context references required")
        text_key(ref["uri"], "Model URI", 2048) if name == "model" else identifier(ref["id"])
        positive_version(ref["version"])
        sha256_key(ref["sha256"])


def _entry(entry, *, replay):
    if not isinstance(entry, dict) or set(entry) != {"calculation", "mappings"}:
        raise ContractError("Calculation and exact mapping definitions required")
    c = entry["calculation"]
    if not isinstance(c, dict) or c.get("schema_version") != 1:
        raise ContractError("Unsupported scalar calculation")
    if c.get("result_sha256") != digest({k: v for k, v in c.items() if k != "result_sha256"}):
        raise LineageConflict("Calculation checksum differs")
    if c.get("status") != "calculated" or c.get("issues"):
        raise LineageConflict("Review-required calculations cannot be published")
    try:
        domain = DomainContract.from_dict(c["binding"]["domain"])
        policy = SurvivorshipPolicy.from_dict(c["binding"]["policy"])
        mappings = tuple(SourceMapping.from_dict(m, domain) for m in entry["mappings"])
        approvals = c["binding"]["approvals"]
        binding = SurvivorshipBinding(policy, domain, mappings, tuple(approvals))
        if c["binding"]["policy_sha256"] != policy.sha256:
            raise LineageConflict("Policy checksum differs")
        required = {("domain", domain.domain_id, domain.version): domain.sha256,
                    ("survivorship", policy.policy_id, policy.version): policy.sha256,
                    **{("mapping", m.source_id, m.version): m.sha256 for m in mappings}}
        seen = set()
        for receipt in approvals:
            key = (receipt["kind"], receipt["object_id"], receipt["version"])
            if (key not in required or key in seen or receipt["domain_id"] != domain.domain_id
                    or receipt["state"] != "approved" or receipt["definition_sha256"] != required[key]):
                raise LineageConflict("Incomplete or inconsistent approval binding")
            positive_version(receipt["revision"])
            for name in ("created_by", "approved_by", "approval_reason"):
                text_key(receipt[name], name)
            if receipt["created_by"] == receipt["approved_by"]:
                raise LineageConflict("Independent approval required")
            timestamp(receipt["approved_at"])
            seen.add(key)
        if seen != set(required):
            raise LineageConflict("Complete approved policy/domain/mappings required")
        master_key(c["master_id"])
        positive_version(c["identity_revision"])
        inputs = c["inputs"]
        if digest(inputs) != c["input_sha256"]:
            raise LineageConflict("Input checksum differs")
        if (inputs["identity"]["master_id"], inputs["identity"]["revision"]) != (c["master_id"], c["identity_revision"]):
            raise LineageConflict("Identity receipt differs")
        if set(c["values"]) != {f.name for f in domain.fields} or set(c["fields"]) != set(c["values"]):
            raise LineageConflict("Complete field explanations required")
        for name, value in c["values"].items():
            if digest(value) != c["fields"][name]["value_sha256"]:
                raise LineageConflict("Field value checksum differs")
        if replay:
            actual = calculate(binding, inputs["identity"], inputs["records"], as_of=inputs["as_of"],
                               overrides=[d["decision"] for d in inputs["overrides"]])
            if actual != c:
                raise LineageConflict("Calculation does not replay with its pinned inputs/implementation")
    except (KeyError, TypeError) as error:
        raise ContractError("Incomplete calculation evidence") from error
    entry["mappings"] = sorted(entry["mappings"], key=lambda m: m["source_id"])
    return domain.domain_id


def _project(publication_id, entries, context, revisions):
    tables = {name: [] for name in TABLES}
    contracts, sources, owners = {}, {}, {}
    for entry in sorted(entries, key=lambda e: e["calculation"]["master_id"]):
        c = entry["calculation"]
        master_id, revision = c["master_id"], revisions[c["master_id"]]
        domain_id = c["binding"]["domain"]["domain_id"]
        common = {"publication_id": publication_id, "domain_id": domain_id}
        contract = {"binding": c["binding"], "mappings": entry["mappings"], "matching_context": context}
        contract_hash = digest(contract)
        contracts[contract_hash] = {**common, "contract_sha256": contract_hash, "definition_json": encode(contract)}
        tables["golden_records"].append({**common, "master_id": master_id, "revision": revision,
            "identity_revision": c["identity_revision"], "contract_sha256": contract_hash,
            "calculation_sha256": c["result_sha256"], "values_json": encode(c["values"]),
            "calculation_json": encode(c)})
        policy = c["binding"]["policy"]
        for name, evidence in sorted(c["fields"].items()):
            tables["attribute_lineage"].append({**common, "master_id": master_id, "revision": revision,
                "field_path": name, "value_json": encode(c["values"][name]), "value_sha256": evidence["value_sha256"],
                "reason": evidence["reason"], "winner_json": encode(evidence["winner"]),
                "alternatives_json": encode(evidence["alternatives"]), "policy_id": policy["policy_id"],
                "policy_version": policy["version"], "policy_sha256": c["binding"]["policy_sha256"],
                "contract_sha256": contract_hash})
        for source in sorted(c["inputs"]["records"], key=lambda r: (r["source_id"], r["source_key"])):
            ref = (source["source_id"], source["source_key"])
            if ref in owners:
                raise LineageConflict("A source reference belongs to multiple masters")
            owners[ref] = master_id
            source_hash = digest(source)
            sources[ref] = {**common, "source_id": ref[0], "source_key": ref[1], "source_version": source["version"],
                "source_sha256": source_hash, "mapping_version": source["mapping_version"],
                "mapping_sha256": source["mapping_sha256"], "deleted": source["deleted"], "source_json": encode(source)}
            tables["memberships"].append({**common, "master_id": master_id, "identity_revision": c["identity_revision"],
                "source_id": ref[0], "source_key": ref[1], "source_version": source["version"],
                "source_sha256": source_hash, "deleted": source["deleted"]})
    tables["contracts"] = [contracts[key] for key in sorted(contracts)]
    tables["source_versions"] = [sources[key] for key in sorted(sources)]
    if len(sources) > MAX_SOURCES or len(tables["attribute_lineage"]) > MAX_ATTRIBUTES:
        raise ContractError("Snapshot exceeds source/attribute row bounds")
    return tables


def prepare_entries(entries, context, *, replay=True):
    if not isinstance(entries, (list, tuple)) or not 1 <= len(entries) <= MAX_MASTERS:
        raise ContractError("Expected 1–100 master calculations")
    entries, context = detached(entries), detached(context)
    _context(context)
    domains = {_entry(e, replay=replay) for e in entries}
    ids = [e["calculation"]["master_id"] for e in entries]
    if len(domains) != 1 or len(set(ids)) != len(ids):
        raise LineageConflict("One domain and unique masters required")
    return sorted(entries, key=lambda e: e["calculation"]["master_id"]), context


def request_sha256(publication_id, expected_previous, entries, context):
    text_key(publication_id, "Publication ID", 200)
    if expected_previous is not None:
        text_key(expected_previous, "Previous publication ID", 200)
    return digest({"publication_id": publication_id, "expected_previous": expected_previous,
                   "entries": entries, "matching_context": context, "snapshot_schema": 1})


def build_snapshot(publication_id, entries, context, *, expected_previous, previous=None):
    entries, context = prepare_entries(entries, context)
    request_sha256(publication_id, expected_previous, entries, context)
    domain_id = entries[0]["calculation"]["binding"]["domain"]["domain_id"]
    old = {}
    if previous is not None:
        verify_snapshot(previous)
        if previous["domain_id"] != domain_id:
            raise LineageConflict("Publication namespace belongs to another domain")
        old = {r["master_id"]: r for r in previous["tables"]["golden_records"]}
    if (previous["publication_id"] if previous else None) != expected_previous:
        raise LineageConflict("Stale expected previous publication")
    if set(old) - {e["calculation"]["master_id"] for e in entries}:
        raise LineageConflict("Master removal requires explicit retirement publication support")
    revisions = {}
    for entry in entries:
        c = entry["calculation"]
        prior = old.get(c["master_id"])
        revisions[c["master_id"]] = 1
        if prior:
            old_c = json.loads(prior["calculation_json"])
            if c["identity_revision"] < prior["identity_revision"] or timestamp(c["inputs"]["as_of"]) < timestamp(old_c["inputs"]["as_of"]):
                raise LineageConflict("Identity revision or evaluation time moved backward")
            if c["identity_revision"] == prior["identity_revision"] and c["inputs"]["identity"]["members"] != old_c["inputs"]["identity"]["members"]:
                raise LineageConflict("Membership changed without an identity revision")
            contract = {"binding": c["binding"], "mappings": entry["mappings"], "matching_context": context}
            unchanged = c["result_sha256"] == prior["calculation_sha256"] and digest(contract) == prior["contract_sha256"]
            revisions[c["master_id"]] = prior["revision"] + int(not unchanged)
    tables = _project(publication_id, entries, context, revisions)
    if previous:
        heads = {(r["source_id"], r["source_key"]): r for r in previous["tables"]["source_versions"]}
        for record in tables["source_versions"]:
            prior = heads.get((record["source_id"], record["source_key"]))
            if prior and (record["source_version"] < prior["source_version"] or (
                    record["source_version"] == prior["source_version"] and record["source_sha256"] != prior["source_sha256"])):
                raise LineageConflict("Source version rollback or changed content under the same version")
    body = {"schema_version": 1, "publication_id": publication_id, "previous_publication_id": expected_previous,
            "domain_id": domain_id, "matching_context": context, "tables": tables,
            "table_sha256": {name: digest(rows) for name, rows in tables.items()},
            "counts": {name: len(rows) for name, rows in tables.items()}}
    return detached({**body, "snapshot_sha256": digest(body)})


def verify_snapshot(snapshot):
    """Read-only integrity checks. Never recalculate history with current rules."""
    s = detached(snapshot)
    try:
        if s["schema_version"] != 1 or set(s["tables"]) != set(TABLES):
            raise ContractError("Unsupported provenance snapshot")
        if s["snapshot_sha256"] != digest({k: v for k, v in s.items() if k != "snapshot_sha256"}):
            raise LineageConflict("Snapshot checksum differs")
        if s["counts"] != {n: len(r) for n, r in s["tables"].items()} or s["table_sha256"] != {n: digest(r) for n, r in s["tables"].items()}:
            raise LineageConflict("Table count/checksum differs")
        contracts = {r["contract_sha256"]: json.loads(r["definition_json"]) for r in s["tables"]["contracts"]}
        entries, revisions = [], {}
        for row in s["tables"]["golden_records"]:
            positive_version(row["revision"])
            c = json.loads(row["calculation_json"])
            contract = contracts[row["contract_sha256"]]
            if digest(contract) != row["contract_sha256"] or contract["matching_context"] != s["matching_context"]:
                raise LineageConflict("Contract content differs")
            entries.append({"calculation": c, "mappings": contract["mappings"]})
            revisions[c["master_id"]] = row["revision"]
        entries, context = prepare_entries(entries, s["matching_context"], replay=False)
        if entries[0]["calculation"]["binding"]["domain"]["domain_id"] != s["domain_id"]:
            raise LineageConflict("Domain differs")
        if _project(s["publication_id"], entries, context, revisions) != s["tables"]:
            raise LineageConflict("Stored field/source/contract projections differ")
    except (KeyError, TypeError) as error:
        raise ContractError("Incomplete provenance snapshot") from error
    return s


def entity_detail(snapshot, master_id):
    """Bounded internal detail, pinned to a single verified publication."""
    master_key(master_id)
    s = verify_snapshot(snapshot)
    master = next((r for r in s["tables"]["golden_records"] if r["master_id"] == master_id), None)
    if master is None:
        return None
    c = json.loads(master["calculation_json"])
    contract = next(json.loads(r["definition_json"]) for r in s["tables"]["contracts"] if r["contract_sha256"] == master["contract_sha256"])
    return {"publication_id": s["publication_id"], "master_id": master_id, "revision": master["revision"],
            "identity_revision": master["identity_revision"], "values": json.loads(master["values_json"]),
            "fields": c["fields"], "sources": c["inputs"]["records"], "overrides": c["inputs"]["overrides"],
            "contract": contract}
