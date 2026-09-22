"""Versioned comparison policies; no model, registry approval or merge authority."""
from dataclasses import asdict, dataclass

from .contracts import ContractError, DomainContract, SourceMapping, digest, identifier, positive_version
from .identity_contract import sha256_key
from .survivorship_contract import MappingPin

FIELDS = ("record_kind", "legal_name", "country", "registration_id", "address_line1", "city", "postal_code")
METHODS = frozenset({"identifier", "name", "tokens", "trigrams"})
ALGORITHM = "company_pair_evidence_v2"
NORMALIZATION = "unicode_company_comparison_v1"
# Fixed precedence is part of the algorithm, not caller-controlled code.
PRECEDENCE = ("deleted_source", "same_source_record", "ineligible_granularity", "incomplete_identity",
              "different_jurisdictions", "identifier_conflict", "same_source_duplicate",
              "identifier_agreement", "name_agreement", "insufficient_evidence")


@dataclass(frozen=True)
class MatchRuleset:
    ruleset_id: str
    version: int
    domain_id: str
    domain_version: int
    domain_sha256: str
    mappings: tuple[MappingPin, ...]
    implementation_sha256: str
    algorithm: str = ALGORITHM
    normalization: str = NORMALIZATION
    precedence: tuple[str, ...] = PRECEDENCE
    schema_version: int = 1

    def __post_init__(self):
        identifier(self.ruleset_id)
        identifier(self.domain_id)
        positive_version(self.version)
        positive_version(self.domain_version)
        sha256_key(self.domain_sha256)
        sha256_key(self.implementation_sha256)
        if (type(self.schema_version) is not int or self.schema_version != 1 or self.algorithm != ALGORITHM
                or self.normalization != NORMALIZATION or self.precedence != PRECEDENCE):
            raise ContractError("Unsupported comparison schema, normalization or precedence")
        if (not isinstance(self.mappings, tuple) or not 1 <= len(self.mappings) <= 10
                or any(not isinstance(m, MappingPin) for m in self.mappings)
                or len({m.source_id for m in self.mappings}) != len(self.mappings)):
            raise ContractError("Ruleset requires 1–10 unique mapping pins")

    @classmethod
    def from_dict(cls, value):
        try:
            if "schema_version" not in value:
                raise ContractError("Explicit comparison schema_version required")
            return cls(**{**value, "mappings": tuple(MappingPin(**m) for m in value["mappings"]),
                          "precedence": tuple(value.get("precedence", PRECEDENCE))})
        except (TypeError, KeyError) as error:
            raise ContractError("Invalid comparison ruleset keys") from error

    @property
    def sha256(self):
        return digest(asdict(self))


@dataclass(frozen=True)
class MatchBinding:
    ruleset: MatchRuleset
    domain: DomainContract
    mappings: tuple[SourceMapping, ...]

    def __post_init__(self):
        if not isinstance(self.ruleset, MatchRuleset) or not isinstance(self.domain, DomainContract):
            raise ContractError("Typed comparison ruleset and domain required")
        r, d = self.ruleset, self.domain
        if (r.domain_id, r.domain_version, r.domain_sha256) != (d.domain_id, d.version, d.sha256):
            raise ContractError("Comparison domain binding differs")
        fields = {f.name: f for f in d.fields}
        if (d.identity_granularity != "legal_company" or not set(FIELDS) <= fields.keys()
                or any(fields[n].type != "string" for n in FIELDS)):
            raise ContractError("Comparison requires legal-company scalar string fields")
        if (not isinstance(self.mappings, tuple) or any(not isinstance(m, SourceMapping) for m in self.mappings)
                or len(self.mappings) != len(r.mappings)
                or {MappingPin(m.source_id, m.version, m.sha256) for m in self.mappings} != set(r.mappings)):
            raise ContractError("Comparison mapping binding differs")
        if any(m.domain.sha256 != d.sha256 or not set(FIELDS) <= {f.target for f in m.fields} for m in self.mappings):
            raise ContractError("Every comparison field requires an explicit domain mapping")
        self.check_implementation()

    def check_implementation(self):
        from .match_evidence import implementation_digest
        if self.ruleset.implementation_sha256 != implementation_digest():
            raise ContractError("Comparison implementation changed; issue a new ruleset version")

    def manifest(self):
        # Serialized definitions are detached from the immutable contract objects.
        import json
        return json.loads(json.dumps({"ruleset": asdict(self.ruleset), "ruleset_sha256": self.ruleset.sha256,
                                      "domain": asdict(self.domain), "authority": "unapproved_worker_preview"}))
