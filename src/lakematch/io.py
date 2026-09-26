"""Reading inputs named in the config: CSV (header, all strings) or Parquet by extension, or a table by name."""
from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession

from .config import Config


def read_table(spark: SparkSession, cfg: Config, spec: dict) -> DataFrame:
    if spec.get("table"):
        return spark.table(spec["table"])
    path = cfg.path(spec["path"])
    fmt = spec.get("format") or ("parquet" if path.suffix == ".parquet" or path.is_dir() else "csv")
    if fmt == "csv":
        return spark.read.option("header", True).option("inferSchema", False).csv(str(path))
    return spark.read.format(fmt).load(str(path))
