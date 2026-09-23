"""APX transport for the separately configured mastering service.

No engine or PostgreSQL dependency is imported by the default review app. A
deployment entrypoint must explicitly bind a WorkflowAPI at app construction.
Missing binding fails closed; local review identity is never used here.
"""
from __future__ import annotations

import json
import os
import re
from typing import Annotated, Any, Literal, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt


class DispatchResult(Protocol):
    status: int
    body: dict[str, Any]


class MasteringAPI(Protocol):
    def dispatch(self, principal: str, domain_id: str, action: str,
                 arguments: dict[str, Any], *, key: str | None = None) -> DispatchResult: ...


class MasteringBoundaryMiddleware:
    """Bound request bodies and prevent HTTP caching on the entire v1 surface."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope['path'].startswith('/api/v1/'):
            return await self.app(scope, receive, send)

        async def private_send(message):
            if message['type'] == 'http.response.start':
                headers = [(k, v) for k, v in message.get('headers', []) if k.lower() != b'cache-control']
                message = {**message, 'headers': [*headers, (b'cache-control', b'no-store')]}
            await send(message)

        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body.extend(message.get('body', b''))
            if len(body) > 65536:
                return await JSONResponse({'detail': 'Workflow request exceeds 64 KiB'}, status_code=413)(scope, receive, private_send)
            if not message.get('more_body', False):
                break
        if body and scope['method'] in {'POST', 'PUT', 'PATCH'}:
            try:
                def unique_object(pairs):
                    result = {}
                    for key, value in pairs:
                        if key in result:
                            raise ValueError('Duplicate JSON key')
                        result[key] = value
                    return result
                def reject_constant(value):
                    raise ValueError('Nonfinite JSON')
                value = json.loads(body, object_pairs_hook=unique_object, parse_constant=reject_constant)
                nodes = 0
                def bounded(item, depth=0):
                    nonlocal nodes
                    nodes += 1
                    if depth > 16 or nodes > 4096:
                        raise ValueError('JSON envelope exceeded')
                    if isinstance(item, dict):
                        for v in item.values():
                            bounded(v, depth+1)
                    elif isinstance(item, list):
                        for v in item:
                            bounded(v, depth+1)
                bounded(value)
            except (ValueError, UnicodeError, RecursionError):
                return await JSONResponse({'detail': 'Invalid bounded JSON request'}, status_code=400)(scope, receive, private_send)
        delivered = False
        async def bounded_receive():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
        await self.app(scope, bounded_receive, private_send)


def authenticated_principal(request: Request) -> str:
    # This trust boundary requires the Databricks Apps ingress to be the only
    # network entry and to overwrite user headers. Local callers cannot opt in
    # through an HTTP header; actual proxy isolation remains a deployment test.
    workspace = os.environ.get('DATABRICKS_WORKSPACE_ID', '')
    users = request.headers.getlist('x-forwarded-user')
    if (not os.environ.get('DATABRICKS_APP_NAME') or not re.fullmatch(r'[0-9]{1,24}', workspace)
            or len(users) != 1 or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', users[0])):
        raise HTTPException(401, 'An authenticated Databricks Apps user session is required')
    return f'databricks:{workspace}:{users[0]}'


def configured_api(request: Request) -> MasteringAPI:
    api = getattr(request.app.state, 'mastering_api', None)
    if api is None:
        raise HTTPException(503, 'Mastering is not configured for this deployment')
    return api


def command_key(request: Request) -> str:
    values = request.headers.getlist('idempotency-key')
    if (len(values) != 1 or not values[0].strip() or values[0] != values[0].strip()
            or len(values[0].encode()) > 512 or '\x00' in values[0]):
        raise HTTPException(422, 'One bounded Idempotency-Key header is required')
    return values[0]


Principal = Annotated[str, Depends(authenticated_principal)]
Backend = Annotated[MasteringAPI, Depends(configured_api)]
Key = Annotated[str, Depends(command_key)]
PositiveRevision = Annotated[StrictInt, Field(ge=1, lt=2**63-1)]


class CommandIn(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    reason: str = Field(min_length=1, max_length=4096)


class CreateTaskIn(CommandIn):
    kind: Literal['merge', 'override', 'split_new', 'restore_merge']
    entity_ids: list[str] = Field(min_length=1, max_length=32)
    priority: StrictInt = Field(default=0, ge=-1000, le=1000)
    evidence: dict[str, Any]


class RevisionIn(CommandIn):
    expected_revision: PositiveRevision


class ClaimIn(RevisionIn):
    seconds: StrictInt = Field(ge=1, le=900)


class LeaseIn(RevisionIn):
    lease_token: str


class RenewIn(LeaseIn):
    seconds: StrictInt = Field(ge=1, le=900)


class CancelIn(RevisionIn):
    lease_token: str | None = None


class ProposeIn(LeaseIn):
    versions: dict[str, PositiveRevision]
    payload: dict[str, Any]
    evidence: dict[str, Any]


def _dispatch(api, principal, domain_id, action, arguments, key=None):
    result = api.dispatch(principal, domain_id, action, arguments, key=key)
    return JSONResponse(result.body, status_code=result.status)


def _cursor(value):
    if value is None:
        return None
    try:
        cursor = json.loads(value)
        if not isinstance(cursor, dict):
            raise ValueError()
        return cursor
    except (ValueError, RecursionError):
        raise HTTPException(422, 'Invalid pagination cursor') from None


router = APIRouter(prefix='/api/v1/domains/{domain_id}', tags=['Mastering workflow'])


@router.post('/tasks', response_model=dict[str, Any], operation_id='masteringCreateTask')
def create_task(domain_id: str, body: CreateTaskIn, principal: Principal, api: Backend, key: Key):
    return _dispatch(api, principal, domain_id, 'create_task', body.model_dump(), key)


@router.get('/tasks', response_model=dict[str, Any], operation_id='masteringInbox')
def inbox(domain_id: str, principal: Principal, api: Backend,
          state: Literal['open', 'claimed', 'resolved', 'canceled'] = 'open',
          limit: int = Query(50, ge=1, le=100), after: str | None = Query(None, max_length=2048)):
    return _dispatch(api, principal, domain_id, 'inbox', {'state': state, 'limit': limit, 'after': _cursor(after)})


@router.get('/tasks/{task_id}', response_model=dict[str, Any], operation_id='masteringGetTask')
def get_task(domain_id: str, task_id: UUID, principal: Principal, api: Backend):
    return _dispatch(api, principal, domain_id, 'get_task', {'task_id': str(task_id)})


@router.post('/tasks/{task_id}/claim', response_model=dict[str, Any], operation_id='masteringClaimTask')
def claim(domain_id: str, task_id: UUID, body: ClaimIn, principal: Principal, api: Backend, key: Key):
    return _dispatch(api, principal, domain_id, 'claim', {'task_id': str(task_id), **body.model_dump()}, key)


@router.post('/tasks/{task_id}/renew', response_model=dict[str, Any], operation_id='masteringRenewTask')
def renew(domain_id: str, task_id: UUID, body: RenewIn, principal: Principal, api: Backend, key: Key):
    return _dispatch(api, principal, domain_id, 'renew', {'task_id': str(task_id), **body.model_dump()}, key)


@router.post('/tasks/{task_id}/release', response_model=dict[str, Any], operation_id='masteringReleaseTask')
def release(domain_id: str, task_id: UUID, body: LeaseIn, principal: Principal, api: Backend, key: Key):
    return _dispatch(api, principal, domain_id, 'release', {'task_id': str(task_id), **body.model_dump()}, key)


@router.post('/tasks/{task_id}/cancel', response_model=dict[str, Any], operation_id='masteringCancelTask')
def cancel(domain_id: str, task_id: UUID, body: CancelIn, principal: Principal, api: Backend, key: Key):
    return _dispatch(api, principal, domain_id, 'cancel', {'task_id': str(task_id), **body.model_dump()}, key)


@router.post('/tasks/{task_id}/propose', response_model=dict[str, Any], operation_id='masteringPropose')
def propose(domain_id: str, task_id: UUID, body: ProposeIn, principal: Principal, api: Backend, key: Key):
    return _dispatch(api, principal, domain_id, 'propose', {'task_id': str(task_id), **body.model_dump()}, key)


@router.get('/operations/{operation_id}', response_model=dict[str, Any], operation_id='masteringGetOperation')
def get_operation(domain_id: str, operation_id: UUID, principal: Principal, api: Backend):
    return _dispatch(api, principal, domain_id, 'get_operation', {'operation_id': str(operation_id)})


@router.post('/operations/{operation_id}/approve', response_model=dict[str, Any], operation_id='masteringApprove')
def approve(domain_id: str, operation_id: UUID, body: RevisionIn, principal: Principal, api: Backend, key: Key):
    return _dispatch(api, principal, domain_id, 'approve', {'operation_id': str(operation_id), **body.model_dump()}, key)


@router.get('/tasks/{task_id}/history', response_model=dict[str, Any], operation_id='masteringTaskHistory')
def task_history(domain_id: str, task_id: UUID, principal: Principal, api: Backend,
                 limit: int = Query(50, ge=1, le=100), after: str | None = Query(None, max_length=2048)):
    return _dispatch(api, principal, domain_id, 'history', {'task_id': str(task_id), 'limit': limit, 'after': _cursor(after)})


@router.get('/operations/{operation_id}/history', response_model=dict[str, Any], operation_id='masteringOperationHistory')
def operation_history(domain_id: str, operation_id: UUID, principal: Principal, api: Backend,
                      limit: int = Query(50, ge=1, le=100), after: str | None = Query(None, max_length=2048)):
    return _dispatch(api, principal, domain_id, 'history',
                     {'operation_id': str(operation_id), 'limit': limit, 'after': _cursor(after)})
