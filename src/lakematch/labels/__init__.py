"""Labelled pairs for training and threshold selection.

    labels.source: file          a CSV or Parquet of (l_id, r_id, is_match) written by a person or a tool
    labels.source: truth_sample  benchmarks only: `labels.n` candidate pairs drawn in a fixed pseudo-random order
                                 (xxhash64 of the pair) and labelled from evaluation.truth
    labels.source: app           the arbitration app's label store (ZR-7)
    labels.llm                   the LLM labeller plug-in: none, jev (labels/jev.py; ai_query lands in ZR-6). With
                                 jev, the same `labels.n` sample is labelled by Jev instead of a truth file; only its
                                 confident answers (labels.llm_tau) become labels

`split()` separates training and validation labels *by left record*, so no left record contributes to both sides.
"""
from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession, functions as F

from ..config import Config
from ..io import read_table


def truth_pairs(spark: SparkSession, cfg: Config) -> DataFrame | None:
    spec = cfg.get("evaluation.truth")
    if not spec:
        return None
    df = read_table(spark, cfg, spec)
    return df.select(F.col(spec.get("left_id", "l_id")).cast("string").alias("l_id"),
                     F.col(spec.get("right_id", "r_id")).cast("string").alias("r_id")).distinct()


def sample(features: DataFrame, cfg: Config) -> DataFrame:
    """`labels.n` candidate pairs in a fixed pseudo-random order (xxhash64 of the pair)."""
    return features.orderBy(F.xxhash64("l_id", "r_id"), "l_id", "r_id").limit(cfg.get("labels.n"))


def llm_labelled(spark: SparkSession, features: DataFrame, cfg: Config, left: DataFrame, right: DataFrame,
                 pairs: DataFrame | None = None) -> tuple[DataFrame, dict]:
    """Jev's confident labels on `pairs` (default: the `labels.n` sample). Returns (labelled pairs, usage)."""
    from . import jev
    fields = list(cfg.fields)
    todo = (sample(features, cfg) if pairs is None else pairs).select("l_id", "r_id")
    rec = lambda side, p: side.select(F.col("id").alias(f"{p}_id"), F.struct(*fields).alias(f"{p}_rec"))
    rows = todo.join(rec(left, "l"), "l_id").join(rec(right, "r"), "r_id").orderBy("l_id", "r_id").collect()
    asked = [{"l_id": r.l_id, "r_id": r.r_id, "record_a": r.l_rec.asDict(), "record_b": r.r_rec.asDict()} for r in rows]
    name = cfg.get("entity.name")
    what = (f"two {name} records from two sources; a duplicate may carry typos, abbreviations, missing, reordered "
            "or swapped fields")
    cache = cfg.path(cfg.get("labels.llm_cache")) or cfg.path(cfg.get("storage.root")) / "jev_cache.jsonl"
    answers, usage = jev.ask(asked, what, name, cache, tau=cfg.get("labels.llm_tau"),
                             max_usd=cfg.get("labels.llm_max_usd"))
    kept = [(a["l_id"], a["r_id"], a["label"]) for a in answers if a["label"] is not None]
    usage.update({"asked": len(asked), "kept": len(kept)})
    lab = spark.createDataFrame(kept, "l_id string, r_id string, label double")
    return features.join(lab, ["l_id", "r_id"]), usage


def labelled(spark: SparkSession, features: DataFrame, cfg: Config, left: DataFrame | None = None,
             right: DataFrame | None = None, usage: dict | None = None) -> DataFrame:
    """The candidate pairs that carry a label, with a double `label` column. `left`/`right` (entity sides) are
    needed by an LLM labeller, which reads the records; its usage (predicted and actual cost) lands in `usage`."""
    if cfg.require("labels.llm") == "jev":
        if left is None or right is None:
            raise ValueError("labels.llm: jev needs the entity sides")
        lab, used = llm_labelled(spark, features, cfg, left, right)
        if usage is not None:
            usage.update(used)
        return lab
    source = cfg.require("labels.source")
    if source == "truth_sample":
        truth = truth_pairs(spark, cfg)
        if truth is None:
            raise ValueError("labels.source: truth_sample needs evaluation.truth")
        hits = truth.withColumn("label", F.lit(1.0))
        return sample(features, cfg).join(hits, ["l_id", "r_id"], "left").fillna(0.0, ["label"])
    spec = {"path": cfg.get("labels.path")}
    lab = read_table(spark, cfg, spec).select(F.col("l_id").cast("string"), F.col("r_id").cast("string"),
                                              F.col("is_match").cast("double").alias("label"))
    return features.join(lab, ["l_id", "r_id"])


def split(labels: DataFrame, cfg: Config) -> tuple[DataFrame, DataFrame]:
    """(train, validation) by a hash of the left id: stable across runs and free of shared anchors."""
    cut = int(cfg.get("decision.validation_share") * 1000)
    bucket = F.pmod(F.xxhash64("l_id"), F.lit(1000))
    return labels.filter(bucket >= cut), labels.filter(bucket < cut)
