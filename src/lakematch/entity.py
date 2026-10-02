"""Entity view: one row per record with normalised fields, tokens and the character q-grams candidates are built on.

All Spark SQL built-ins, all lazy. Normalisation depends on the field type:

    person_name, address, organisation, title   lower case, punctuation -> space, spaces collapsed
    code                                        lower case, everything but letters and digits removed;
                                                with `multi: true` the raw value is a set of identifiers separated by
                                                | ; or , (e-mails, phones) and each item is normalised on its own
    date                                        lower case, tokens split at letter/digit boundaries
    number                                      trimmed

Output columns: `id` (string), one column per configured field (normalised string, '' when missing),
`tok_<field>` for the text types and dates, `set_<field>` for multi-valued codes, and `_grams` (distinct q-grams of
all fields joined by a space).
"""
from __future__ import annotations

from pyspark.sql import Column, DataFrame, functions as F

from .config import Config

TEXT_TYPES = ("person_name", "address", "organisation", "title")
MULTI_TOKEN_TYPES = ("address", "organisation", "title")
MULTI_SEPARATORS = r"\s*[|;,]\s*"


def normalise(col: Column, ftype: str) -> Column:
    s = F.coalesce(col.cast("string"), F.lit(""))
    if ftype in TEXT_TYPES:
        s = F.regexp_replace(F.lower(s), r"[^\p{L}\p{N}]+", " ")
        return F.trim(F.regexp_replace(s, r"\s+", " "))
    if ftype == "code":
        return F.regexp_replace(F.lower(s), r"[^\p{L}\p{N}]", "")
    if ftype == "date":
        s = F.regexp_replace(F.lower(s), r"(\p{L})(\p{N})", "$1 $2")        # sat1953 -> sat 1953
        s = F.regexp_replace(s, r"(\p{N})(\p{L})", "$1 $2")                  # 18sat -> 18 sat
        s = F.regexp_replace(s, r"[^\p{L}\p{N}]+", " ")
        return F.trim(F.regexp_replace(s, r"\s+", " "))
    return F.trim(s)


def tokens(col: Column) -> Column:
    return F.filter(F.split(col, " "), lambda t: F.length(t) > 0)


def code_set(col: Column) -> Column:
    """Distinct normalised identifiers of a multi-valued code field."""
    items = F.split(F.coalesce(col.cast("string"), F.lit("")), MULTI_SEPARATORS)
    items = F.transform(items, lambda x: F.regexp_replace(F.lower(x), r"[^\p{L}\p{N}]", ""))
    return F.array_sort(F.array_distinct(F.filter(items, lambda x: F.length(x) > 0)))


def qgrams(text: Column, q: int) -> Column:
    """Distinct character q-grams of `text`; a text shorter than q yields itself."""
    idx = F.sequence(F.lit(1), F.greatest(F.length(text) - q + 1, F.lit(1)))
    return F.array_distinct(F.filter(F.transform(idx, lambda i: F.substring(text, i, q)), lambda g: F.length(g) > 0))


def prepare(df: DataFrame, cfg: Config, id_column: str, check: bool = True) -> DataFrame:
    """`check: False` skips the missing-column check: it analyses the plan (df.columns), which an open-source
    pipeline flow refuses — pipelines/flows.py checks once at import instead."""
    fields = cfg.fields
    missing = [c for c in [id_column, *fields] if c not in df.columns] if check else []
    if missing:
        raise ValueError(f"input lacks column(s) {', '.join(missing)}")
    cols = [F.col(id_column).cast("string").alias("id")]
    for name, spec in fields.items():
        if spec.get("multi"):
            items = code_set(F.col(name))
            cols += [F.array_join(items, " ").alias(name), items.alias(f"set_{name}")]
        else:
            cols.append(normalise(F.col(name), spec["type"]).alias(name))
    out = df.select(*cols)
    for name, spec in fields.items():
        if spec["type"] in TEXT_TYPES or spec["type"] == "date":
            out = out.withColumn(f"tok_{name}", tokens(F.col(name)))
    text = F.concat_ws(" ", *[F.col(n) for n in fields])
    return out.withColumn("_grams", qgrams(text, cfg.get("candidates.q")))
