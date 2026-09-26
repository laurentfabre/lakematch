"""Quality gate. `engine(cfg)` returns the module for `quality.engine`: native today, DQX / expectations in ZR-6.

Every engine exposes the same interface: `apply_and_split(df, checks) -> (valid, quarantined)`.
"""
from __future__ import annotations

from ..config import Config
from . import native


def engine(cfg: Config):
    cfg.require("quality.engine")      # dqx and expectations land in ZR-6 (dqx_adapter.py, lazy import)
    return native


def input_checks(cfg: Config, id_column: str, side: str) -> list[native.Check]:
    """The checks every input gets (a present, unique id) plus the config's own for this side.
    A config check may carry `side: left | right | both` (default both)."""
    specs = [{k: v for k, v in s.items() if k != "side"} for s in cfg.get("quality.checks")
             if s.get("side", "both") in (side, "both")]
    return [native.is_not_null(id_column), native.is_unique(id_column)] + native.from_config(specs)
