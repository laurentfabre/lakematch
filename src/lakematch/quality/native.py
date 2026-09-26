"""Native data-quality engine: the laptop engine and the reference the DQX adapter must agree with (ZR-6).

A check is row-level (a predicate on one row) or dataset-level (a predicate that needs the other rows: uniqueness,
a minimum row count), each with a criticality:

    error   the row goes to quarantine
    warn    the row stays valid, the message is kept

`apply(df, checks)` adds two columns, `_errors` and `_warnings` (arrays of messages, empty when clean — the column
names DQX uses). `apply_and_split(df, checks)` returns `(valid, quarantined)`. Everything is lazy: no action, so the
gate can sit at the head of a Spark Declarative Pipelines flow.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from pyspark.sql import Column, DataFrame, Window, functions as F

ERRORS, WARNINGS = "_errors", "_warnings"
CRITICALITIES = ("error", "warn")


@dataclass(frozen=True)
class Check:
    name: str
    fails: Callable[[DataFrame], Column]      # TRUE where the row fails the check
    message: str
    criticality: str = "error"
    level: str = "row"                        # row | dataset

    def __post_init__(self):
        if self.criticality not in CRITICALITIES:
            raise ValueError(f"check {self.name}: criticality must be error or warn")


# --- row-level ----------------------------------------------------------------------------------------------------
def is_not_null(column: str, criticality: str = "error") -> Check:
    return Check(f"is_not_null({column})", lambda df: F.col(column).isNull(), f"{column} is null", criticality)


def is_not_empty(column: str, criticality: str = "error") -> Check:
    return Check(f"is_not_empty({column})",
                 lambda df: F.col(column).isNull() | (F.trim(F.col(column).cast("string")) == ""),
                 f"{column} is empty", criticality)


def matches_regex(column: str, pattern: str, criticality: str = "error") -> Check:
    return Check(f"matches_regex({column})",
                 lambda df: F.col(column).isNotNull() & ~F.col(column).cast("string").rlike(pattern),
                 f"{column} does not match {pattern}", criticality)


def is_in(column: str, values: Iterable, criticality: str = "error") -> Check:
    values = list(values)
    return Check(f"is_in({column})", lambda df: F.col(column).isNotNull() & ~F.col(column).isin(values),
                 f"{column} is not in the allowed set", criticality)


def max_length(column: str, n: int, criticality: str = "warn") -> Check:
    return Check(f"max_length({column},{n})", lambda df: F.length(F.col(column).cast("string")) > n,
                 f"{column} is longer than {n}", criticality)


def sql(name: str, fails_when: str, criticality: str = "error", message: str | None = None) -> Check:
    """A row check written as a Spark SQL predicate that is TRUE on failing rows."""
    return Check(name, lambda df: F.expr(fails_when), message or f"{name} failed", criticality)


# --- dataset-level ------------------------------------------------------------------------------------------------
def is_unique(columns: list[str] | str, criticality: str = "error") -> Check:
    cols = [columns] if isinstance(columns, str) else list(columns)
    return Check(f"is_unique({','.join(cols)})",
                 lambda df: F.count(F.lit(1)).over(Window.partitionBy(*cols)) > 1,
                 f"{','.join(cols)} is not unique", criticality, "dataset")


def min_rows(n: int, criticality: str = "error") -> Check:
    """Every row fails when the dataset holds fewer than n rows (an unpartitioned window: small inputs only)."""
    return Check(f"min_rows({n})", lambda df: F.count(F.lit(1)).over(Window.partitionBy()) < n,
                 f"dataset has fewer than {n} rows", criticality, "dataset")


REGISTRY = {"is_not_null": is_not_null, "is_not_empty": is_not_empty, "matches_regex": matches_regex,
            "is_in": is_in, "max_length": max_length, "is_unique": is_unique, "min_rows": min_rows, "sql": sql}


def from_config(specs: list[dict]) -> list[Check]:
    """[{check: is_not_null, column: rec_id, criticality: error}, {check: is_unique, columns: [rec_id]}, ...]"""
    checks = []
    for spec in specs:
        spec = dict(spec)
        kind = spec.pop("check", None)
        if kind not in REGISTRY:
            raise ValueError(f"quality.checks: unknown check '{kind}' ({', '.join(REGISTRY)})")
        checks.append(REGISTRY[kind](**spec))
    return checks


# --- engine -------------------------------------------------------------------------------------------------------
def apply(df: DataFrame, checks: list[Check]) -> DataFrame:
    """Add `_errors` and `_warnings` (array<string>, empty when the row passes)."""
    def messages(level: str) -> Column:
        hits = [F.when(c.fails(df), F.lit(c.message)) for c in checks if c.criticality == level]
        if not hits:
            return F.array().cast("array<string>")
        return F.filter(F.array(*hits), lambda m: m.isNotNull())
    return df.withColumn(ERRORS, messages("error")).withColumn(WARNINGS, messages("warn"))


def apply_and_split(df: DataFrame, checks: list[Check]) -> tuple[DataFrame, DataFrame]:
    """(valid, quarantined): valid rows keep `_warnings`; quarantined rows keep both reason columns."""
    checked = apply(df, checks)
    valid = checked.filter(F.size(ERRORS) == 0).drop(ERRORS)
    quarantined = checked.filter(F.size(ERRORS) > 0)
    return valid, quarantined
