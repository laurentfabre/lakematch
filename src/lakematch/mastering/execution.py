"""Versioned company retrieval bindings and an explicit v1 feature-row adapter.

These are internal job services, not authentication or a publication API.
"""
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import re

from lakematch.config import from_dict
from lakematch.mastering.contracts import ContractError, DomainContract, SourceMapping, digest, identifier, positive_version
from lakematch.mastering import retrieval


def sha256_reference(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ContractError("An explicit SHA-256 contract reference is required")


def retrieval_digest():
    return hashlib.sha256(Path(retrieval.__file__).read_bytes()).hexdigest()


@dataclass(frozen=True)
class ExecutionSpec:
    execution_id: str
    version: int
    domain_id: str
    domain_version: int
    domain_sha256: str
    left_source_id: str
    left_mapping_version: int
    left_mapping_sha256: str
    right_source_id: str
    right_mapping_version: int
    right_mapping_sha256: str
    retrieval_alternative: str
    retrieval_sha256: str
    limits: retrieval.Limits
    schema_version: int = 1

    def __post_init__(self):
        for value in (self.execution_id, self.domain_id, self.left_source_id, self.right_source_id):
            identifier(value)
        for value in (self.version, self.domain_version, self.left_mapping_version, self.right_mapping_version):
            positive_version(value)
        for value in (self.domain_sha256, self.left_mapping_sha256, self.right_mapping_sha256, self.retrieval_sha256):
            sha256_reference(value)
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ContractError("Unsupported execution schema_version")
        if self.left_source_id == self.right_source_id:
            raise ContractError("Execution requires two distinct source mappings")
        if self.retrieval_alternative not in retrieval.ALTERNATIVES or not isinstance(self.limits, retrieval.Limits):
            raise ContractError("A declared candidate alternative and finite limits are required")

    @classmethod
    def from_dict(cls, value):
        try:
            if "schema_version" not in value:
                raise ContractError("An explicit execution schema_version is required")
            return cls(**{**value, "limits": retrieval.Limits(**value["limits"])})
        except (TypeError, KeyError, ValueError) as error:
            raise ContractError("Invalid execution contract") from error

    @property
    def sha256(self):
        return digest(asdict(self))


@dataclass(frozen=True)
class ExecutionBinding:
    spec: ExecutionSpec
    domain: DomainContract
    left: SourceMapping
    right: SourceMapping
    approvals: tuple[dict, ...]

    def __post_init__(self):
        s = self.spec
        if (self.domain.domain_id, self.domain.version, self.domain.sha256) != (s.domain_id, s.domain_version, s.domain_sha256):
            raise ContractError("Execution domain binding differs")
        if self.domain.identity_granularity != "legal_company":
            raise ContractError("This retrieval adapter requires legal-company granularity")
        fields = {f.name: f for f in self.domain.fields}
        if not (retrieval.FEATURES | {"record_kind"}) <= fields.keys() or any(fields[n].type != "string" for n in retrieval.FEATURES | {"record_kind"}):
            raise ContractError("Company retrieval needs the declared scalar string fields")
        for side, mapping in (("left", self.left), ("right", self.right)):
            expected = (getattr(s, side + "_source_id"), getattr(s, side + "_mapping_version"), getattr(s, side + "_mapping_sha256"))
            if (mapping.source_id, mapping.version, mapping.sha256) != expected or mapping.domain.sha256 != self.domain.sha256:
                raise ContractError("Execution mapping binding differs")
            if not (retrieval.FEATURES | {"record_kind"}) <= {f.target for f in mapping.fields}:
                raise ContractError("Every retrieval field must be explicitly mapped, even when its value is null")
        if s.retrieval_sha256 != retrieval_digest():
            raise ContractError("Retrieval implementation changed; approve a new execution version")

    def manifest(self):
        return {"schema_version": 1, "execution": asdict(self.spec), "execution_sha256": self.spec.sha256,
                "domain": asdict(self.domain), "approvals": list(self.approvals),
                "left_mapping": mapping_definition(self.left), "right_mapping": mapping_definition(self.right),
                "feature_allowlist": sorted(retrieval.FEATURES),
                "authority": "approved at registry resolution; no authentication or publication approval"}


def mapping_definition(mapping):
    return {"schema_version": 1, "source_id": mapping.source_id, "version": mapping.version,
            "domain_id": mapping.domain.domain_id, "domain_version": mapping.domain.version,
            "domain_sha256": mapping.domain.sha256, "source_key": mapping.source_key,
            "source_columns": list(mapping.source_columns), "fields": [asdict(f) for f in mapping.fields]}


def project_rows(mapping, rows):
    output, seen = [], set()
    for row in rows:
        receipt = mapping.apply(row)
        if receipt["payload"].get("record_kind") != "legal_company":
            raise ContractError("Only legal-company records are eligible; quarantine branches separately")
        if receipt["source_key"] in seen:
            raise ContractError("Duplicate source key")
        seen.add(receipt["source_key"])
        output.append({"record_id": receipt["source_key"],
                       "features": {name: receipt["payload"][name] for name in sorted(retrieval.FEATURES)}})
    return output


def preview_mapping(mapping, rows):
    """Bounded engineering preview, before source records are accepted by a job."""
    if not isinstance(rows, list) or len(rows) > 1000:
        raise ContractError("Preview requires at most 1000 explicit rows")
    import json
    if len(json.dumps(rows, ensure_ascii=False, allow_nan=False).encode()) > 1024 * 1024:
        raise ContractError("Preview exceeds 1 MiB")
    accepted, errors, seen = [], [], set()
    for index, row in enumerate(rows):
        try:
            receipt = mapping.apply(row)
            if receipt["payload"].get("record_kind") != "legal_company":
                raise ContractError("ineligible_record_kind")
            if receipt["source_key"] in seen:
                raise ContractError("duplicate_source_key")
            seen.add(receipt["source_key"])
            accepted.append(receipt)
        except ContractError as error:
            errors.append({"row_index": index, "error": str(error)})
    return {"source_id": mapping.source_id, "mapping_version": mapping.version,
            "mapping_sha256": mapping.sha256, "input_rows": len(rows), "accepted": accepted, "errors": errors}


def execute_candidates(binding, left_rows, right_rows):
    """Run only pinned candidate retrieval and emit a reproducible job receipt."""
    if max(len(left_rows), len(right_rows)) > binding.spec.limits.input_rows_per_source:
        raise ContractError("Source row bound exceeded before mapping")
    # Validate both complete inputs before retrieval: no partial success on drift.
    left, right = project_rows(binding.left, left_rows), project_rows(binding.right, right_rows)
    result = retrieval.retrieve(left, right, binding.spec.retrieval_alternative, binding.spec.limits)
    return {"binding": binding.manifest(), "input_snapshots": {
                binding.left.source_id: {"rows": len(left_rows), "sha256": digest(left_rows)},
                binding.right.source_id: {"rows": len(right_rows), "sha256": digest(right_rows)}},
            "candidate_rows_sha256": digest(result["rows"]), "result": result,
            "auto_merge": "not implemented; candidates are not identity decisions"}


def company_feature_config():
    """Construct a normal v1 config for this explicit feature-row projection only."""
    return from_dict({"entity": {"name": "company", "id_column": "rec_id", "fields": {
        "legal_name": {"type": "organisation"}, "country": {"type": "code"},
        "registration_id": {"type": "code"}, "address_line1": {"type": "address"},
        "city": {"type": "address"}, "postal_code": {"type": "code"}}}})


def legacy_feature_rows(mapping, rows, config):
    """Export v1-shaped rows without rewriting an old config or its candidate path."""
    expected = company_feature_config()["entity"]
    if config["entity"] != expected:
        raise ContractError("Explicit company v1 feature contract required; old configs are not rewritten")
    return [{"rec_id": row["record_id"], **row["features"]} for row in project_rows(mapping, rows)]
