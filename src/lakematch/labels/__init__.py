"""Labelled pairs for training and threshold selection.

    labels.source: file          a CSV or Parquet of (l_id, r_id, is_match) written by a person or a tool
    labels.source: truth_sample  benchmarks only: `labels.n` candidate pairs drawn in a fixed pseudo-random order
                                 (xxhash64 of the pair) and labelled from evaluation.truth
    labels.source: app           the arbitration app's label store (ZR-7)
    labels.llm                   the LLM labeller plug-in (none today; jev in ZR-3, ai_query in ZR-6)

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


def labelled(spark: SparkSession, features: DataFrame, cfg: Config) -> DataFrame:
    """The candidate pairs that carry a label, with a double `label` column."""
    cfg.require("labels.llm")
    source = cfg.require("labels.source")
    if source == "truth_sample":
        truth = truth_pairs(spark, cfg)
        if truth is None:
            raise ValueError("labels.source: truth_sample needs evaluation.truth")
        sample = features.orderBy(F.xxhash64("l_id", "r_id"), "l_id", "r_id").limit(cfg.get("labels.n"))
        hits = truth.withColumn("label", F.lit(1.0))
        return sample.join(hits, ["l_id", "r_id"], "left").fillna(0.0, ["label"])
    spec = {"path": cfg.get("labels.path")}
    lab = read_table(spark, cfg, spec).select(F.col("l_id").cast("string"), F.col("r_id").cast("string"),
                                              F.col("is_match").cast("double").alias("label"))
    return features.join(lab, ["l_id", "r_id"])


def split(labels: DataFrame, cfg: Config) -> tuple[DataFrame, DataFrame]:
    """(train, validation) by a hash of the left id: stable across runs and free of shared anchors."""
    cut = int(cfg.get("decision.validation_share") * 1000)
    bucket = F.pmod(F.xxhash64("l_id"), F.lit(1000))
    return labels.filter(bucket >= cut), labels.filter(bucket < cut)
