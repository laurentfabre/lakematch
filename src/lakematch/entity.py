"""Entity view: one row per record with normalised fields, tokens and the character q-grams candidates are built on.

All Spark SQL built-ins, all lazy. Normalisation depends on the field type:

    person_name, address, organisation, title   lower case, punctuation -> space, spaces collapsed
    code                                        lower case, everything but letters and digits removed
    date, number                                trimmed

Output columns: `id` (string), one column per configured field (normalised string, '' when missing),
`tok_<field>` for multi-token field types, and `_grams` (distinct q-grams of all fields joined by a space).
"""
from __future__ import annotations

from pyspark.sql import Column, DataFrame, functions as F

from .config import Config

TEXT_TYPES = ("person_name", "address", "organisation", "title")
MULTI_TOKEN_TYPES = ("address", "organisation", "title")


def normalise(col: Column, ftype: str) -> Column:
    s = F.coalesce(col.cast("string"), F.lit(""))
    if ftype in TEXT_TYPES:
        s = F.regexp_replace(F.lower(s), r"[^\p{L}\p{N}]+", " ")
        return F.trim(F.regexp_replace(s, r"\s+", " "))
    if ftype == "code":
        return F.regexp_replace(F.lower(s), r"[^\p{L}\p{N}]", "")
    return F.trim(s)


def tokens(col: Column) -> Column:
    return F.filter(F.split(col, " "), lambda t: F.length(t) > 0)


def qgrams(text: Column, q: int) -> Column:
    """Distinct character q-grams of `text`; a text shorter than q yields itself."""
    idx = F.sequence(F.lit(1), F.greatest(F.length(text) - q + 1, F.lit(1)))
    return F.array_distinct(F.filter(F.transform(idx, lambda i: F.substring(text, i, q)), lambda g: F.length(g) > 0))


def prepare(df: DataFrame, cfg: Config, id_column: str) -> DataFrame:
    fields = cfg.fields
    missing = [c for c in [id_column, *fields] if c not in df.columns]
    if missing:
        raise ValueError(f"input lacks column(s) {', '.join(missing)}")
    cols = [F.col(id_column).cast("string").alias("id")]
    cols += [normalise(F.col(name), spec["type"]).alias(name) for name, spec in fields.items()]
    out = df.select(*cols)
    for name, spec in fields.items():
        if spec["type"] in MULTI_TOKEN_TYPES:
            out = out.withColumn(f"tok_{name}", tokens(F.col(name)))
    text = F.concat_ws(" ", *[F.col(n) for n in fields])
    return out.withColumn("_grams", qgrams(text, cfg.get("candidates.q")))
