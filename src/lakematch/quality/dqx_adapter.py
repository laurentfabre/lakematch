"""DQX quality engine — the default whenever the runtime is Databricks (D18).

DQX (databricks-labs-dqx) carries the Databricks License: it may only be used within or connecting to Databricks
services, so it is imported here and nowhere else, lazily, and is never a mandatory dependency (the `dqx` extra).
The native engine (native.py) is the reference this adapter must agree with on the valid / quarantine split: every
lakematch check spec maps to one DQX check with the same failing rows, null handling included (a check whose
condition is null does not fire, in both engines).

    is_not_null     -> is_not_null
    is_not_empty    -> is_not_null_and_not_empty(trim_strings=True)    native: null or blank after trim
    matches_regex   -> regex_match                                      null passes
    is_in           -> is_in_list (string values quoted: DQX parses bare strings as expressions)
    max_length      -> sql_expression(length(cast(c as string)) > n, negate=True)
    sql             -> sql_expression(<fails_when>, negate=True)
    is_unique       -> is_unique(nulls_distinct=False)                  native groups nulls together
    min_rows        -> is_aggr_not_less_than(column="*", aggr_type=count)

Output is normalised to the native shape: `_errors` / `_warnings` as array<string> of messages (DQX keeps structs).
"""
from __future__ import annotations

from pyspark.sql import Column, DataFrame, functions as F

from .native import ERRORS, WARNINGS

DEFAULT_CRITICALITY = {"max_length": "warn"}       # as in native.py's constructors


def _quote(col: str) -> str:
    return "`" + col.replace("`", "``") + "`"


def _literal(v):
    if isinstance(v, str):
        return "'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'"
    return v


def to_dqx(spec: dict) -> dict:
    """One lakematch check spec -> one DQX metadata check."""
    s = dict(spec)
    kind = s.pop("check")
    crit = s.pop("criticality", DEFAULT_CRITICALITY.get(kind, "error"))
    if kind == "is_not_null":
        fn, args = "is_not_null", {"column": s["column"]}
    elif kind == "is_not_empty":
        fn, args = "is_not_null_and_not_empty", {"column": s["column"], "trim_strings": True}
    elif kind == "matches_regex":
        fn, args = "regex_match", {"column": s["column"], "regex": s["pattern"]}
    elif kind == "is_in":
        # DQX reads a bare string as a column expression ("75001" even as a number): quote string literals
        fn, args = "is_in_list", {"column": s["column"], "allowed": [_literal(v) for v in s["values"]]}
    elif kind == "max_length":
        fn, args = "sql_expression", {"expression": f"length(cast({_quote(s['column'])} as string)) > {int(s['n'])}",
                                      "negate": True, "msg": f"{s['column']} is longer than {s['n']}",
                                      "name": f"{s['column']}_max_length_{s['n']}"}
    elif kind == "sql":
        fn, args = "sql_expression", {"expression": s["fails_when"], "negate": True,
                                      "msg": s.get("message") or f"{s['name']} failed", "name": s["name"]}
    elif kind == "is_unique":
        cols = s["columns"]
        fn, args = "is_unique", {"columns": [cols] if isinstance(cols, str) else list(cols), "nulls_distinct": False}
    elif kind == "min_rows":
        fn, args = "is_aggr_not_less_than", {"column": "*", "limit": int(s["n"]), "aggr_type": "count"}
    else:
        raise ValueError(f"quality.checks: '{kind}' has no DQX mapping")
    return {"criticality": crit, "check": {"function": fn, "arguments": args}}


def _messages(col: str) -> Column:
    return F.coalesce(F.transform(F.col(col), lambda x: x["message"]), F.array().cast("array<string>"))


def engine(workspace_client=None):
    from databricks.labs.dqx.config import ExtraParams
    from databricks.labs.dqx.engine import DQEngine
    if workspace_client is None:
        from databricks.sdk import WorkspaceClient
        workspace_client = WorkspaceClient()
    return DQEngine(workspace_client, extra_params=ExtraParams(
        result_column_names={"errors": ERRORS, "warnings": WARNINGS}))


def split(df: DataFrame, specs: list[dict], workspace_client=None) -> tuple[DataFrame, DataFrame]:
    """(valid, quarantined), shaped like native.apply_and_split: valid keeps `_warnings`, quarantined keeps both."""
    checks = [to_dqx(s) for s in specs]
    dq = engine(workspace_client)
    problems = dq.validate_checks(checks)
    if problems.has_errors:
        raise ValueError(f"DQX refused the checks: {problems.errors}")
    checked = dq.apply_checks_by_metadata(df, checks)
    checked = checked.withColumn(ERRORS, _messages(ERRORS)).withColumn(WARNINGS, _messages(WARNINGS))
    valid = checked.filter(F.size(ERRORS) == 0).drop(ERRORS)
    quarantined = checked.filter(F.size(ERRORS) > 0)
    return valid, quarantined
