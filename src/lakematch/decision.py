"""From scored pairs to links: a threshold and an explicit cardinality policy.

    decision.threshold    a probability, or from_validation: the threshold that maximises pair-level F1 on the
                          validation labels (grid 0.05..0.95 by 0.01; ties go to the value closest to 0.5)
    decision.cardinality
        unrestricted      every pair with p >= threshold
        many_to_one       each left record keeps its best right record (several left records may share a right one)
        one_to_one        each left record keeps its best right record, then each right record keeps its best left
                          record among those; a left record whose best partner was taken is not re-assigned
Ties are broken on ids (right id for a left record, left id for a right record): the same input gives the same links.
"""
from __future__ import annotations

import logging

from pyspark.sql import DataFrame, Window, functions as F

from .config import Config

log = logging.getLogger("lakematch")


def pick_threshold(validation_scored: DataFrame, cfg: Config) -> float:
    fixed = cfg.get("decision.threshold")
    if fixed != "from_validation":
        return float(fixed)
    rows = validation_scored.select("p", "label").collect()     # a few hundred labelled pairs at most
    positives = sum(1 for r in rows if r["label"] == 1.0)
    if not positives:
        log.warning("decision: no positive validation label — threshold falls back to 0.5")
        return 0.5
    best, best_key = 0.5, None
    for i in range(5, 96):
        t = i / 100
        tp = sum(1 for r in rows if r["p"] >= t and r["label"] == 1.0)
        fp = sum(1 for r in rows if r["p"] >= t and r["label"] != 1.0)
        f1 = 2 * tp / (2 * tp + fp + (positives - tp))
        key = (f1, -abs(t - 0.5))
        if best_key is None or key > best_key:
            best, best_key = t, key
    return best


def links(scored: DataFrame, threshold: float, cfg: Config, columns: list[str] | None = None) -> DataFrame:
    """With `columns`, the result is exactly those columns, selected by name: no drop() of the helper columns
    (Spark Connect plans drop() by analysing its input, which a pipeline flow cannot afford)."""
    policy = cfg.require("decision.cardinality")
    finish = (lambda df: df.select(*columns)) if columns else (lambda df: df.drop(*[c for c in ("_r", "_l")
                                                                                      if c in df.columns]))
    kept = scored.filter(F.col("p") >= threshold)
    if policy == "unrestricted":
        return kept.select(*columns) if columns else kept
    best_r = Window.partitionBy("l_id").orderBy(F.desc("p"), F.asc("r_id"))
    kept = kept.withColumn("_r", F.row_number().over(best_r)).filter("_r = 1")
    if policy == "many_to_one":
        return finish(kept)
    best_l = Window.partitionBy("r_id").orderBy(F.desc("p"), F.asc("l_id"))
    return finish(kept.withColumn("_l", F.row_number().over(best_l)).filter("_l = 1"))
