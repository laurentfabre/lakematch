"""Lazy normalization and character grams using public Spark expressions."""
from pyspark.sql import functions as F


def normalize(value):
    # Preserve Unicode letters and numbers; punctuation and whitespace delimit tokens.
    return F.trim(F.regexp_replace(F.lower(F.coalesce(value.cast("string"), F.lit(""))), r"[^\p{L}\p{N}]+", " "))


def grams(value, q):
    empty = F.array().cast("array<string>")
    return F.when(F.length(value) == 0, empty).when(F.length(value) < q, F.array(value)).otherwise(
        F.array_distinct(F.transform(F.sequence(F.lit(1), F.length(value) - q + 1),
                                   lambda i: F.substring(value, i, q))))


def prepare(frame, config):
    return frame.select(F.col(config["entity"]["id_column"]).cast("string").alias("rec_id"),
                        *[normalize(F.col(name)).alias(name) for name in config.fields])
