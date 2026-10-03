"""The arbitration app's inputs (ZR-7): the review queue and the run history, written by every run.

Queue order (spec/BRIEF.md ZR-7): uncertainty first, then high-impact merges.

    near_threshold   |p - threshold| <= review.band                          tier 0, closest to the threshold first
    llm_unsure       the LLM (review.llm) could not tell, among the review.llm_pairs most uncertain pairs
                                                                             tier 0, ahead of near_threshold
    high_impact      a linked pair whose merge yields an entity of >= review.impact_min records (the crosswalk)
                                                                             tier 1, largest merge first
    other            the rest, closest to the threshold first                tier 2

Within a tier, pairs at the same distance from the threshold (a tree ensemble's probabilities come in a few discrete
values) are ordered by how much the candidate ranking disagrees with the decision: an unlinked pair with a high
candidate score, or a linked pair with a low one, comes first.

At most review.max_pairs pairs, ranked 1..n. Each row carries what a reviewer needs to decide and what the label
store must record about it: both records as JSON (the gate's valid rows, not the normalised entity view), p, the
threshold and the model version that produced them. The app removes a pair from the queue once the store holds a
decision for it, so the queue itself is never written by the app.

The run history (one row per run) feeds the app's statistics: precision / recall on the evaluation sample per model
version, label counts, quarantine counts, queue depth.

Laptop: <storage.root>/review/queue/ (Parquet, overwritten) and <storage.root>/review/runs.jsonl (appended).
Databricks: <storage.catalog>.lm_review_queue (overwritten) and .lm_review_runs (appended); the train task also creates
the empty label table, so the app's service principal needs SELECT and MODIFY, never CREATE.
"""
from __future__ import annotations

import json
import logging
import time
from collections import Counter
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession, Window, functions as F

from .config import Config

log = logging.getLogger("lakematch")

QUEUE_TABLE, RUNS_TABLE = "lm_review_queue", "lm_review_runs"
QUEUE_COLUMNS = ["rank", "l_id", "r_id", "p", "threshold", "distance", "queue_reason", "llm_label", "llm_p_same",
                 "linked", "impact", "cand_score", "cand_rank", "l_record", "r_record", "model_version", "run_id", "created_at"]
RUN_COLUMNS: list[tuple[str, str]] = [
    ("run_id", "string"), ("model_version", "string"), ("created_at", "string"), ("threshold", "double"),
    ("evaluation", "string"),            # truth (the evaluation sample) | none
    ("precision", "double"), ("recall", "double"), ("f1", "double"),
    ("candidates", "long"), ("links", "long"), ("labels_train", "long"), ("labels_validation", "long"),
    ("label_source", "string"), ("app_labels_used", "long"), ("label_set_sha256", "string"),
    ("quarantined_left", "long"), ("quarantined_right", "long"),
    ("queue_pairs", "long"), ("queue_by_reason", "string"),   # JSON {reason: count}
    ("llm", "string"), ("llm_usd", "double"),
]


def _table(cfg: Config, name: str) -> str:
    return f"{cfg.get('storage.catalog')}.{name}"


def _sizes(spark: SparkSession, crosswalk: dict[str, str] | None, side: str) -> DataFrame:
    """(<side>_id, <side>_cluster, <side>_size) from a crosswalk {"left:<id>" | "right:<id>": mdm_id}."""
    p = side[0]
    schema = f"{p}_id string, {p}_cluster string, {p}_size int"
    if not crosswalk:
        return spark.createDataFrame([], schema)
    size = Counter(crosswalk.values())
    pre = f"{side}:"
    rows = [(k[len(pre):], c, size[c]) for k, c in crosswalk.items() if k.startswith(pre)]
    return spark.createDataFrame(rows, schema)


def _records(raw: DataFrame, id_column: str, cfg: Config, p: str) -> DataFrame:
    fields = [f for f in cfg.fields if f in raw.columns]
    return raw.select(F.col(id_column).cast("string").alias(f"{p}_id"),
                      F.to_json(F.struct(*[F.col(f).cast("string").alias(f) for f in fields])).alias(f"{p}_record"))


