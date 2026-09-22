"""Portable identity command contracts; no Spark or PostgreSQL import required."""
from dataclasses import asdict, dataclass
import json
import re
from uuid import UUID

from .contracts import ContractError, identifier, positive_version

PERSISTENT_POLICY = "persistent_uuid_v1"
LEGACY_POLICY = "spark_min_member_sha256_v1"
MAX_MEMBERS = 1000
MAX_ALIASES = 1000
MAX_PARTICIPANTS = 32
MAX_REDIRECTS = 64
MAX_REQUEST_BYTES = 1024 * 1024


class IdentityConflict(ValueError):
    """The request conflicts with an existing binding, receipt or revision."""


class IdentityUnavailable(ValueError):
    """A required identity, domain approval or legacy alias is unavailable."""


def text_key(value, label, maximum=512):
    if (not isinstance(value, str) or not value.strip() or value != value.strip()
            or "\x00" in value or len(value.encode("utf-8")) > maximum):
        raise ContractError(f"{label} must be nonblank, trimmed text of at most {maximum} UTF-8 bytes")


def sha256_key(value):
    if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
        raise ContractError("A lowercase SHA-256 identifier is required")


def master_key(value):
    if not isinstance(value, str):
        raise ContractError("A canonical UUID string is required")
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except ValueError as error:
        raise ContractError("A canonical UUID string is required") from error
    return value


@dataclass(frozen=True, order=True)
class SourceRef:
    source_id: str
    source_key: str

    def __post_init__(self):
        identifier(self.source_id)
        text_key(self.source_key, "Source key", 2048)


@dataclass(frozen=True, order=True)
class LegacyAlias:
    namespace: str
    old_id: str
    policy_version: str = LEGACY_POLICY

    def __post_init__(self):
        text_key(self.namespace, "Legacy namespace", 1024)
        sha256_key(self.old_id)
        if self.policy_version != LEGACY_POLICY:
            raise ContractError("Unsupported legacy identity policy")


@dataclass(frozen=True)
class IdentityContext:
    domain_id: str
    domain_version: int
    domain_sha256: str
    policy_version: str = PERSISTENT_POLICY

    def __post_init__(self):
        identifier(self.domain_id)
        positive_version(self.domain_version)
        sha256_key(self.domain_sha256)
        if self.policy_version != PERSISTENT_POLICY:
            raise ContractError("Unsupported persistent identity policy")


def references(values, cls, *, allow_empty=False):
    maximum = MAX_MEMBERS if cls is SourceRef else MAX_ALIASES
    if not isinstance(values, (list, tuple)) or not (0 if allow_empty else 1) <= len(values) <= maximum:
        raise ContractError(f"Expected {'0' if allow_empty else '1'}–{maximum} {cls.__name__} values")
    if not all(isinstance(v, cls) for v in values) or len(set(values)) != len(values):
        raise ContractError(f"Expected unique typed {cls.__name__} values")
    return [asdict(v) for v in sorted(values)]


def revisions(values, *, minimum=1):
    if not isinstance(values, dict) or not minimum <= len(values) <= MAX_PARTICIPANTS:
        raise ContractError("An expected-revision map with a bounded participant count is required")
    for key, version in values.items():
        master_key(key)
        positive_version(version)
    return dict(sorted(values.items()))


def command_payload(context, kind, payload, actor, reason):
    text_key(actor, "Actor")
    text_key(reason, "Reason", 4096)
    request = {"context": asdict(context), "kind": kind, "payload": payload, "actor": actor, "reason": reason}
    if len(json.dumps(request, ensure_ascii=False, allow_nan=False).encode()) > MAX_REQUEST_BYTES:
        raise ContractError("Identity command exceeds 1 MiB")
    return request
