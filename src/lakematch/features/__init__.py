"""Comparison vector for each candidate pair. Every default feature is a Spark SQL built-in expression — no UDF.

Per field (a missing value on either side gives -1, so the classifier can learn "unknown" apart from "different"):

    every type                     lev_<f>   1 - levenshtein / max length (features.string_similarity: levenshtein)
                                   eq_<f>    exact equality after normalisation
    person_name                    sdx_<f>   soundex agreement
    address, organisation, title   the `features.multi_token` choices:
        idf_token_cosine  itc_<f>  cosine of IDF-weighted token sets (weights from both sides; see token_weights)
        gram_overlap      gov_<f>  Jaccard of the field's character q-gram sets
        monge_elkan_token mek_<f>  symmetric token-level Monge-Elkan, generalised mean m = 2 (Jimenez 2009), inner
                                   similarity = normalised levenshtein between tokens
Per pair: cand_score, cand_rank, cand_gap from the candidate step.

Jaro-Winkler, the affine-gap alignment and embeddings are ZR-2; `embeddings.provider: auto` skips the embedding
feature with a warning while no local provider is installed, which is always the case before ZR-2.
"""
from __future__ import annotations

import logging

from pyspark.sql import Column, DataFrame, functions as F

from ..config import Config
from ..entity import MULTI_TOKEN_TYPES, qgrams

log = logging.getLogger("lakematch")
MISSING = -1.0


def _norm_lev(a: Column, b: Column) -> Column:
    return 1 - F.levenshtein(a, b) / F.greatest(F.length(a), F.length(b))


def _present(a: Column, b: Column) -> Column:
    return (F.length(a) > 0) & (F.length(b) > 0)


def token_weights(left: DataFrame, right: DataFrame, field: str) -> tuple[DataFrame, DataFrame]:
    """Add `tw_<field>`: the record's distinct tokens -> smoothed IDF weight, scaled to unit length (a map)."""
    tok = f"tok_{field}"
    both = (left.select(F.explode(F.array_distinct(tok)).alias("t"))
                .unionAll(right.select(F.explode(F.array_distinct(tok)).alias("t"))))
    n = left.agg(F.count(F.lit(1)).alias("n_l")).crossJoin(right.agg(F.count(F.lit(1)).alias("n_r")))
    idf = (both.groupBy("t").agg(F.count(F.lit(1)).alias("df")).crossJoin(n)
               .select("t", (F.log((1 + F.col("n_l") + F.col("n_r")) / (1 + F.col("df"))) + 1).alias("w")))

    def add(side: DataFrame) -> DataFrame:
        weights = (side.select("id", F.explode(F.array_distinct(tok)).alias("t")).join(idf, "t")
                       .groupBy("id").agg(F.map_from_entries(F.collect_list(F.struct("t", "w"))).alias("m"),
                                          F.sqrt(F.sum(F.col("w") * F.col("w"))).alias("norm"))
                       .select("id", F.transform_values("m", lambda _, v: v / F.col("norm")).alias(f"tw_{field}")))
        return side.join(weights, "id", "left")
    return add(left), add(right)


def prepare_sides(left: DataFrame, right: DataFrame, cfg: Config) -> tuple[DataFrame, DataFrame]:
    """Record-level work done once per record, before pairs exist."""
    multi = cfg.fields_of_type(*MULTI_TOKEN_TYPES)
    if "idf_token_cosine" in cfg.get("features.multi_token"):
        for f in multi:
            left, right = token_weights(left, right, f)
    if "gram_overlap" in cfg.get("features.multi_token"):
        q = cfg.get("candidates.q")
        for f in multi:
            left, right = left.withColumn(f"qg_{f}", qgrams(F.col(f), q)), right.withColumn(f"qg_{f}", qgrams(F.col(f), q))
    return left, right


def _monge_elkan(ta: Column, tb: Column) -> Column:
    def directed(xs: Column, ys: Column) -> Column:
        best = F.transform(xs, lambda x: F.pow(F.array_max(F.transform(ys, lambda y: _norm_lev(x, y))), 2))
        return F.sqrt(F.aggregate(best, F.lit(0.0), lambda acc, v: acc + v) / F.size(xs))
    return F.when((F.size(ta) > 0) & (F.size(tb) > 0), (directed(ta, tb) + directed(tb, ta)) / 2).otherwise(MISSING)


def _idf_cosine(ma: Column, mb: Column) -> Column:
    shared = F.array_intersect(F.map_keys(ma), F.map_keys(mb))
    dot = F.aggregate(shared, F.lit(0.0), lambda acc, t: acc + ma[t] * mb[t])
    return F.when(ma.isNotNull() & mb.isNotNull(), dot).otherwise(MISSING)


def _jaccard(ga: Column, gb: Column) -> Column:
    union = F.size(F.array_union(ga, gb))
    return F.when((F.size(ga) > 0) & (F.size(gb) > 0), F.size(F.array_intersect(ga, gb)) / union).otherwise(MISSING)


def check(cfg: Config) -> None:
    cfg.require("features.string_similarity")
    for choice in cfg.get("features.multi_token"):
        cfg.require("features.multi_token", choice)
    provider = cfg.require("features.embeddings.provider")
    if provider == "auto" and cfg.fields_of_type(*cfg.get("features.embeddings.fields_of_type")):
        log.warning("embeddings: provider auto found no local embedding provider (it lands in ZR-2) — "
                    "the embedding feature is skipped for %s", ", ".join(cfg.fields_of_type(
                        *cfg.get("features.embeddings.fields_of_type"))))


def compare(pairs: DataFrame, cfg: Config) -> tuple[DataFrame, list[str]]:
    """`pairs` holds l_<col> and r_<col> for every entity column; returns it with the feature columns added."""
    check(cfg)
    feats = ["cand_score", "cand_rank", "cand_gap"]
    cols = {}
    multi = cfg.get("features.multi_token")
    for f, spec in cfg.fields.items():
        a, b = F.col(f"l_{f}"), F.col(f"r_{f}")
        ok = _present(a, b)
        cols[f"lev_{f}"] = F.when(ok, _norm_lev(a, b)).otherwise(MISSING)
        cols[f"eq_{f}"] = F.when(ok, (a == b).cast("double")).otherwise(MISSING)
        if spec["type"] == "person_name":
            cols[f"sdx_{f}"] = F.when(ok, (F.soundex(a) == F.soundex(b)).cast("double")).otherwise(MISSING)
        if spec["type"] in MULTI_TOKEN_TYPES:
            if "idf_token_cosine" in multi:
                cols[f"itc_{f}"] = _idf_cosine(F.col(f"l_tw_{f}"), F.col(f"r_tw_{f}"))
            if "gram_overlap" in multi:
                cols[f"gov_{f}"] = _jaccard(F.col(f"l_qg_{f}"), F.col(f"r_qg_{f}"))
            if "monge_elkan_token" in multi:
                cols[f"mek_{f}"] = _monge_elkan(F.col(f"l_tok_{f}"), F.col(f"r_tok_{f}"))
    out = pairs.withColumns({k: v.cast("double") for k, v in cols.items()})
    out = out.withColumn("cand_rank", F.col("cand_rank").cast("double"))
    return out, feats + list(cols)