def build_queue(spark: SparkSession, cfg: Config, *, scored: DataFrame, linked: DataFrame, threshold: float,
                model_version: str, run_id: str, crosswalk: dict[str, str] | None, raws: dict[str, DataFrame],
                left: DataFrame | None = None, right: DataFrame | None = None) -> tuple[DataFrame, dict]:
    """The ranked queue (QUEUE_COLUMNS) and its statistics. `scored`: every candidate pair with p; `linked`: the
    pairs the decision policy linked; `raws`: the gate's valid rows per side (ids in inputs.<side>.id); `left` /
    `right`: the entity sides, needed only when review.llm asks an LLM."""
    band, impact_min = float(cfg.get("review.band")), cfg.get("review.impact_min")
    thr = F.lit(float(threshold))
    cand = [F.col(c) if c in scored.columns else F.lit(None).cast(t).alias(c)
            for c, t in (("cand_score", "double"), ("cand_rank", "int"))]
    base = (scored.select("l_id", "r_id", F.col("p").cast("double").alias("p"), *cand)
            .withColumn("cand_rank", F.col("cand_rank").cast("int"))
            .join(linked.select("l_id", "r_id").withColumn("_linked", F.lit(True)), ["l_id", "r_id"], "left")
            .withColumn("linked", F.coalesce(F.col("_linked"), F.lit(False))).drop("_linked")
            .withColumn("distance", F.abs(F.col("p") - thr))
            .join(_sizes(spark, crosswalk, "left"), "l_id", "left")
            .join(_sizes(spark, crosswalk, "right"), "r_id", "left")
            .withColumn("impact", F.when(F.col("l_cluster") == F.col("r_cluster"), F.col("l_size"))
                        .otherwise(F.coalesce(F.col("l_size"), F.lit(1)) + F.coalesce(F.col("r_size"), F.lit(1)))
                        .cast("int"))
            .drop("l_cluster", "r_cluster", "l_size", "r_size"))
    near = F.col("distance") <= band
    disagree = F.when(F.col("linked"), F.coalesce(F.col("cand_score"), F.lit(0.0))) \
        .otherwise(-F.coalesce(F.col("cand_score"), F.lit(0.0)))
    big = F.col("linked") & (F.col("impact") >= impact_min)

    stats: dict = {"band": band, "impact_min": impact_min, "llm": cfg.get("review.llm")}
    opinions = spark.createDataFrame([], "l_id string, r_id string, llm_label string, llm_p_same double")
    n_llm = cfg.get("review.llm_pairs")
    if cfg.get("review.llm") == "jev" and n_llm:
        if left is None or right is None:
            raise ValueError("review.llm: jev needs the entity sides")
        from .labels import jev_answers
        pre_tier = F.when(near, 0).when(big, 1).otherwise(2)
        todo = base.orderBy(pre_tier, "distance", disagree, "l_id", "r_id").limit(n_llm).select("l_id", "r_id")
        answers, usage = jev_answers(cfg, todo, left, right)
        word = {1.0: "same", 0.0: "different"}
        rows = [(a["l_id"], a["r_id"], word.get(a["label"], "unsure"), float(a["probs"][-1]) if a["probs"] else None)
                for a in answers if a["probs"]]
        opinions = spark.createDataFrame(rows, "l_id string, r_id string, llm_label string, llm_p_same double")
        stats["llm_usage"] = usage
    q = base.join(opinions, ["l_id", "r_id"], "left")
    reason = (F.when(F.col("llm_label") == "unsure", "llm_unsure").when(near, "near_threshold")
              .when(big, "high_impact").otherwise("other"))
    q = q.withColumn("queue_reason", reason)
    tier = F.when(F.col("queue_reason").isin("llm_unsure", "near_threshold"), 0) \
        .when(F.col("queue_reason") == "high_impact", 1).otherwise(2)
    within = F.when(tier == 0, F.when(F.col("queue_reason") == "llm_unsure", 0).otherwise(1)) \
        .when(tier == 1, -F.col("impact")).otherwise(0)
    keys = ["_t", "_w", "distance", "_d", "l_id", "r_id"]
    top = q.withColumn("_t", tier).withColumn("_w", within).withColumn("_d", disagree).orderBy(*keys) \
        .limit(cfg.get("review.max_pairs"))
    w = Window.orderBy(*keys)
    lid, rid = cfg.get("inputs.left.id"), cfg.get("inputs.right.id")
    top = (top.withColumn("rank", F.row_number().over(w)).drop("_t", "_w", "_d")
           .join(_records(raws["left"], lid, cfg, "l"), "l_id", "left")
           .join(_records(raws["right"], rid, cfg, "r"), "r_id", "left")
           .withColumn("threshold", thr).withColumn("model_version", F.lit(str(model_version)))
           .withColumn("run_id", F.lit(str(run_id))).withColumn("created_at", F.current_timestamp())
           .select(*QUEUE_COLUMNS))
    by_reason = {r.queue_reason: r["count"] for r in top.groupBy("queue_reason").count().collect()}
    stats.update({"pairs": sum(by_reason.values()), "by_reason": dict(sorted(by_reason.items()))})
    return top, stats


