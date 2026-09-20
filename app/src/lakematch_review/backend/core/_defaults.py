# Modified for lakematch on 2026-09-20 from the APX 0.3.8 scaffold.
from __future__ import annotations
from typing import Annotated, AsyncGenerator, TypeAlias
from contextlib import asynccontextmanager
import os

from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config as DatabricksConfig
from fastapi import Depends, FastAPI, Request, HTTPException

from ._base import LifespanDependency
from ._config import AppConfig, logger
from ._headers import HeadersDependency


class _ConfigDependency(LifespanDependency):
    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        app.state.config = AppConfig()
        logger.info(f"Starting app with configuration:\n{app.state.config}")
        yield

    @staticmethod
    def __call__(request: Request) -> AppConfig:
        return request.app.state.config


class _WorkspaceClientDependency(LifespanDependency):
    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncGenerator[None, None]:
        config = app.state.config
        app.state.workspace_client = None
        if config.store == "delta":
            if os.environ.get("DATABRICKS_APP_NAME"):
                app.state.workspace_client = WorkspaceClient(config=DatabricksConfig(http_timeout_seconds=55, retry_timeout_seconds=60))
            elif config.workspace_profile:
                app.state.workspace_client = WorkspaceClient(config=DatabricksConfig(profile=config.workspace_profile, http_timeout_seconds=55, retry_timeout_seconds=60))
            else:
                raise ValueError("Select a workspace_profile for local Delta access")
        yield

    @staticmethod
    def __call__(request: Request) -> WorkspaceClient:
        client = request.app.state.workspace_client
        if client is None:
            raise HTTPException(503, "Workspace access is disabled in local mode")
        return client


def _get_user_ws(
    headers: HeadersDependency,
) -> WorkspaceClient:
    """
    Returns a Databricks Workspace client with authentication behalf of user.
    If the request contains an X-Forwarded-Access-Token header, on behalf of user authentication is used.

    Example usage: `user_ws: Dependencies.UserClient`
    """

    if not headers.token:
        raise HTTPException(401, "A delegated user session is required")

    return WorkspaceClient(config=DatabricksConfig(
        host=os.environ.get("DATABRICKS_HOST"), token=headers.token.get_secret_value(), auth_type="pat",
        http_timeout_seconds=55, retry_timeout_seconds=60,
    ))  # explicit token auth prevents a fallback to the app service principal


ConfigDependency: TypeAlias = Annotated[AppConfig, _ConfigDependency.depends()]

ClientDependency: TypeAlias = Annotated[
    WorkspaceClient, _WorkspaceClientDependency.depends()
]

UserWorkspaceClientDependency: TypeAlias = Annotated[
    WorkspaceClient, Depends(_get_user_ws)
]
