"""Quality gate. `engine(cfg)` returns the engine for `quality.engine`; every engine exposes
`split(df, specs) -> (valid, quarantined)` over the same check specs (dicts, the config's own shape):

    native   native.py: the laptop engine and the reference
    dqx      dqx_adapter.py: the default on Databricks (D18); lazy import, Databricks License
    expectations   expectations.py: Lakeflow expectations inside the pipeline (pipelines/flows.py); everywhere
             else the native engine applies the same specs with the same semantics

Both engines give the same split on the same specs: tests/test_quality.py checks it locally (DQX's documented local
testing mode) and bench/serverless.py measures it on Databricks with seeded bad rows.
"""
from __future__ import annotations

from ..config import Config
from . import native


class _Native:
    name = "native"

    @staticmethod
    def split(df, specs):
        return native.apply_and_split(df, native.from_config(specs))


class _Dqx:
    name = "dqx"

    def __init__(self, workspace_client=None):
        self.ws = workspace_client

    def split(self, df, specs):
        from . import dqx_adapter
        return dqx_adapter.split(df, specs, self.ws)


def engine(cfg: Config, name: str | None = None, workspace_client=None):
    """The engine `quality.engine` names (or `name`, to compare engines on the same input)."""
    name = name or cfg.require("quality.engine")
    if name == "native":
        return _Native()
    if name == "dqx":
        return _Dqx(workspace_client)
    if name == "expectations":     # Lakeflow expectations live in the pipeline (flows.py); a job task applies the
        return _Native()           # same specs natively — expectations.py derives its constraints from the same rules
    cfg.require("quality.engine", name)
    raise ValueError(f"quality.engine: {name} has no engine")


def input_specs(cfg: Config, id_column: str, side: str) -> list[dict]:
    """The checks every input gets (a present, unique id) plus the config's own for this side.
    A config check may carry `side: left | right | both` (default both)."""
    own = [{k: v for k, v in s.items() if k != "side"} for s in cfg.get("quality.checks")
           if s.get("side", "both") in (side, "both")]
    return [{"check": "is_not_null", "column": id_column}, {"check": "is_unique", "columns": [id_column]}] + own


def input_checks(cfg: Config, id_column: str, side: str) -> list[native.Check]:
    return native.from_config(input_specs(cfg, id_column, side))