def run_record(*, run_id: str, model_version: str, threshold: float, summary: dict, queue_stats: dict,
               cfg: Config) -> dict:
    """One row of the run history (RUN_COLUMNS) from a run's summary."""
    ev = (summary.get("evaluation") or {}).get("all")
    app = (summary.get("labels") or {}).get("app") or {}
    llm = queue_stats.get("llm_usage") or {}
    return {
        "run_id": str(run_id), "model_version": str(model_version),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "threshold": float(threshold),
        "evaluation": "truth" if ev else "none",
        "precision": ev["precision"] if ev else None, "recall": ev["recall"] if ev else None,
        "f1": ev["f1"] if ev else None,
        "candidates": (summary.get("candidates") or {}).get("pairs"), "links": (summary.get("decision") or {}).get("links"),
        "labels_train": (summary.get("labels") or {}).get("train"),
        "labels_validation": (summary.get("labels") or {}).get("validation"),
        "label_source": cfg.get("labels.source"), "app_labels_used": app.get("used", 0),
        "label_set_sha256": ((summary.get("mlflow") or {}).get("label_set") or {}).get("sha256"),
        "quarantined_left": (summary.get("quarantined") or {}).get("left", 0),
        "quarantined_right": (summary.get("quarantined") or {}).get("right", 0),
        "queue_pairs": queue_stats.get("pairs", 0), "queue_by_reason": json.dumps(queue_stats.get("by_reason", {})),
        "llm": queue_stats.get("llm"), "llm_usd": llm.get("usd"),
    }


def ensure_label_table(spark: SparkSession, cfg: Config) -> str | None:
    """Databricks: create the (empty) Delta label table if it is missing, so the app never needs CREATE TABLE.
    Not for a Lakebase store (the app's database owns that table)."""
    from .labels import store
    loc = store.location(cfg)
    if "table" not in loc or cfg.get("paid_features.lakebase_label_store"):
        return None
    cols = ", ".join(f"{n} {t.upper()}" for n, t in store.STORE_COLUMNS)
    spark.sql(f"CREATE TABLE IF NOT EXISTS {loc['table']} ({cols}) USING DELTA "
              "COMMENT 'lakematch arbitration app: append-only label decisions (labels/store.py)'")
    return loc["table"]


def write(spark: SparkSession, cfg: Config, queue: DataFrame, record: dict) -> dict:
    """Queue overwritten, run history appended. Returns where both went."""
    rec = spark.createDataFrame([tuple(record[n] for n, _ in RUN_COLUMNS)], ", ".join(f"{n} {t}" for n, t in RUN_COLUMNS))
    if cfg.get("storage.catalog"):
        queue.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(_table(cfg, QUEUE_TABLE))
        rec.write.mode("append").saveAsTable(_table(cfg, RUNS_TABLE))
        return {"queue": _table(cfg, QUEUE_TABLE), "runs": _table(cfg, RUNS_TABLE),
                "labels": ensure_label_table(spark, cfg)}
    root = Path(cfg.path(cfg.get("storage.root"))) / "review"
    root.mkdir(parents=True, exist_ok=True)
    queue.write.mode("overwrite").parquet(str(root / "queue"))
    with (root / "runs.jsonl").open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return {"queue": str(root / "queue"), "runs": str(root / "runs.jsonl")}
