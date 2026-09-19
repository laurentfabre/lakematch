"""Lazy native quality checks, with explicit error/warning reasons."""
from dataclasses import dataclass

from pyspark.sql import DataFrame, Window, functions as F


@dataclass
class QualityResult:
    valid: DataFrame
    quarantined: DataFrame


def apply_and_split(frame, config):
    """Duplicate IDs quarantine every occurrence, including otherwise valid rows."""
    ident = config["entity"]["id_column"]
    checks = [
        {"name": "id_required", "kind": "not_null", "column": ident, "criticality": "error"},
        {"name": "id_unique", "kind": "unique", "column": ident, "criticality": "error"},
    ] + config["quality"]["checks"]
    names, reasons = set(), []
    for check in checks:
        if set(check) - {"name", "kind", "column", "criticality", "pattern", "min", "max", "value"}:
            raise ValueError(f"Unknown quality check option: {check}")
        name, kind = check["name"], check["kind"]
        severity = check.get("criticality", "error")
        if name in names or severity not in {"error", "warn"}:
            raise ValueError("Quality names must be unique and criticality must be error or warn")
        names.add(name)
        column = check.get("column", ident)
        if column not in [ident, *config.fields]:
            raise ValueError(f"Quality check references unknown field: {column}")
        value = F.col(column)
        if kind == "not_null":
            passed = value.isNotNull() & (F.length(F.trim(value.cast("string"))) > 0)
        elif kind == "unique":
            passed = F.count(F.lit(1)).over(Window.partitionBy(column)) == 1
        elif kind == "regex":
            passed = value.rlike(check["pattern"])
        elif kind == "range":
            number = value.try_cast("double")
            passed = number.between(check["min"], check["max"])
        elif kind == "min_rows":
            passed = F.count(F.lit(1)).over(Window.partitionBy(F.lit(1))) >= int(check["value"])
        else:
            raise ValueError(f"Unknown quality check kind: {kind}")
        reasons.append(F.when(~F.coalesce(passed, F.lit(False)),
                              F.struct(F.lit(name).alias("check"), F.lit(severity).alias("criticality"))))
    annotated = frame.withColumn("lm_reasons", F.filter(F.array(*reasons), lambda x: x.isNotNull()))
    invalid = F.exists(F.col("lm_reasons"), lambda x: x["criticality"] == "error")
    return QualityResult(annotated.filter(~invalid), annotated.filter(invalid))
