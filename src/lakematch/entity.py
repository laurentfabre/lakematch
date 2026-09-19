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
    expressions = []
    for name, spec in config["entity"]["fields"].items():
        raw = F.col(name)
        if spec.get("multiple"):
            values = F.array_distinct(F.filter(F.transform(raw, normalize), lambda x: F.length(x) > 0))
            values = F.coalesce(values, F.array().cast("array<string>"))
            expressions += [F.concat_ws(" ", values).alias(name), values.alias(f"lm_values_{name}")]
        else:
            expressions.append(normalize(raw).alias(name))
        if spec["type"] in {"date", "number"}:
            # Typed comparisons must retain signs, decimal points and date separators.
            expressions.append(F.trim(raw.cast("string")).alias(f"lm_raw_{name}"))
    return frame.select(F.col(config["entity"]["id_column"]).cast("string").alias("rec_id"), *expressions)
