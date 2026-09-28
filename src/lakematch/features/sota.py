"""SIM-2 opt-in comparisons. Every builder emits Spark 4.1 built-in expressions.

DP is SQL text so Connect sends one shallow expression rather than a deeply nested protobuf.
No Python function runs on records. See spec/SIMILARITY.md for definitions and resource limits.
"""
from __future__ import annotations

from pyspark.sql import Column, DataFrame, functions as F

from ..config import Config

MISSING = -1.0
TEXT = ("person_name", "address", "organisation", "title")
MULTI = ("address", "organisation", "title")
FIELD_TYPES = {
    "osa": ("person_name", "title", "code"),
    "weighted_jaccard": MULTI,
    "padded_bigram_dice": (*TEXT, "code"),
    "qgram_count_cosine": MULTI,
    "token_sort_lev": TEXT,
    "soft_tfidf_lev": MULTI,
    "lcs_indel": (*TEXT, "code"),
}
PREFIXES = {"osa": "osa", "weighted_jaccard": "wja", "padded_bigram_dice": "pbd",
            "qgram_count_cosine": "qcc", "token_sort_lev": "tsl", "soft_tfidf_lev": "stl",
            "lcs_indel": "lci"}


def _present(a: Column, b: Column) -> Column:
    return (F.length(a) > 0) & (F.length(b) > 0)


def sorted_tokens(tokens: Column) -> Column:
    return F.concat_ws(" ", F.sort_array(tokens))


def token_sort_lev(a: Column, b: Column) -> Column:
    """The inputs are sorted, duplicate-preserving token strings prepared once per record."""
    return F.when(_present(a, b), 1.0 - F.levenshtein(a, b) / F.greatest(F.length(a), F.length(b))).otherwise(MISSING)


def _counts(grams: Column) -> Column:
    # Bind grams once. Distinct keys avoid map-key dedup-policy dependence; counting is O(n*u).
    def count(gs):
        keys = F.array_distinct(gs)
        return F.map_from_arrays(keys, F.transform(keys, lambda k: F.size(F.filter(gs, lambda g: g == k)).cast("double")))
    return F.get(F.transform(F.array(grams), count), 0)


def bigram_counts(s: Column) -> Column:
    """JSON pairs encode boundary nulls separately from literal input characters, including quotes."""
    text = F.coalesce(s, F.lit(""))
    n = F.length(text)
    grams = F.transform(F.sequence(F.lit(0), n), lambda i: F.to_json(F.array(
        F.when(i > 0, F.substring(text, i, 1)),
        F.when(i < n, F.substring(text, i + 1, 1)))))
    return F.when(n > 0, _counts(grams)).otherwise(F.create_map().cast("map<string,double>"))


def trigram_counts(s: Column) -> Column:
    text = F.coalesce(s, F.lit(""))
    n = F.length(text)
    grams = F.when(n < 3, F.array(F.concat(F.lit("short:"), text))).otherwise(
        F.transform(F.sequence(F.lit(1), F.greatest(n - 2, F.lit(1))),
                    lambda i: F.concat(F.lit("gram:"), F.substring(text, i, 3))))
    return F.when(n > 0, _counts(grams)).otherwise(F.create_map().cast("map<string,double>"))


def _sum(values: Column) -> Column:
    return F.aggregate(values, F.lit(0.0), lambda s, v: s + v)


def _norm(values: Column) -> Column:
    return F.sqrt(_sum(F.transform(values, lambda v: v * v)))


def _maps_present(a: Column, b: Column) -> Column:
    return (F.size(a) > 0) & (F.size(b) > 0)


def weighted_jaccard(a: Column, b: Column) -> Column:
    shared = F.array_intersect(F.map_keys(a), F.map_keys(b))
    union = F.array_union(F.map_keys(a), F.map_keys(b))
    total = _sum(F.transform(union, lambda k: F.coalesce(a[k], b[k])))
    score = _sum(F.transform(shared, lambda k: a[k])) / total
    return F.when(_maps_present(a, b) & (total > 0), score).otherwise(MISSING)


