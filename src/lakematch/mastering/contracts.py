"""Versioned scalar domain/mapping contracts for the LF-A prototype.

These are separate from engine v1 configuration. They do not allocate identities,
infer identity matches, publish golden records or approve schema changes.
"""
from dataclasses import asdict, dataclass
from datetime import date, datetime
import hashlib
import json
import math
import re


class ContractError(ValueError):
    """A schema, mapping or input value violates its declared contract."""


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value):
        raise ContractError("Contract identifiers must be lowercase names of 1–63 characters")


def positive_version(value):
    if type(value) is not int or value < 1:
        raise ContractError("Versions must be positive integers")


@dataclass(frozen=True)
class Field:
    name: str
    type: str
    required: bool = False

    def __post_init__(self):
        identifier(self.name)
        if self.type not in {"string", "string_array", "integer", "number", "boolean", "date", "timestamp"}:
            raise ContractError(f"Unsupported field type: {self.type}")
        if type(self.required) is not bool:
            raise ContractError("required must be boolean")

    def validate(self, value):
        if value is None:
            if self.required:
                raise ContractError(f"Required field {self.name} is null/missing")
            return
        valid = {
            "string": lambda: isinstance(value, str),
            "string_array": lambda: isinstance(value, list) and all(isinstance(v, str) for v in value),
            "integer": lambda: type(value) is int,
            "number": lambda: type(value) in (int, float) and math.isfinite(value),
            "boolean": lambda: type(value) is bool,
            "date": lambda: isinstance(value, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)) and bool(date.fromisoformat(value)),
            "timestamp": lambda: isinstance(value, str) and "T" in value and datetime.fromisoformat(value).utcoffset() is not None,
        }
        try:
            ok = valid[self.type]()
        except (ValueError, OverflowError):
            ok = False
        if not ok or (self.required and isinstance(value, str) and not value.strip()):
            raise ContractError(f"Invalid {self.type} value for {self.name}")


@dataclass(frozen=True)
class DomainContract:
    domain_id: str
    version: int
    identity_granularity: str
    fields: tuple[Field, ...]
    schema_version: int = 1

    def __post_init__(self):
        identifier(self.domain_id)
        positive_version(self.version)
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ContractError("Unsupported contract schema_version")
        identifier(self.identity_granularity)
        if not isinstance(self.fields, tuple) or not self.fields or not all(isinstance(f, Field) for f in self.fields):
            raise ContractError("fields must be a nonempty tuple of Field contracts")
        if len({f.name for f in self.fields}) != len(self.fields):
            raise ContractError("Duplicate domain fields")

    @classmethod
    def from_dict(cls, value):
        try:
            if "schema_version" not in value:
                raise ContractError("An explicit contract schema_version is required")
            return cls(**{**value, "fields": tuple(Field(**f) for f in value["fields"])})
        except (TypeError, KeyError) as error:
            raise ContractError("Invalid domain contract keys") from error

    @property
    def sha256(self):
        return digest(asdict(self))

    def validate_record(self, record):
        if not isinstance(record, dict) or set(record) - {f.name for f in self.fields}:
            raise ContractError("Unknown fields in canonical record")
        for field in self.fields:
            field.validate(record.get(field.name))


TRANSFORMS = {
    "strip": str.strip,
    "upper": str.upper,
    "casefold": str.casefold,
    "collapse_whitespace": lambda value: " ".join(value.split()),
}


@dataclass(frozen=True)
class FieldMapping:
    target: str
    source: str
    transforms: tuple[str, ...] = ()

    def __post_init__(self):
        identifier(self.target)
        if not isinstance(self.source, str) or not self.source:
            raise ContractError("A literal source column is required")
        if not isinstance(self.transforms, tuple) or any(t not in TRANSFORMS for t in self.transforms):
            raise ContractError("Unknown transformation; executable mapping expressions are unsupported")


@dataclass(frozen=True)
class SourceMapping:
    source_id: str
    version: int
    domain: DomainContract
    source_key: str
    source_columns: tuple[str, ...]
    fields: tuple[FieldMapping, ...]

    def __post_init__(self):
        identifier(self.source_id)
        positive_version(self.version)
        if not isinstance(self.domain, DomainContract):
            raise ContractError("A validated domain contract is required")
        if not isinstance(self.source_columns, tuple) or not self.source_columns or any(not isinstance(c, str) or not c for c in self.source_columns):
            raise ContractError("source_columns must declare nonempty literal column names")
        if len(set(self.source_columns)) != len(self.source_columns) or self.source_key not in self.source_columns:
            raise ContractError("Duplicate source columns or undeclared source key")
        if not isinstance(self.fields, tuple) or not all(isinstance(f, FieldMapping) for f in self.fields):
            raise ContractError("fields must be a tuple of FieldMapping contracts")
        targets = [f.target for f in self.fields]
        if len(set(targets)) != len(targets):
            raise ContractError("A target field can have only one source mapping")
        domain_fields = {f.name: f for f in self.domain.fields}
        if set(targets) - domain_fields.keys() or any(f.source not in self.source_columns for f in self.fields):
            raise ContractError("Unknown mapping source or target")
        if {f.name for f in self.domain.fields if f.required} - set(targets):
            raise ContractError("Required target fields need a mapping")
        if any(f.transforms and domain_fields[f.target].type != "string" for f in self.fields):
            raise ContractError("String transformations require a string target")

    @classmethod
    def from_dict(cls, value, domain):
        try:
            data = dict(value)
            if data.pop("schema_version") != 1 or type(value["schema_version"]) is not int:
                raise ContractError("Unsupported mapping schema_version")
            positive_version(data["domain_version"])
            if (data.pop("domain_id"), data.pop("domain_version"), data.pop("domain_sha256")) != (domain.domain_id, domain.version, domain.sha256):
                raise ContractError("Mapping is bound to a different domain definition")
            if not isinstance(data["source_columns"], list):
                raise ContractError("source_columns must be a list")
            data["fields"] = tuple(FieldMapping(**{**f, "transforms": tuple(f.get("transforms", ()))}) for f in data["fields"])
            data["source_columns"] = tuple(data["source_columns"])
            return cls(domain=domain, **data)
        except (TypeError, KeyError) as error:
            raise ContractError("Invalid mapping contract keys") from error

    @property
    def sha256(self):
        return digest(asdict(self))

    def apply(self, record):
        if not isinstance(record, dict) or set(record) != set(self.source_columns):
            raise ContractError("Source schema drift; review and version the mapping")
        key = record[self.source_key]
        if not isinstance(key, str) or not key.strip():
            raise ContractError("Source key must be a nonempty string; no implicit cast")
        output = {}
        for mapping in self.fields:
            value = record[mapping.source]
            if value is not None:
                for transform in mapping.transforms:
                    if not isinstance(value, str):
                        raise ContractError("String transformation received a nonstring")
                    value = TRANSFORMS[transform](value)
            output[mapping.target] = value[:] if isinstance(value, list) else value
        self.domain.validate_record(output)
        return {"domain_id": self.domain.domain_id, "domain_version": self.domain.version,
                "domain_sha256": self.domain.sha256, "source_id": self.source_id,
                "source_key": key, "mapping_version": self.version,
                "mapping_sha256": self.sha256, "payload": output,
                "payload_sha256": digest(output)}
