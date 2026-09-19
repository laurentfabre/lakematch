"""ZR-1 comparison vector. Additional type-specific families land in ZR-2."""
from pyspark.sql import functions as F


def feature_order(config):
    return ["cos", "rank", "gap"] + [f"{metric}_{name}" for name in config.fields for metric in ("lev", "eq", "sdx", "missing")]


def build(pairs, left, right, config):
    config.require_implemented()
    a = left.select(F.col("rec_id").alias("a_id"), *[F.col(n).alias(f"l_{n}") for n in config.fields])
    b = right.select(F.col("rec_id").alias("b_id"), *[F.col(n).alias(f"r_{n}") for n in config.fields])
    joined = pairs.join(a, "a_id").join(b, "b_id")
    expressions = []
    for name in config.fields:
        l, r = F.col(f"l_{name}"), F.col(f"r_{name}")
        both = (F.length(l) > 0) & (F.length(r) > 0)
        expressions.extend([
            F.when(both, 1 - F.levenshtein(l, r) / F.greatest(F.length(l), F.length(r))).otherwise(-1.0).alias(f"lev_{name}"),
            F.when(both, (l == r).cast("double")).otherwise(-1.0).alias(f"eq_{name}"),
            F.when(both, (F.soundex(l) == F.soundex(r)).cast("double")).otherwise(-1.0).alias(f"sdx_{name}"),
            (~both).cast("double").alias(f"missing_{name}"),
        ])
    return joined.select("a_id", "b_id", "cos", "rank", "gap", *expressions)