def padded_bigram_dice(a: Column, b: Column) -> Column:
    shared = F.array_intersect(F.map_keys(a), F.map_keys(b))
    common = _sum(F.transform(shared, lambda k: F.least(a[k], b[k])))
    total = _sum(F.map_values(a)) + _sum(F.map_values(b))
    return F.when(_maps_present(a, b) & (total > 0), 2.0 * common / total).otherwise(MISSING)


def qgram_count_cosine(a: Column, b: Column) -> Column:
    shared = F.array_intersect(F.map_keys(a), F.map_keys(b))
    dot = _sum(F.transform(shared, lambda k: a[k] * b[k]))
    total = _norm(F.map_values(a)) * _norm(F.map_values(b))
    return F.when(_maps_present(a, b) & (total > 0), F.least(F.lit(1.0), dot / total)).otherwise(MISSING)


def weighted_tokens(weights: Column) -> Column:
    """Canonical lexical order and unit L2 norm; token weights come from the common IDF dictionary."""
    state = F.struct(weights.alias("weights"), _norm(F.map_values(weights)).alias("norm"))
    def normalized(s):
        return F.transform(F.sort_array(F.map_entries(s.weights)), lambda e:
                           F.struct(e.key.alias("token"), (e.value / s.norm).alias("weight")))
    return F.get(F.transform(F.array(state), normalized), 0)


def soft_tfidf_lev(a: Column, b: Column, token_cap: int) -> Column:
    def directed(xs, ys):
        def contribution(x):
            sims = F.transform(ys, lambda y: F.struct(
                (1.0 - F.levenshtein(x.token, y.token) / F.greatest(F.length(x.token), F.length(y.token))).alias("score"),
                y.weight.alias("weight")))
            return F.aggregate(sims, F.struct(F.lit(-1.0).alias("score"), F.lit(0.0).alias("weight")),
                lambda best, candidate: F.when(candidate.score > best.score, candidate).otherwise(best),
                lambda best: F.when(best.score > 0.8, x.weight * best.weight * best.score).otherwise(0.0))
        return _sum(F.transform(xs, contribution))
    score = F.least(F.lit(1.0), (directed(a, b) + directed(b, a)) / 2.0)
    return (F.when((F.size(a) <= 0) | (F.size(b) <= 0) | a.isNull() | b.isNull(), MISSING)
            .when((F.size(a) > token_cap) | (F.size(b) > token_cap),
                  F.raise_error(F.lit("soft_tfidf_lev exceeds features.token_cap; increase the explicit limit")))
            .otherwise(score))


