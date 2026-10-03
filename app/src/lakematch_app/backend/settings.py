"""Where the app reads its queue and writes its labels. One code base, chosen by environment variables, so the same
app runs on the laptop against local files and as a Databricks App against Unity Catalog tables.

    LAKEMATCH_APP_SOURCE        local | warehouse        the queue and run history (written by every lakematch run)
    LAKEMATCH_APP_LABEL_STORE   delta | lakebase         the label store (lakebase = paid_features.lakebase_label_store)

    local      LAKEMATCH_APP_REVIEW_DIR = <storage.root>/review of a laptop run: queue/ (Parquet), runs.jsonl, and the
               label store labels/ (a Delta directory) next to them
    warehouse  LAKEMATCH_APP_SCHEMA (workspace.lakematch): lm_review_queue, lm_review_runs and, for a Delta store,
               lm_review_labels, through the SQL warehouse DATABRICKS_SQL_WAREHOUSE_ID (the app's sql-warehouse resource)
    genie      LAKEMATCH_APP_GENIE (paid_features.genie) and LAKEMATCH_APP_GENIE_SPACE_ID: the Genie panel, which asks
               the space as the signed-in user (genie.py), never as the app's service principal
    lakebase   the table LAKEMATCH_APP_LAKEBASE_TABLE in the app's Lakebase database (PG* variables of its database
               resource; under `apx dev` the dev server's embedded Postgres)

Nothing else is kept between requests: every request reads the store, so a restart (Free Edition stops an app after
24 h) loses nothing.
"""
from __future__ import annotations

import getpass
import socket
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .core._config import env_file


class ReviewSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=env_file, env_prefix="LAKEMATCH_APP_", extra="ignore")

    source: Literal["local", "warehouse"] = "local"
    label_store: Literal["delta", "lakebase"] = "delta"
    review_dir: Path | None = None
    schema_name: str = Field(default="workspace.lakematch", validation_alias="LAKEMATCH_APP_SCHEMA")
    warehouse_id: str | None = Field(default=None, validation_alias="DATABRICKS_SQL_WAREHOUSE_ID")
    lakebase_table: str = "lakematch.review_labels"
    lakebase_database: str = "databricks_postgres"
    local_user: str | None = None          # the reviewer's name on a laptop (no Databricks Apps header there)
    # paid_features.genie (written by scripts/deploy.sh from the engine config): the Genie panel and /api/genie/*
    genie: bool = False
    genie_space_id: str | None = None      # the app's genie-space resource on Databricks

    def local_reviewer(self) -> str:
        return self.local_user or f"{getpass.getuser()}@{socket.gethostname().split('.')[0]}"

    def require_review_dir(self) -> Path:
        if self.review_dir is None:
            raise RuntimeError("LAKEMATCH_APP_SOURCE=local needs LAKEMATCH_APP_REVIEW_DIR (<storage.root>/review)")
        return self.review_dir.expanduser().resolve()


@lru_cache(maxsize=1)
def settings() -> ReviewSettings:
    """Read once per process from the environment: configuration, not state."""
    return ReviewSettings()
