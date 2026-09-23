"""Versioned access grants for the workflow boundary; no platform credentials."""
from dataclasses import dataclass

from .contracts import ContractError, identifier
from .identity_contract import master_key, text_key
from .policy import Grant, ROLE_ACTIONS, permits
from .workflow_contract import bounded_object

POLICY = 'workflow_access_v1'
MAX_GRANTS = 16
MAX_OBJECTS = 1024


class AccessDenied(ValueError):
    """The current server-owned grants do not permit the action/projection."""


class AccessUnavailable(ValueError):
    """Access policy is absent or its immutable audit binding is damaged."""


class HiddenObject(ValueError):
    """Object absent or outside the caller's permitted scope."""


def grant_set(principal, domain_id, values):
    text_key(principal, 'Principal')
    identifier(domain_id)
    if not isinstance(values, (list, tuple)) or len(values) > MAX_GRANTS:
        raise ContractError('At most 16 explicit grants are supported')
    result = []
    for value in values:
        if not isinstance(value, dict) or set(value) != {'role', 'fields', 'object_ids'}:
            raise ContractError('Grant requires exactly role, fields and object_ids')
        role = value['role']
        if not isinstance(role, str) or role not in ROLE_ACTIONS:
            raise ContractError('Unknown business role')
        fields, objects = value['fields'], value['object_ids']
        for items, maximum, validate in ((fields, 128, identifier), (objects, MAX_OBJECTS, master_key)):
            if items is not None:
                if not isinstance(items, list) or not 1 <= len(items) <= maximum:
                    raise ContractError('A scope must be null or a bounded nonempty list')
                for item in items:
                    validate(item)
                if len(set(items)) != len(items):
                    raise ContractError('Scope entries must be unique')
        result.append({'role': role, 'fields': sorted(fields) if fields is not None else None,
                       'object_ids': sorted(objects) if objects is not None else None})
    # Grant order is semantic-free; exact duplicate grants are rejected.
    from .contracts import digest
    result.sort(key=digest)
    if len({digest(g) for g in result}) != len(result):
        raise ContractError('Duplicate grants are unsupported')
    return bounded_object({'policy_version': POLICY, 'principal': principal,
                           'domain_id': domain_id, 'grants': result}, maximum=262144)


@dataclass(frozen=True)
class AccessSnapshot:
    principal: str
    domain_id: str
    revision: int
    definition_sha256: str
    grants: tuple[Grant, ...]

    def require_action(self, action):
        if not any(action in ROLE_ACTIONS[g.role] for g in self.grants):
            raise AccessDenied('Action is not permitted')

    def permits(self, action, fields, object_id, *, proposed_by=None):
        return permits(self.principal, self.grants, domain_id=self.domain_id, action=action,
                       fields=fields, object_id=object_id, proposed_by=proposed_by)

    def readable_objects(self, fields):
        """Union complete field/object grants, never union fragmented fields."""
        eligible = [g for g in self.grants if 'task.read' in ROLE_ACTIONS[g.role]
                    and (g.fields is None or fields <= g.fields)]
        if not eligible:
            raise AccessDenied('Full workflow field access is required')
        if any(g.object_ids is None for g in eligible):
            return None
        objects = frozenset().union(*(g.object_ids for g in eligible))
        if len(objects) > MAX_OBJECTS:
            raise AccessDenied('Combined object scope exceeds the bounded access policy')
        return sorted(objects)
