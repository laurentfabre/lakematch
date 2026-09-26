"""The optional UDF features — off by default, behind `features.udf_features`, never run by Photon.

    jaro_winkler   Winkler (1990): Jaro similarity plus a prefix bonus of 0.1 per shared leading character (at most
                   4), applied only when Jaro exceeds 0.7. A pandas UDF on Spark 4.1 / 4.2; from 4.3 the built-in
                   `jaro_winkler_similarity` (SPARK-57253) replaces it with no config change.
    affine_gap     a character-level local alignment with affine gap costs (Gotoh 1982), with the scores Monge and
                   Elkan (1996) used for field matching: match +5, approximate match +3 for letters that are often
                   confused ({d t} {g j} {l r} {m n} {b p v} {a e i o u}), mismatch -3, gap open -5, gap extension -1.
                   The best local score is divided by 5 x the shorter length, so containment scores 1.0. Inputs are
                   cut to 64 characters: the alignment is quadratic and meant for short strings.

Both are written from those published descriptions; no third-party matcher code is used.
"""
# No `from __future__ import annotations` here: pandas_udf reads the type hints at definition time.
from pyspark.sql import Column, functions as F

AFFINE_MAX_LEN = 64
_APPROX = {}
for _group in ("dt", "gj", "lr", "mn", "bpv", "aeiou"):
    for _x in _group:
        for _y in _group:
            if _x != _y:
                _APPROX[(_x, _y)] = True


def jaro(a: str, b: str) -> float:
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if not la or not lb:
        return 0.0
    window = max(max(la, lb) // 2 - 1, 0)
    ma, mb = [False] * la, [False] * lb
    matches = 0
    for i, ch in enumerate(a):
        lo, hi = max(0, i - window), min(lb, i + window + 1)
        for j in range(lo, hi):
            if not mb[j] and b[j] == ch:
                ma[i] = mb[j] = True
                matches += 1
                break
    if not matches:
        return 0.0
    transpositions, j = 0, 0
    for i in range(la):
        if ma[i]:
            while not mb[j]:
                j += 1
            if a[i] != b[j]:
                transpositions += 1
            j += 1
    m = matches
    return (m / la + m / lb + (m - transpositions / 2) / m) / 3


def jaro_winkler_score(a: str | None, b: str | None) -> float | None:
    if a is None or b is None:
        return None
    j = jaro(a, b)
    if j <= 0.7:
        return j
    prefix = 0
    for x, y in zip(a[:4], b[:4]):
        if x != y:
            break
        prefix += 1
    return j + prefix * 0.1 * (1 - j)


def affine_gap_score(a: str | None, b: str | None) -> float | None:
    if a is None or b is None:
        return None
    a, b = a[:AFFINE_MAX_LEN], b[:AFFINE_MAX_LEN]
    if not a or not b:
        return 0.0
    match, approx, mismatch, gap_open, gap_ext = 5.0, 3.0, -3.0, -5.0, -1.0
    n = len(b)
    neg = float("-inf")
    prev_m, prev_x, prev_y = [0.0] * (n + 1), [neg] * (n + 1), [neg] * (n + 1)
    best = 0.0
    for i in range(1, len(a) + 1):
        cur_m, cur_x, cur_y = [0.0] * (n + 1), [neg] * (n + 1), [neg] * (n + 1)
        ca = a[i - 1]
        for j in range(1, n + 1):
            cb = b[j - 1]
            s = match if ca == cb else approx if (ca, cb) in _APPROX else mismatch
            diag = max(prev_m[j - 1], prev_x[j - 1], prev_y[j - 1], 0.0)
            cur_m[j] = max(0.0, diag + s)
            cur_x[j] = max(prev_m[j] + gap_open, prev_x[j] + gap_ext)          # gap in b
            cur_y[j] = max(cur_m[j - 1] + gap_open, cur_y[j - 1] + gap_ext)    # gap in a
            if cur_m[j] > best:
                best = cur_m[j]
        prev_m, prev_x, prev_y = cur_m, cur_x, cur_y
    return min(best / (match * min(len(a), len(b))), 1.0)


_UDFS: dict = {}


def _pandas_udf(name: str, fn):
    if name not in _UDFS:
        import pandas as pd
        from pyspark.sql.functions import pandas_udf

        @pandas_udf("double")
        def run(a: pd.Series, b: pd.Series) -> pd.Series:
            return pd.Series([fn(x, y) for x, y in zip(a, b)], dtype="float64")
        _UDFS[name] = run
    return _UDFS[name]


def jaro_winkler(a: Column, b: Column, spark_version: str) -> Column:
    from . import spark_at_least
    if spark_at_least(spark_version, 4, 3):
        return F.call_function("jaro_winkler_similarity", a, b)
    return _pandas_udf("jaro_winkler", jaro_winkler_score)(a, b)


def affine_gap(a: Column, b: Column) -> Column:
    return _pandas_udf("affine_gap", affine_gap_score)(a, b)
