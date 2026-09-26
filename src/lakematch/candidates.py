"""Candidate pairs: a cheap first step that proposes, for each left record, a short list of right records worth scoring.

`gram_topk` (the starting default, D06) — IDF-weighted cosine over character q-gram sets, top-k per left record:

    vocabulary  every q-gram of either side, minus the "ubiquitous" ones present in more than `gram_cap` right records
    weight      w(g) = ln((1 + N) / (1 + df(g))) + 1 with N = |left| + |right| and df(g) = records holding g on
                either side (smoothed IDF, always > 0); `idf_weighted: false` sets w(g) = 1 (plain set cosine)
    score       cos(l, r) = sum_{g in l ∩ r} w(g)^2 / (||l|| · ||r||), both norms over the *same* vocabulary — a real
                cosine between two IDF vectors, not an overlap masked by the cap divided by unmasked norms
    keep        the k best right records per left record, ties broken by right id (deterministic)

Candidate budget. The only quadratic step is the join on shared grams. A kept gram is held by at most `gram_cap`
right records, so a left record with G grams reaches at most G × gram_cap right rows before aggregation, and the join
emits at most sum_l G_l × gram_cap rows in total; the output is exactly min(k, reachable) pairs per left record.
Lowering `gram_cap` bounds the join harder at the cost of candidate recall — `lakematch doctor` prints the bound.

Output columns: l_id, r_id, cand_score, cand_rank (1 = best), cand_gap (best score of this left record − this one).
The other methods are valid config choices that land in ZR-3.
"""
from __future__ import annotations

from pyspark.sql import DataFrame, Window, functions as F

from .config import Config


def gram_topk(left: DataFrame, right: DataFrame, cfg: Config) -> DataFrame:
    k, cap, weighted = cfg.get("candidates.k"), cfg.get("candidates.gram_cap"), cfg.get("candidates.idf_weighted")
    el = left.select(F.col("id").alias("l_id"), F.explode("_grams").alias("gram"))
    er = right.select(F.col("id").alias("r_id"), F.explode("_grams").alias("gram"))
    df_l = el.groupBy("gram").agg(F.count(F.lit(1)).alias("df_l"))
    df_r = er.groupBy("gram").agg(F.count(F.lit(1)).alias("df_r"))
    sizes = left.agg(F.count(F.lit(1)).alias("n_l")).crossJoin(right.agg(F.count(F.lit(1)).alias("n_r")))
    vocab = (df_l.join(df_r, "gram", "full").fillna(0, ["df_l", "df_r"])
                 .filter(F.col("df_r") <= cap)                                    # drop ubiquitous grams
                 .crossJoin(sizes))
    if weighted:
        w = F.log((1 + F.col("n_l") + F.col("n_r")) / (1 + F.col("df_l") + F.col("df_r"))) + 1
    else:
        w = F.lit(1.0)
    vocab = vocab.select("gram", w.alias("w"))
    wl = el.join(vocab, "gram")
    wr = er.join(vocab, "gram")
    norm_l = wl.groupBy("l_id").agg(F.sqrt(F.sum(F.col("w") * F.col("w"))).alias("norm_l"))
    norm_r = wr.groupBy("r_id").agg(F.sqrt(F.sum(F.col("w") * F.col("w"))).alias("norm_r"))
    dot = (wl.join(wr.select("r_id", "gram"), "gram")
             .groupBy("l_id", "r_id").agg(F.sum(F.col("w") * F.col("w")).alias("dot")))
    scored = (dot.join(norm_l, "l_id").join(norm_r, "r_id")
                 .select("l_id", "r_id", (F.col("dot") / (F.col("norm_l") * F.col("norm_r"))).alias("cand_score")))
    by_left = Window.partitionBy("l_id").orderBy(F.desc("cand_score"), F.asc("r_id"))
    return (scored.withColumn("cand_rank", F.row_number().over(by_left)).filter(F.col("cand_rank") <= k)
                  .withColumn("cand_gap", F.max("cand_score").over(Window.partitionBy("l_id")) - F.col("cand_score")))


def generate(left: DataFrame, right: DataFrame, cfg: Config) -> DataFrame:
    method = cfg.require("candidates.method")
    return {"gram_topk": gram_topk}[method](left, right, cfg)


def budget_note(cfg: Config) -> str:
    return (f"gram_topk: join rows <= sum over left records of (grams per record x {cfg.get('candidates.gram_cap')}); "
            f"output <= {cfg.get('candidates.k')} pairs per left record")
