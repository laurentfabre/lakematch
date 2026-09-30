"""Entity view, candidates, features, decision — each against values computed by hand."""
import math

import pytest
from pyspark.sql import functions as F

from conftest import make_cfg
from lakematch import candidates, decision, entity, features


def test_normalise_and_grams(spark):
    df = spark.createDataFrame([("1", " Jean-Luc  O'Neil ", "75-001 ", "Rue du  Bac")],
                               "rid string, name string, code string, addr string")
    cfg = make_cfg(entity={"fields": {"name": {"type": "person_name"}, "code": {"type": "code"},
                                      "addr": {"type": "address"}}}, candidates={"q": 3})
    row = entity.prepare(df, cfg, "rid").first()
    assert (row.id, row.name, row.code, row.addr) == ("1", "jean luc o neil", "75001", "rue du bac")
    assert row.tok_addr == ["rue", "du", "bac"]
    short = spark.range(1).select(entity.qgrams(F.lit("ab"), 3).alias("g")).first().g
    assert short == ["ab"]


def _sides(spark, left, right):
    mk = lambda rows: spark.createDataFrame([(i, g) for i, g in rows], "id string, _grams array<string>")
    return mk(left), mk(right)


def test_gram_topk_is_a_real_idf_cosine(spark):
    left, right = _sides(spark, [("a", ["x", "y"])], [("b", ["x", "z"]), ("c", ["y", "z"])])
    cfg = make_cfg(candidates={"k": 5, "gram_cap": 10, "rank_vocab_share": 1.0})
    got = {r.r_id: r.cand_score for r in candidates.gram_topk(left, right, cfg).collect()}
    n = 3
    w = {g: math.log((1 + n) / (1 + d)) + 1 for g, d in {"x": 2, "y": 2, "z": 2}.items()}
    norm = lambda gs: math.sqrt(sum(w[g] ** 2 for g in gs))
    assert got["b"] == pytest.approx(w["x"] ** 2 / (norm("xy") * norm("xz")))
    assert got["c"] == pytest.approx(w["y"] ** 2 / (norm("xy") * norm("yz")))


def test_ubiquitous_grams_leave_both_numerator_and_norms(spark):
    # "z" sits in 3 of 3 right records > rank_vocab_share 0.5: it must vanish from the dot product AND the norms
    left, right = _sides(spark, [("a", ["x", "z"])], [("b", ["x", "z"]), ("c", ["z"]), ("d", ["z", "q"])])
    cfg = make_cfg(candidates={"k": 5, "gram_cap": 2, "rank_vocab_share": 0.5, "idf_weighted": False})
    got = {r.r_id: r.cand_score for r in candidates.gram_topk(left, right, cfg).collect()}
    assert got == {"b": pytest.approx(1.0)}      # both reduce to {x}: cosine 1, not 1/2


def test_join_cap_is_not_the_ranking_vocabulary(spark):
    # ZR-3s: "z" is too common to JOIN on (gram_cap 1) but stays in the ranking vocabulary (share 1.0), so b is
    # proposed through "x" alone and then ranked over {x, z}: identical sets, cosine 1; c and d share only "z"
    left, right = _sides(spark, [("a", ["x", "z"])], [("b", ["x", "z"]), ("c", ["z"]), ("d", ["z", "q"])])
    cfg = make_cfg(candidates={"k": 5, "gram_cap": 1, "rank_vocab_share": 1.0, "idf_weighted": False})
    got = {r.r_id: r.cand_score for r in candidates.gram_topk(left, right, cfg).collect()}
    assert got == {"b": pytest.approx(1.0)}
    scored = {r.r_id: r.cand_score for r in candidates.rescore(
        spark.createDataFrame([("a", r) for r in "bcd"], "l_id string, r_id string"), left, right, cfg).collect()}
    assert scored["c"] == pytest.approx(1 / math.sqrt(2)) and scored["d"] == pytest.approx(0.5)


def test_top_k_and_deterministic_ties(spark):
    left, right = _sides(spark, [("a", ["x"])], [(r, ["x"]) for r in ("r3", "r1", "r2")])
    cfg = make_cfg(candidates={"k": 2, "gram_cap": 10, "rank_vocab_share": 1.0})
    rows = sorted(candidates.gram_topk(left, right, cfg).collect(), key=lambda r: r.cand_rank)
    assert [(r.r_id, r.cand_rank, r.cand_gap) for r in rows] == [("r1", 1, 0.0), ("r2", 2, 0.0)]


def test_multi_token_features(spark):
    df = spark.createDataFrame([(["main", "st"], ["st", "main"], ["abc"], [])],
                               "a array<string>, b array<string>, c array<string>, d array<string>")
    row = df.select(features._monge_elkan(F.col("a"), F.col("b")).alias("me"),
                    features._monge_elkan(F.col("a"), F.col("d")).alias("me_missing"),
                    features._jaccard(F.array(F.lit("ab"), F.lit("bc")), F.array(F.lit("bc"), F.lit("cd"))).alias("j")
                    ).first()
    assert row.me == pytest.approx(1.0) and row.me_missing == -1.0 and row.j == pytest.approx(1 / 3)


@pytest.fixture
def scored(spark):
    rows = [("a", "x", 0.9), ("a", "y", 0.8), ("b", "x", 0.95), ("b", "z", 0.7), ("c", "w", 0.3), ("d", "v", 0.8),
            ("d", "u", 0.8)]
    return spark.createDataFrame(rows, "l_id string, r_id string, p double")


def _pairs(df):
    return sorted((r.l_id, r.r_id) for r in df.collect())


def test_cardinality_policies(scored):
    link = lambda c: _pairs(decision.links(scored, 0.5, make_cfg(decision={"cardinality": c})))
    assert link("unrestricted") == [("a", "x"), ("a", "y"), ("b", "x"), ("b", "z"), ("d", "u"), ("d", "v")]
    assert link("many_to_one") == [("a", "x"), ("b", "x"), ("d", "u")]           # tie on d: lower r_id wins
    assert link("one_to_one") == [("b", "x"), ("d", "u")]                          # x goes to b (0.95 > 0.9)


def test_threshold_from_validation(spark):
    val = spark.createDataFrame([(0.9, 1.0), (0.8, 1.0), (0.3, 0.0), (0.6, 0.0)], "p double, label double")
    t = decision.pick_threshold(val, make_cfg())
    assert 0.6 < t <= 0.8
    assert decision.pick_threshold(val, make_cfg(decision={"threshold": 0.42})) == 0.42
