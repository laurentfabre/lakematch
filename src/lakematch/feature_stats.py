"""Native training IDF: log((N+1)/(df+1))+1; empty documents count in N.

Fit only declared training records. Unseen tokens use df=0. An empty-string
sentinel stores that weight and is never a token. Save the vocabulary with models.
"""
from functools import reduce

from pyspark.sql import functions as F

from .similarity import tokens


def _long(frame, config):
    fields = F.array(*[F.struct(F.lit(n).alias("field"), tokens(
        F.substring(F.col(n), 1, config["features"]["max_chars"]), config["features"]["max_tokens"]).alias("tokens"))
        for n in config.fields])
    return frame.select("rec_id", F.explode(fields).alias("item")).select("rec_id", "item.*")


def fit_idf(frames, config):
    docs = reduce(lambda a, b: a.unionByName(b), [_long(f, config) for f in frames])
    totals = docs.groupBy("field").agg(F.count("rec_id").alias("n"))
    frequency = docs.select("field", F.explode("tokens").alias("token")).groupBy("field", "token").count()
    known = frequency.join(totals, "field").select("field", "token", (F.log((F.col("n") + 1) / (F.col("count") + 1)) + 1).alias("idf"))
    unseen = totals.select("field", F.lit("").alias("token"), (F.log(F.col("n") + 1) + 1).alias("idf"))
    return known.unionByName(unseen)


def attach_idf(frame, vocabulary, config):
    oov = vocabulary.filter(F.col("token") == "").select("field", F.col("idf").alias("unseen"))
    exploded = _long(frame, config).select("rec_id", "field", F.explode_outer("tokens").alias("token"))
    weighted = exploded.join(vocabulary, ["field", "token"], "left").join(oov, "field", "left")
    empty_map = F.create_map().cast("map<string,double>")
    maps = weighted.groupBy("rec_id", "field").agg(F.map_from_entries(F.collect_list(F.when(F.col("token").isNotNull(),
        F.struct("token", F.coalesce("idf", "unseen").alias("weight"))))).alias("weights"))
    wide = maps.groupBy("rec_id").agg(*[F.first(F.when(F.col("field") == name, F.col("weights")), ignorenulls=True)
        .alias(f"lm_weights_{name}") for name in config.fields])
    joined = frame.join(wide, "rec_id", "left")
    for name in config.fields:
        joined = joined.withColumn(f"lm_weights_{name}", F.coalesce(F.col(f"lm_weights_{name}"), empty_map))
    return joined
