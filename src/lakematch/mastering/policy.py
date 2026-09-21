"""Default-deny policy prototype; grants must come from a trusted server store.

This is a policy decision function, not authentication, token validation, RLS or
an API integration. Callers must enforce its result on every accessed object.
"""
from dataclasses import dataclass


READ = frozenset({"entity.read", "provenance.read", "task.read", "graph.read", "catalog.read"})
ROLE_ACTIONS = {
    "viewer": READ,
    "steward": READ | {"task.claim", "decision.propose", "product.edit"},
    "approver": READ | {"decision.approve", "catalog.approve"},
    "engineer": READ | {"domain.configure", "source.map", "run.execute"},
    "administrator": READ | {"task.claim", "decision.propose", "product.edit", "decision.approve",
                              "catalog.approve", "domain.configure", "source.map", "run.execute", "access.manage"},
}


@dataclass(frozen=True)
class Grant:
    principal: str
    domain_id: str
    role: str
    fields: frozenset[str] | None = None
    object_ids: frozenset[str] | None = None

    def __post_init__(self):
        if not self.principal or not self.domain_id or self.role not in ROLE_ACTIONS:
            raise ValueError("A principal, domain and known role are required")
        if any(x is not None and (not isinstance(x, frozenset) or any(not isinstance(v, str) or not v for v in x))
               for x in (self.fields, self.object_ids)):
            raise ValueError("Optional field/object scopes must be frozensets of names")


def permits(principal, grants, *, domain_id, action, fields=None, object_id=None, proposed_by=None):
    """Authorize a concrete action and projection, with independent approval."""
    if not principal or not domain_id:
        return False
    if fields is not None and not isinstance(fields, frozenset):
        return False
    if action in {"decision.approve", "catalog.approve"} and (not proposed_by or principal == proposed_by):
        return False
    if action in READ and (not isinstance(fields, frozenset) or not fields):
        return False
    for grant in grants:
        if grant.principal != principal or grant.domain_id != domain_id:
            continue
        if action not in ROLE_ACTIONS.get(grant.role, ()):
            continue
        if grant.object_ids is not None and object_id not in grant.object_ids:
            continue
        if grant.fields is not None and (fields is None or not fields <= grant.fields):
            continue
        return True
    return False
