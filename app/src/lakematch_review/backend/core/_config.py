# Modified for lakematch on 2026-09-20 from the APX 0.3.8 scaffold.
from __future__ import annotations

import logging
from importlib import resources
from pathlib import Path
from typing import ClassVar
from typing import Literal
import os

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..._metadata import app_name, app_slug

# --- Config ---

project_root = Path(__file__).parent.parent.parent.parent.parent
env_file = project_root / ".env"

if env_file.exists():
    load_dotenv(dotenv_path=env_file)


class AppConfig(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=env_file,
        env_prefix=f"{app_slug.upper()}_",
        extra="ignore",
        env_nested_delimiter="__",
    )
    app_name: str = Field(default=app_name)
    store: Literal["sqlite", "delta"] = "sqlite"
    database: str = "data/review.sqlite"
    warehouse_id: str = ""
    schema_name: str = ""
    local_user: str = "local-reviewer"
    workspace_profile: str | None = None
    genie_enabled: bool = False
    genie_space_id: str = ""

    @model_validator(mode="after")
    def validate_storage(self):
        if os.environ.get("DATABRICKS_APP_NAME") and self.store != "delta":
            raise ValueError("Deployed reviews require durable Delta storage")
        if self.store == "delta" and (not self.warehouse_id or not self.schema_name):
            raise ValueError("Delta storage requires a warehouse resource and schema")
        return self

    @property
    def static_assets_path(self) -> Path:
        return Path(str(resources.files(app_slug))).joinpath("__dist__")

    def __hash__(self) -> int:
        return hash(self.app_name)


# --- Logger ---

logger = logging.getLogger(app_name)
