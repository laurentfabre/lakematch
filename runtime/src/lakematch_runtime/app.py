"""Explicit Apps entrypoint; the ordinary APX app remains separately usable."""
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
import os

from lakematch.mastering.access_contract import AccessUnavailable
from lakematch.mastering.workflow_api import WorkflowAPI

from .connection import Connections, app_credentials
from .preflight import verify_connection
from .settings import Binding, require


def create_deployed_app(*, binding=None, connections=None, env=None):
    # The alternative wheel shares the portable lakematch namespace. Refuse a
    # mixed installation rather than running whichever distribution won last.
    try:
        version('lakematch')
    except PackageNotFoundError:
        pass
    else:
        raise AccessUnavailable('Install the workflow runtime in an isolated app environment')
    env = dict(os.environ if env is None else env)
    if binding is None:
        require(bool(env.get('LAKEMATCH_WORKFLOW_BINDING')), 'Select a workflow binding file')
        binding = Binding.load(env['LAKEMATCH_WORKFLOW_BINDING'])
    user = binding.validate_environment(env)
    if connections is None:
        credentials = app_credentials(binding, env)
        connections = Connections(binding, user, credentials,
            lambda connection: verify_connection(connection, binding, user))
    # Delay APX imports until deployment inputs have passed validation.
    from lakematch_review.backend.app import create_review_app
    app = create_review_app(WorkflowAPI(connections.connection, binding.contexts))
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(instance):
        from starlette.concurrency import run_in_threadpool
        def ready():
            with connections.connection():
                pass
        await run_in_threadpool(ready)
        async with original(instance):
            yield
    app.router.lifespan_context = lifespan
    return app
