"""IDF-weighted set cosine, with budgets checked BEFORE the exploded join.

Vocabulary is the union of both sides. A gram survives only if document frequency
on each side <= gram_cap. Weight = log((N+1)/(df+1))+1, so the dot product and both
norms use squared IDF over the SAME retained vocabulary. Side-only grams remain in
the norm. This fixes the prototype's masked numerator / unmasked denominator.
"""
from dataclasses import dataclass

from pyspark.sql import DataFrame, Window, functions as F

from .config import MethodUnavailable
from .entity import grams


class CandidateBudgetExceeded(RuntimeError):
    pass


@dataclass
class CandidatePlan:
    pairs: DataFrame
    diagnostics: DataFrame
    max_join_rows: int
    max_pairs: int

    def validate_budget(self):
        """Job-time action; flows consume plans only after this task succeeds."""
        report = self.diagnostics.first().asDict()
        if report["join_rows_after_cap"] > self.max_join_rows:
            raise CandidateBudgetExceeded(f"Pre-top-k join budget exceeded: {report}; limit={self.max_join_rows}")
        n = self.pairs.limit(self.max_pairs + 1).count()
        if n > self.max_pairs:
            raise CandidateBudgetExceeded(f"Candidate pair budget exceeded: >{self.max_pairs}")
        return {**report, "candidate_pairs": n, "max_join_rows": self.max_join_rows, "max_pairs": self.max_pairs}


def build(left, right, config):
    spec = config["candidates"]
    if spec["method"] != "gram_topk":
        raise MethodUnavailable(f"Candidate method {spec['method']} requires ZR-3")
    q, cap = spec["q"], spec["gram_cap"]
    def explode(frame, id_name):
        return frame.select(F.col("rec_id").alias(id_name),
                            F.explode(grams(F.trim(F.concat_ws(" ", *config.fields)), q)).alias("gram"))
    a, b = explode(left, "a_id"), explode(right, "b_id")
    da, db = a.groupBy("gram").count().withColumnRenamed("count", "da"), b.groupBy("gram").count().withColumnRenamed("count", "db")
    stats = da.join(db, "gram", "full").fillna(0, ["da", "db"])
    kept = (F.col("da") <= cap) & (F.col("db") <= cap)
    diagnostics = stats.agg(
        F.coalesce(F.sum(F.col("da") * F.col("db")), F.lit(0)).alias("join_rows_before_cap"),
        F.coalesce(F.sum(F.when(kept, F.col("da") * F.col("db")).otherwise(0)), F.lit(0)).alias("join_rows_after_cap"),
        F.coalesce(F.sum(F.when(~kept, 1).otherwise(0)), F.lit(0)).alias("dropped_grams"))
    total = left.agg(F.count("rec_id").alias("nl")).crossJoin(right.agg(F.count("rec_id").alias("nr")))
    vocabulary = stats.filter(kept).crossJoin(total).select("gram", (
        F.pow(F.log((F.col("nl") + F.col("nr") + 1) / (F.col("da") + F.col("db") + 1)) + 1, 2)
        if spec["idf_weighted"] else F.lit(1.0)).alias("weight2"))
    ga, gb = a.join(vocabulary, "gram"), b.join(vocabulary.select("gram"), "gram")
    norms_a = ga.groupBy("a_id").agg(F.sum("weight2").alias("norm_a2"))
    norms_b = gb.join(vocabulary, "gram").groupBy("b_id").agg(F.sum("weight2").alias("norm_b2"))
    # This scalar guard also protects direct lazy-plan consumers; the runner validates
    # the same diagnostic before triggering this plan so it never relies on top-k.
    guard = diagnostics.select(F.when(F.col("join_rows_after_cap") <= spec["max_join_rows"], True)
                               .otherwise(F.raise_error("Candidate pre-top-k join budget exceeded")).alias("lm_budget_ok"))
    guarded_a = ga.crossJoin(guard).filter("lm_budget_ok").drop("lm_budget_ok")
    pairs = (guarded_a.join(gb, "gram").groupBy("a_id", "b_id").agg(F.sum("weight2").alias("dot"))
             .join(norms_a, "a_id").join(norms_b, "b_id")
             .withColumn("cos", F.least(F.lit(1.0), F.col("dot") / F.sqrt(F.col("norm_a2") * F.col("norm_b2")))))
    window = Window.partitionBy("a_id").orderBy(F.desc("cos"), "b_id")
    pairs = (pairs.withColumn("rank", F.row_number().over(window)).filter(F.col("rank") <= spec["k"])
             .withColumn("gap", F.max("cos").over(Window.partitionBy("a_id")) - F.col("cos"))
             .select("a_id", "b_id", "cos", "rank", "gap"))
    return CandidatePlan(pairs, diagnostics, spec["max_join_rows"], spec["max_pairs"])