def _identifier(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def _dp(a: str, b: str, max_chars: int, transpositions: bool) -> Column:
    """Exact bounded DP; choose the shorter string as columns to reduce copied row state."""
    if type(max_chars) is not int or max_chars < 1:
        raise ValueError("max_chars must be a positive integer")
    a, b = _identifier(a), _identifier(b)
    if transpositions:
        initial = "named_struct('prev2', sequence(0, length(s.y)), 'prev', sequence(0, length(s.y)))"
        cell = """least(
            element_at(r.prev, j + 1) + 1,
            element_at(c, j) + 1,
            element_at(r.prev, j) + IF(substring(s.x, i, 1) = substring(s.y, j, 1), 0, 1),
            CASE WHEN i > 1 AND j > 1
                   AND substring(s.x, i, 1) = substring(s.y, j - 1, 1)
                   AND substring(s.x, i - 1, 1) = substring(s.y, j, 1)
                 THEN element_at(r.prev2, j - 1) + 1 ELSE length(s.x) + length(s.y) END)"""
        row = f"aggregate(sequence(1, length(s.y)), array(i), (c, j) -> concat(c, array({cell})))"
        state = f"named_struct('prev2', r.prev, 'prev', {row})"
        finish = "1.0 - element_at(r.prev, -1) / CAST(length(s.x) AS DOUBLE)"
    else:
        initial = "array_repeat(0, length(s.y) + 1)"
        cell = """CASE WHEN substring(s.x, i, 1) = substring(s.y, j, 1)
                        THEN element_at(r, j) + 1
                        ELSE greatest(element_at(r, j + 1), element_at(c, j)) END"""
        state = f"aggregate(sequence(1, length(s.y)), array(0), (c, j) -> concat(c, array({cell})))"
        finish = "2.0 * element_at(r, -1) / CAST(length(s.x) + length(s.y) AS DOUBLE)"
    family = "osa" if transpositions else "lcs_indel"
    return F.expr(f"""
        CASE WHEN {a} IS NULL OR {b} IS NULL OR length({a}) = 0 OR length({b}) = 0 THEN -1.0
             WHEN greatest(length({a}), length({b})) > {max_chars}
             THEN CAST(raise_error('{family} exceeds features.sota_max_chars; increase the explicit limit') AS DOUBLE)
             ELSE get(transform(array(named_struct(
                  'x', IF(length({a}) >= length({b}), {a}, {b}),
                  'y', IF(length({a}) >= length({b}), {b}, {a}))),
                  s -> aggregate(sequence(1, length(s.x)), {initial},
                       (r, i) -> {state}, r -> {finish})), 0)
        END
    """)


def osa(a: str, b: str, max_chars: int = 256) -> Column:
    return _dp(a, b, max_chars, True)


def lcs_indel(a: str, b: str, max_chars: int = 256) -> Column:
    return _dp(a, b, max_chars, False)


def prepare(side: DataFrame, cfg: Config, families: set[str]) -> DataFrame:
    cols = {}
    for f, spec in cfg.fields.items():
        t = spec["type"]
        if "token_sort_lev" in families and t in FIELD_TYPES["token_sort_lev"]:
            cols[f"sts_{f}"] = sorted_tokens(F.col(f"tok_{f}"))
        if "padded_bigram_dice" in families and t in FIELD_TYPES["padded_bigram_dice"]:
            cols[f"pbg_{f}"] = bigram_counts(F.col(f))
        if "qgram_count_cosine" in families and t in FIELD_TYPES["qgram_count_cosine"]:
            cols[f"tgc_{f}"] = trigram_counts(F.col(f))
        if "soft_tfidf_lev" in families and t in FIELD_TYPES["soft_tfidf_lev"]:
            cols[f"sti_{f}"] = weighted_tokens(F.col(f"ti_{f}"))
    return side.withColumns(cols) if cols else side


def comparisons(field: str, ftype: str, cfg: Config, families: set[str]) -> dict[str, Column]:
    left = lambda prefix: F.col(f"l_{prefix}_{field}")
    right = lambda prefix: F.col(f"r_{prefix}_{field}")
    out = {}
    for family, types in FIELD_TYPES.items():
        if family not in families or ftype not in types:
            continue
        if family == "osa":
            expr = osa(f"l_{field}", f"r_{field}", cfg.get("features.sota_max_chars"))
        elif family == "lcs_indel":
            expr = lcs_indel(f"l_{field}", f"r_{field}", cfg.get("features.sota_max_chars"))
        elif family == "token_sort_lev":
            expr = token_sort_lev(left("sts"), right("sts"))
        elif family == "weighted_jaccard":
            expr = weighted_jaccard(left("ti"), right("ti"))
        elif family == "padded_bigram_dice":
            expr = padded_bigram_dice(left("pbg"), right("pbg"))
        elif family == "qgram_count_cosine":
            expr = qgram_count_cosine(left("tgc"), right("tgc"))
        else:
            expr = soft_tfidf_lev(left("sti"), right("sti"), cfg.get("features.token_cap"))
        out[f"{PREFIXES[family]}_{field}"] = expr
    return out
