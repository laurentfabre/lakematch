"""Bounded stewardship intent contracts; no authentication or business execution."""
from dataclasses import asdict, dataclass
import json
import math

from .contracts import ContractError, identifier
from .identity_contract import SourceRef, master_key, references, sha256_key, text_key

POLICY = 'steward_workflow_v1'
KINDS = frozenset({'merge', 'override', 'split_new', 'restore_merge'})
MAX_ENTITIES = 32
MAX_LEASE_SECONDS = 900
MAX_PAGE = 100


class WorkflowConflict(ValueError):
    """A command key, revision, lease or state conflicts with current state."""


class WorkflowUnavailable(ValueError):
    """The object or its bound domain is absent, legacy or unavailable."""


def revision(value):
    if type(value) is not int or not 1 <= value < 2**63-1:
        raise ContractError('A positive bounded revision is required')
    return value


@dataclass(frozen=True)
class WorkflowContext:
    domain_id: str
    domain_version: int
    domain_sha256: str
    policy_version: str = POLICY

    def __post_init__(self):
        identifier(self.domain_id)
        revision(self.domain_version)
        if self.domain_version >= 2**31:
            raise ContractError('Domain version exceeds the PostgreSQL integer bound')
        sha256_key(self.domain_sha256)
        if self.policy_version != POLICY:
            raise ContractError('Unsupported workflow policy')


def bounded_object(value, *, maximum=32768):
    """Detach JSON while rejecting non-string keys, nonfinite values and deep trees."""
    if not isinstance(value, dict):
        raise ContractError('An explicit JSON object is required')
    nodes = 0
    def visit(item, depth):
        nonlocal nodes
        nodes += 1
        if depth > 8 or nodes > 4096:
            raise ContractError('JSON structure exceeds the depth/node envelope')
        if isinstance(item, dict):
            for k,v in item.items():
                if not isinstance(k,str) or '\x00' in k:
                    raise ContractError('JSON keys must be strings without null bytes')
                visit(v,depth+1)
        elif isinstance(item,list):
            for v in item: visit(v,depth+1)
        elif type(item) not in (str,int,float,bool,type(None)):
            raise ContractError('Only JSON scalar values are supported')
        elif isinstance(item,str) and '\x00' in item:
            raise ContractError('Null bytes are not supported')
        elif isinstance(item,float) and not math.isfinite(item):
            raise ContractError('Nonfinite JSON numbers are unsupported')
    try:
        visit(value,0)
        raw=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
        if len(raw.encode()) > maximum:
            raise ContractError(f'JSON object exceeds {maximum} bytes')
        return json.loads(raw)
    except (TypeError, ValueError, RecursionError, UnicodeError) as error:
        if isinstance(error,ContractError): raise
        raise ContractError('Bounded valid JSON required') from error


def entities(kind, values):
    if not isinstance(kind,str) or kind not in KINDS:
        raise ContractError('Unsupported stewardship intent kind')
    minimum,maximum=(2,MAX_ENTITIES) if kind in {'merge','restore_merge'} else (1,1)
    if not isinstance(values,(list,tuple)) or not minimum <= len(values) <= maximum:
        raise ContractError('Intent requires the declared bounded entity count')
    for value in values: master_key(value)
    if len(set(values))!=len(values):
        raise ContractError('Entity IDs must be unique')
    return sorted(values)


def expected_versions(kind, values):
    if not isinstance(values,dict):
        raise ContractError('An explicit expected-version map is required')
    ids=entities(kind,list(values))
    return {key:revision(values[key]) for key in ids}


def intent_payload(kind, values, versions):
    values=bounded_object(values)
    if kind=='merge':
        if set(values)!={'survivor_id'} or master_key(values['survivor_id']) not in versions:
            raise ContractError('An explicit participating survivor is required')
    elif kind=='override':
        if set(values)!={'field','value'}:
            raise ContractError('An override requires exactly field and value')
        identifier(values['field'])
        if values['field'] in {'record_kind','parent_source_key'} or type(values['value']) not in (str,int,float,bool,type(None)):
            raise ContractError('Only scalar business-field overrides are supported')
    elif kind=='split_new':
        if set(values)!={'members'} or not isinstance(values['members'],list):
            raise ContractError('A split requires explicit source members')
        try:
            values['members']=references([SourceRef(**r) for r in values['members']],SourceRef)
        except (TypeError,KeyError) as error:
            raise ContractError('Typed source members required') from error
    elif kind=='restore_merge':
        if set(values)!={'event_id'}:
            raise ContractError('A restoration requires the original merge event')
        master_key(values['event_id'])
    else:
        raise ContractError('Unsupported stewardship intent kind')
    return values


def lease_seconds(value):
    if type(value) is not int or not 1 <= value <= MAX_LEASE_SECONDS:
        raise ContractError('Lease duration must be 1–900 seconds')
    return value


def command(context, action, arguments, actor, reason, key):
    if not isinstance(context,WorkflowContext):
        raise ContractError('An explicit workflow context is required')
    text_key(actor,'Actor')
    text_key(reason,'Reason',4096)
    text_key(key,'Idempotency key')
    return bounded_object({'context':asdict(context),'action':action,'arguments':arguments,
                           'actor':actor,'reason':reason},maximum=65536)
