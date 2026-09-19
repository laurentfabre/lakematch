"""Deterministic cardinality policies (one-to-one uses conservative mutual best).

This is deliberately not a maximum-weight bipartite solver: a losing anchor is
rejected, not reassigned to its runner-up. ZR-3 must measure that recall tradeoff.
"""
from pyspark.sql import Window, functions as F


def links(scored, config, *, threshold=None):
    threshold = config["decision"]["threshold"] if threshold is None else threshold
    if threshold == "from_validation":
        raise ValueError("No frozen validation threshold: train/select it first, or set an explicit threshold")
    selected = scored.filter(F.col("p").isNotNull() & ~F.isnan("p") & (F.col("p") >= threshold)).select("a_id", "b_id", "p")
    # Duplicate candidates are collapsed before cardinality windows.
    selected = selected.groupBy("a_id", "b_id").agg(F.max("p").alias("p"))
    mode = config["decision"]["cardinality"]
    if mode in {"one_to_one", "many_to_one"}:
        selected = selected.withColumn("lm_rank_a", F.row_number().over(
            Window.partitionBy("a_id").orderBy(F.desc("p"), "b_id"))).filter("lm_rank_a = 1").drop("lm_rank_a")
    if mode == "one_to_one":
        selected = selected.withColumn("lm_rank_b", F.row_number().over(
            Window.partitionBy("b_id").orderBy(F.desc("p"), "a_id"))).filter("lm_rank_b = 1").drop("lm_rank_b")
    return selected
