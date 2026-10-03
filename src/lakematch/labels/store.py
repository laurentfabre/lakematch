"""The arbitration app's label store, as the engine reads it (`labels.source: app`, ZR-7).

The store is append-only: one row per decision a reviewer took, never updated in place, so a restarted app (Databricks
stops an app after 24 h on Free Edition) or two app workers never lose or overwrite a label. A pair's label is its
latest row; `retract` (the app's undo) withdraws it and sends the pair back to the queue; `unsure` is recorded with its
provenance but is not a training label.

Where it lives (`labels.store`): a Delta table by default — `<storage.catalog>.lm_review_labels` on Databricks, a Delta
directory `<storage.root>/review/labels` on the laptop (read with the `deltalake` package, extra `review`: the laptop
Spark has no Delta jar). With `paid_features.lakebase_label_store` the app writes to Lakebase and the engine reads the
same rows through the Lakebase database catalog registered in Unity Catalog (`labels.store.table`).

The app (app/, a separate sub-project) writes these columns; it never imports the engine and the engine never imports
it. `STORE_COLUMNS` is the contract both sides test against.
"""
from __future__ import annotations

from pathlib import Path

from pyspark.sql import DataFrame, SparkSession, Window, functions as F

from ..config import Config

STORE_COLUMNS: list[tuple[str, str]] = [
    ("l_id", "string"),            # the pair, as the queue names it
    ("r_id", "string"),
    ("decision", "string"),        # match | no_match | unsure | retract
    ("is_match", "double"),        # 1.0 / 0.0; null for unsure and retract
    ("reviewer", "string"),        # the signed-in user (X-Forwarded-Email on Databricks, the OS user on a laptop)
    ("labelled_at", "timestamp"),  # UTC, set by the app's server, never by the browser
    ("model_version", "string"),   # the model that scored the pair the reviewer saw (from the queue row)
    ("p", "double"),               # that model's probability for the pair
    ("threshold", "double"),       # and its decision threshold
    ("reason", "string"),          # why: a reason code's text or the reviewer's own words (never empty)
    ("queue_reason", "string"),    # why the pair was queued: near_threshold | llm_unsure | high_impact | other
    ("llm_label", "string"),       # the LLM's opinion shown with the pair: same | different | unsure | null
    ("run_id", "string"),          # the run that wrote the queue
    ("label_id", "string"),        # a uuid per row
]
DECISIONS = ("match", "no_match", "unsure", "retract")
DEFAULT_TABLE = "lm_review_labels"


def location(cfg: Config) -> dict:
    """{"table": name} or {"path": Path}: where this config's label store lives."""
    spec = cfg.get("labels.store") or {}
    if spec.get("table"):
        return {"table": spec["table"]}
    if spec.get("path"):
        return {"path": cfg.path(spec["path"])}
    if cfg.get("storage.catalog"):
        return {"table": f"{cfg.get('storage.catalog')}.{DEFAULT_TABLE}"}
    return {"path": cfg.path(cfg.get("storage.root")) / "review" / "labels"}


def _schema() -> str:
    return ", ".join(f"{n} {t}" for n, t in STORE_COLUMNS)


def events(spark: SparkSession, cfg: Config) -> DataFrame:
    """Every row of the store (empty with the contract's schema when the store does not exist yet)."""
    loc = location(cfg)
    if "table" in loc:
        if not spark.catalog.tableExists(loc["table"]):
            return spark.createDataFrame([], _schema())
        df = spark.table(loc["table"])
    else:
        df = _read_delta_dir(spark, loc["path"])
        if df is None:
            return spark.createDataFrame([], _schema())
    missing = [n for n, _ in STORE_COLUMNS if n not in df.columns]
    if missing:
        raise ValueError(f"label store {loc}: missing column(s) {', '.join(missing)} (contract: labels/store.py)")
    return df.select(*[F.col(n).cast(t).alias(n) for n, t in STORE_COLUMNS])


def _read_delta_dir(spark: SparkSession, path: Path) -> DataFrame | None:
    if not (Path(path) / "_delta_log").is_dir():
        return None
    try:
        from deltalake import DeltaTable
    except ImportError as e:   # pragma: no cover - the message is the point
        raise ImportError("labels.source: app on the laptop reads a Delta directory with the `deltalake` package: "
                          "pip install 'lakematch[review]'") from e
    pdf = DeltaTable(str(path)).to_pandas()
    if pdf.empty:
        return None
    return spark.createDataFrame(pdf[[n for n, _ in STORE_COLUMNS]], _schema())


def current(spark: SparkSession, cfg: Config) -> DataFrame:
    """One row per pair: its latest decision, retracted pairs dropped."""
    ev = events(spark, cfg)
    w = Window.partitionBy("l_id", "r_id").orderBy(F.col("labelled_at").desc(), F.col("label_id").desc())
    latest = ev.withColumn("_n", F.row_number().over(w)).filter("_n = 1").drop("_n")
    return latest.filter(F.col("decision") != "retract")


def training_labels(spark: SparkSession, cfg: Config) -> DataFrame:
    """(l_id, r_id, label): the current match / no-match decisions; unsure pairs are not labels."""
    return (current(spark, cfg).filter(F.col("decision").isin("match", "no_match"))
            .select("l_id", "r_id", F.col("is_match").cast("double").alias("label")))
