"""Framework-neutral dispatch for the APX mastering routes.

The host supplies a verified principal and an explicit domain/context map.
This module has no FastAPI, Spark, token or environment dependency.
"""
from dataclasses import dataclass

import psycopg

from .access_contract import AccessDenied, AccessUnavailable, HiddenObject
from .authorized_workflow import AuthorizedWorkflow, COMMAND_ACTIONS
from .contracts import ContractError
from .registry import RegistryUnavailable
from .workflow_contract import WorkflowConflict, WorkflowContext, WorkflowUnavailable


@dataclass(frozen=True)
class ApiResult:
    status: int
    body: dict


class WorkflowAPI:
    def __init__(self, connect, contexts):
        if (not isinstance(contexts, (list, tuple)) or not 1 <= len(contexts) <= 32
                or not all(isinstance(c, WorkflowContext) for c in contexts)
                or len({c.domain_id for c in contexts}) != len(contexts)):
            raise ContractError('Configure 1–32 unique explicit workflow domain contexts')
        self._connect, self._contexts = connect, {c.domain_id: c for c in contexts}

    def dispatch(self, principal, domain_id, action, arguments, *, key=None):
        if domain_id not in self._contexts:
            return ApiResult(404, {'detail': 'Resource is unavailable'})
        if action not in {*COMMAND_ACTIONS, 'get_task', 'get_operation', 'inbox', 'history'}:
            return ApiResult(422, {'detail': 'Unsupported workflow action'})
        if any(k in arguments for k in ('actor', 'principal', 'grants', 'roles', 'key', 'context')):
            return ApiResult(422, {'detail': 'Identity and grants are server controlled'})
        try:
            store = AuthorizedWorkflow(self._connect, self._contexts[domain_id], principal)
            args = dict(arguments)
            if action in COMMAND_ACTIONS:
                args.update(actor=principal, key=key)
            result = getattr(store, action)(**args)
            return ApiResult(200, result)
        except AccessDenied:
            return ApiResult(403, {'detail': 'Action is not permitted'})
        except (HiddenObject, WorkflowUnavailable, RegistryUnavailable):
            return ApiResult(404, {'detail': 'Resource is unavailable'})
        except WorkflowConflict:
            return ApiResult(409, {'detail': 'Command conflicts with current state or a saved request'})
        except (ContractError, TypeError):
            return ApiResult(422, {'detail': 'Invalid workflow request'})
        except (AccessUnavailable, psycopg.Error):
            return ApiResult(503, {'detail': 'Workflow service is temporarily unavailable'})
