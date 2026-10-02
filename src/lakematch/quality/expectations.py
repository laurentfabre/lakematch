"""Lakeflow expectations engine (`quality.engine: expectations`): the gate as pipeline expectations, so pass / drop
counts land in the pipeline's event log. Lakeflow only (open-source pipelines have no expectations); outside a
pipeline the same specs run through the native engine, which has the same semantics.

Every row check becomes one SQL constraint, TRUE for a row that passes, null-safe like native.py (a check whose
condition is null does not fire). Error checks -> `expect_all_or_drop`, warn checks -> `expect_all` (kept, counted).
Expectations see one row at a time, so the dataset-level checks (is_unique, min_rows) are computed first, by the
native engine, into `_dataset_errors` / `_dataset_warnings`, and one more constraint per array reads them.
pipelines/flows.py wires it; tests/test_quality.py checks the constraints give the native split.
"""
from __future__ import annotations

from pyspark.sql import DataFrame, functions as F

from . import native

DATASET_ERRORS, DATASET_WARNINGS = "_dataset_errors", "_dataset_warnings"
DATASET_KINDS = ("is_unique", "min_rows")
DEFAULT_CRITICALITY = {"max_length": "warn"}


def _col(c: str) -> str:
    return "`" + c.replace("`", "``") + "`"


def _str(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def row_constraint(spec: dict) -> str:
    """SQL that is TRUE when the row passes (NULL never fails, as in native.py)."""
    kind, s = spec["check"], spec
    if kind == "is_not_null":
        return f"{_col(s['column'])} IS NOT NULL"
    if kind == "is_not_empty":
        return f"{_col(s['column'])} IS NOT NULL AND trim(CAST({_col(s['column'])} AS STRING)) <> ''"
    if kind == "matches_regex":
        return f"{_col(s['column'])} IS NULL OR CAST({_col(s['column'])} AS STRING) RLIKE {_str(s['pattern'])}"
    if kind == "is_in":
        items = ", ".join(_str(v) if isinstance(v, str) else repr(v) for v in s["values"])
        return f"{_col(s['column'])} IS NULL OR {_col(s['column'])} IN ({items})"
    if kind == "max_length":
        return f"coalesce(length(CAST({_col(s['column'])} AS STRING)) <= {int(s['n'])}, true)"
    if kind == "sql":
        return f"coalesce(NOT ({s['fails_when']}), true)"
    raise ValueError(f"quality.checks: '{kind}' is not a row check")


def constraints(specs: list[dict]) -> tuple[dict[str, str], dict[str, str], list[dict]]:
    """(drop: name -> constraint, warn: name -> constraint, dataset-level specs)."""
    drop, warn, dataset = {}, {}, []
    for i, spec in enumerate(specs):
        if spec["check"] in DATASET_KINDS:
            dataset.append(spec)
            continue
        crit = spec.get("criticality", DEFAULT_CRITICALITY.get(spec["check"], "error"))
        name = f"{i:02d}_{spec['check']}_{spec.get('column') or spec.get('name', '')}"
        (drop if crit == "error" else warn)[name] = row_constraint(spec)
    if any(s.get("criticality", "error") == "error" for s in dataset):
        drop["dataset_checks"] = f"size({DATASET_ERRORS}) = 0"
    if any(s.get("criticality") == "warn" for s in dataset):
        warn["dataset_warnings"] = f"size({DATASET_WARNINGS}) = 0"
    return drop, warn, dataset


def with_dataset_flags(df: DataFrame, dataset_specs: list[dict]) -> DataFrame:
    """The dataset-level checks as two array columns the expectations can read row by row."""
    if not dataset_specs:
        empty = F.array().cast("array<string>")
        return df.withColumn(DATASET_ERRORS, empty).withColumn(DATASET_WARNINGS, empty)
    flagged = native.apply(df, native.from_config(dataset_specs))
    return flagged.withColumnRenamed(native.ERRORS, DATASET_ERRORS).withColumnRenamed(native.WARNINGS, DATASET_WARNINGS)
