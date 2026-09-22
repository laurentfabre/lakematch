"""Portable, immutable scalar policy definitions. No database or Spark imports."""
from dataclasses import asdict, dataclass

from .contracts import ContractError, DomainContract, SourceMapping, digest, identifier, positive_version
from .identity_contract import sha256_key

ALGORITHM = "scalar_survivorship_v1"
MAX_FIELDS = 100
MAX_DECISIONS = 200
MAX_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class MappingPin:
    source_id: str
    version: int
    sha256: str

    def __post_init__(self):
        identifier(self.source_id)
        positive_version(self.version)
        sha256_key(self.sha256)


@dataclass(frozen=True)
class SourcePriority:
    source_id: str
    priority: int

    def __post_init__(self):
        identifier(self.source_id)
        if type(self.priority) is not int or not 0 <= self.priority <= 1000:
            raise ContractError("Source priority must be an integer in [0,1000]")


@dataclass(frozen=True)
class FieldRule:
    field: str
    sources: tuple[SourcePriority, ...]
    minimum_quality: int = 0
    maximum_age_seconds: int | None = None
    allowed_values: tuple[str, ...] = ()

    def __post_init__(self):
        identifier(self.field)
        if (not isinstance(self.sources, tuple) or not self.sources
                or not all(isinstance(s, SourcePriority) for s in self.sources)
                or len({s.source_id for s in self.sources}) != len(self.sources)):
            raise ContractError("Field rule requires unique source priorities")
        if type(self.minimum_quality) is not int or not 0 <= self.minimum_quality <= 100:
            raise ContractError("Minimum quality must be an integer in [0,100]")
        if self.maximum_age_seconds is not None and (
                type(self.maximum_age_seconds) is not int or not 0 <= self.maximum_age_seconds <= 315576000):
            raise ContractError("Maximum age must be seconds in [0,315576000] or null")
        if (not isinstance(self.allowed_values, tuple)
                or any(not isinstance(v, str) or not v.strip() for v in self.allowed_values)
                or len(set(self.allowed_values)) != len(self.allowed_values)):
            raise ContractError("Allowed values must be unique nonblank strings")


@dataclass(frozen=True)
class SurvivorshipPolicy:
    policy_id: str
    version: int
    domain_id: str
    domain_version: int
    domain_sha256: str
    mappings: tuple[MappingPin, ...]
    fields: tuple[FieldRule, ...]
    coherence_groups: tuple[tuple[str, ...], ...] = ()
    algorithm: str = ALGORITHM
    schema_version: int = 1

    def __post_init__(self):
        identifier(self.policy_id)
        identifier(self.domain_id)
        positive_version(self.version)
        positive_version(self.domain_version)
        sha256_key(self.domain_sha256)
        if self.algorithm != ALGORITHM or type(self.schema_version) is not int or self.schema_version != 1:
            raise ContractError("Unsupported survivorship algorithm/schema")
        if (not isinstance(self.mappings, tuple) or not 1 <= len(self.mappings) <= 100
                or not all(isinstance(m, MappingPin) for m in self.mappings)
                or len({m.source_id for m in self.mappings}) != len(self.mappings)):
            raise ContractError("Policy requires 1–100 unique mapping pins")
        if (not isinstance(self.fields, tuple) or not 1 <= len(self.fields) <= MAX_FIELDS
                or not all(isinstance(f, FieldRule) for f in self.fields)
                or len({f.field for f in self.fields}) != len(self.fields)):
            raise ContractError("Policy requires 1–100 unique field rules")
        sources = {m.source_id for m in self.mappings}
        if any({s.source_id for s in f.sources} != sources for f in self.fields):
            raise ContractError("Every field must explicitly rank every pinned source")
        names = {f.field for f in self.fields}
        if (not isinstance(self.coherence_groups, tuple) or len(self.coherence_groups) > MAX_FIELDS
                or any(not isinstance(g, tuple) or not 2 <= len(g) <= MAX_FIELDS
                       or any(not isinstance(n, str) for n in g)
                       or len(set(g)) != len(g) or not set(g) <= names for g in self.coherence_groups)):
            raise ContractError("Invalid scalar coherence groups")

    @classmethod
    def from_dict(cls, value):
        try:
            if "schema_version" not in value:
                raise ContractError("Explicit policy schema_version required")
            return cls(**{**value,
                "mappings": tuple(MappingPin(**m) for m in value["mappings"]),
                "fields": tuple(FieldRule(**{**f, "sources": tuple(SourcePriority(**s) for s in f["sources"]),
                                               "allowed_values": tuple(f.get("allowed_values", ()))}) for f in value["fields"]),
                "coherence_groups": tuple(tuple(g) for g in value.get("coherence_groups", ()))})
        except (TypeError, KeyError) as error:
            raise ContractError("Invalid survivorship policy keys") from error

    @property
    def sha256(self):
        return digest(asdict(self))


@dataclass(frozen=True)
class SurvivorshipBinding:
    policy: SurvivorshipPolicy
    domain: DomainContract
    mappings: tuple[SourceMapping, ...]
    approvals: tuple[dict, ...] = ()

    def __post_init__(self):
        p, d = self.policy, self.domain
        if (p.domain_id, p.domain_version, p.domain_sha256) != (d.domain_id, d.version, d.sha256):
            raise ContractError("Survivorship domain binding differs")
        if {f.field for f in p.fields} != {f.name for f in d.fields}:
            raise ContractError("Every domain field needs exactly one rule")
        if any(f.type == "string_array" for f in d.fields):
            raise ContractError("Scalar survivorship does not support arrays")
        if {MappingPin(m.source_id, m.version, m.sha256) for m in self.mappings} != set(p.mappings):
            raise ContractError("Survivorship mapping binding differs")
        if len(self.mappings) != len(p.mappings) or any(m.domain.sha256 != d.sha256 for m in self.mappings):
            raise ContractError("Duplicate or incompatible mapping binding")
        types = {f.name: f.type for f in d.fields}
        if any(f.allowed_values and types[f.field] != "string" for f in p.fields):
            raise ContractError("Allowed values require a string field")
        if d.identity_granularity == "legal_company":
            kinds = [f for f in p.fields if f.field == "record_kind"]
            if len(kinds) != 1 or kinds[0].allowed_values != ("legal_company",):
                raise ContractError("Company policy must enforce legal-company record kind")

    def manifest(self):
        # Return a detached snapshot; worker inputs must not mutate approvals.
        import json
        return json.loads(json.dumps({"policy": asdict(self.policy), "policy_sha256": self.policy.sha256,
                                      "domain": asdict(self.domain), "approvals": self.approvals}))
