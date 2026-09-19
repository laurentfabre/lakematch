"""Bounded native expressions, plus explicitly optional independent UDF measures.

Missing comparisons use -1. Similarities otherwise lie in [0, 1]. Token
Monge-Elkan averages both directed quadratic means (m=2), not character
alignment. IDF statistics are supplied separately from the training corpus.
"""
import math

from pyspark.sql import functions as F

from .entity import grams


def tokens(value, limit=64):
    return F.slice(F.array_distinct(F.filter(F.split(value, " "), lambda x: F.length(x) > 0)), 1, limit)


def lev(left, right, threshold=64):
    distance = F.levenshtein(left, right, threshold)
    return F.when(distance < 0, 0.0).otherwise(1 - distance / F.greatest(F.length(left), F.length(right), F.lit(1)))


def jaccard(left, right):
    return F.when((F.size(left) > 0) & (F.size(right) > 0),
                  F.size(F.array_intersect(left, right)) / F.size(F.array_union(left, right))).otherwise(-1.0)


def monge_elkan(left, right, threshold=64):
    def directed(a, b):
        maxima = F.transform(a, lambda x: F.pow(F.array_max(F.transform(b, lambda y: lev(x, y, threshold))), 2))
        return F.sqrt(F.aggregate(maxima, F.lit(0.0), lambda s, x: s + x) / F.greatest(F.size(a), F.lit(1)))
    return F.when((F.size(left) > 0) & (F.size(right) > 0),
                  (directed(left, right) + directed(right, left)) / 2).otherwise(-1.0)


def array_cosine(left, right):
    def norm(a):
        return F.sqrt(F.aggregate(a, F.lit(0.0), lambda s, x: s + x * x))
    denominator = norm(left) * norm(right)
    dot = F.aggregate(F.zip_with(left, right, lambda a, b: a * b), F.lit(0.0), lambda s, x: s + x)
    return F.when((F.size(left) == F.size(right)) & (denominator > 0),
                  F.greatest(F.lit(-1.0), F.least(F.lit(1.0), dot / denominator))).otherwise(-1.0)


def weighted_cosine(left, right):
    """Sparse map<string,double> cosine; weights, not squared weights, in maps."""
    def norm(a):
        return F.sqrt(F.aggregate(F.map_values(a), F.lit(0.0), lambda s, x: s + x * x))
    products = F.transform(F.array_intersect(F.map_keys(left), F.map_keys(right)),
                           lambda t: F.element_at(left, t) * F.element_at(right, t))
    denominator = norm(left) * norm(right)
    return F.when(denominator > 0, F.least(F.lit(1.0),
                  F.aggregate(products, F.lit(0.0), lambda s, x: s + x) / denominator)).otherwise(-1.0)


def jaro_winkler(left, right):
    """Standard Jaro with a <=4-character Winkler boost only above 0.7."""
    if not left or not right:
        return -1.0
    if left == right:
        return 1.0
    radius = max(0, max(len(left), len(right)) // 2 - 1)
    la, rb = [False] * len(left), [False] * len(right)
    for i, char in enumerate(left):
        for j in range(max(0, i - radius), min(len(right), i + radius + 1)):
            if not rb[j] and char == right[j]:
                la[i], rb[j] = True, True
                break
    matches = sum(la)
    if not matches:
        return 0.0
    a, b = [x for x, yes in zip(left, la) if yes], [x for x, yes in zip(right, rb) if yes]
    transpositions = sum(x != y for x, y in zip(a, b)) / 2
    score = (matches / len(left) + matches / len(right) + (matches - transpositions) / matches) / 3
    prefix = 0
    for x, y in zip(left[:4], right[:4]):
        if x != y:
            break
        prefix += 1
    return score + prefix * .1 * (1 - score) if score > .7 else score


def affine_gap(left, right):
    """Global affine-gap edit similarity; gap open=1, extension=.25.

    Independent Gotoh-style recurrence; normalized by max length. Global
    alignment deliberately charges unmatched ends instead of rewarding containment.
    Callers bound text length before crossing the UDF boundary.
    """
    if not left or not right:
        return -1.0
    n = len(right)
    prev = [0.0] + [1 + .25 * (j - 1) for j in range(1, n + 1)]
    vertical = [math.inf] * (n + 1)
    for i, x in enumerate(left, 1):
        row = [1 + .25 * (i - 1)] + [0.0] * n
        horizontal = math.inf
        for j, y in enumerate(right, 1):
            vertical[j] = min(prev[j] + 1, vertical[j] + .25)
            horizontal = min(row[j - 1] + 1, horizontal + .25)
            row[j] = min(prev[j - 1] + (x != y), vertical[j], horizontal)
        prev = row
    return max(0.0, 1 - prev[n] / max(len(left), len(right)))
