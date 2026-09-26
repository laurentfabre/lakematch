"""ZR-3a: every candidate method proposes, the shared ranking cuts to k per left record, recall on a noisy toy task."""
import random

import pytest
from pyspark.sql import functions as F

from conftest import make_cfg
from lakematch import candidates, entity

FIELDS = {"given": {"type": "person_name"}, "surname": {"type": "person_name"}, "street": {"type": "address"},
          "postcode": {"type": "code"}, "dob": {"type": "date"}}
GIVEN = ["anna", "benoit", "claire", "david", "elise", "francois", "gaelle", "hugo", "ines", "jules"]
SUR = ["martin", "bernard", "dubois", "thomas", "robert", "richard", "petit", "durand", "leroy", "moreau"]


def _typo(rng, s):
    i = rng.randrange(len(s) - 1)
    return s[:i] + s[i + 1] + s[i] + s[i + 2:]


@pytest.fixture(scope="module")
def task(spark):
    rng = random.Random(3)
    left, right, truth = [], [], set()
    for i in range(60):
        p = (f"L{i:03d}", rng.choice(GIVEN), rng.choice(SUR), f"{rng.randint(1, 99)} rue {rng.choice(SUR)}",
             f"75{rng.randint(1, 20):03d}", f"19{rng.randint(40, 99)}0{rng.randint(1, 9)}1{rng.randint(0, 9)}")
        left.append(p)
        if i % 2 == 0:
            rid = f"R{i:03d}"
            right.append((rid, _typo(rng, p[1]), p[2], p[3], p[4], p[5]))
            truth.add((p[0], rid))
    for j in range(15):                                           # distractors
        right.append((f"X{j:03d}", rng.choice(GIVEN), rng.choice(SUR), f"{rng.randint(1, 99)} rue {rng.choice(SUR)}",
                      f"75{rng.randint(1, 20):03d}", "19500101"))
    schema = "rid string, given string, surname string, street string, postcode string, dob string"
    cfg = make_cfg(entity={"fields": FIELDS}, candidates={"k": 3, "gram_cap": 50})
    L = entity.prepare(spark.createDataFrame(left, schema), cfg, "rid")
    R = entity.prepare(spark.createDataFrame(right, schema), cfg, "rid")
    labelled = spark.createDataFrame(sorted(truth)[:20], "l_id string, r_id string").withColumn("label", F.lit(1.0))
    return L, R, truth, labelled


def _check(out, truth, k, min_recall):
    rows = out.collect()
    assert set(out.columns) >= {"l_id", "r_id", "cand_score", "cand_rank", "cand_gap"}
    per_left = {}
    for r in rows:
        per_left.setdefault(r.l_id, []).append(r)
    assert max(len(v) for v in per_left.values()) <= k                       # the shared budget
    got = {(r.l_id, r.r_id) for r in rows}
    recall = len(got & truth) / len(truth)
    assert recall >= min_recall, recall
    return recall


def _run(task, method, min_recall, **cand):
    L, R, truth, labelled = task
    cfg = make_cfg(entity={"fields": FIELDS}, candidates={"method": method, "k": 3, "gram_cap": 50, **cand})
    out = candidates.generate(L, R, cfg, labelled)
    recall = _check(out, truth, 3, min_recall)
    again = sorted(tuple(r) for r in candidates.generate(L, R, cfg, labelled).select("l_id", "r_id", "cand_rank").collect())
    assert again == sorted(tuple(r) for r in out.select("l_id", "r_id", "cand_rank").collect())   # deterministic
    return recall


def test_candidate_method_gram_topk(task):
    _run(task, "gram_topk", 0.95)


def test_candidate_method_field_blocks(task):
    _run(task, "field_blocks", 0.9)                                     # default blocks: one per field
    _run(task, "field_blocks", 0.9, field_blocks=[["postcode", "substring(dob, 1, 4)"], ["surname"]])


def test_candidate_method_learned_blocker(task):
    L, R, truth, labelled = task
    cfg = make_cfg(entity={"fields": FIELDS}, candidates={"method": "learned_blocker", "k": 3, "gram_cap": 50})
    chosen = candidates.learn_blocker(L, R, cfg, labelled)
    assert chosen and all(n.split(" & ")[0] in candidates.predicate_pool(cfg) for n in chosen)
    _run(task, "learned_blocker", 0.9)
    with pytest.raises(ValueError, match="needs labelled pairs"):
        candidates.generate(L, R, cfg, None)


def test_candidate_method_minhash_lsh(task):
    _run(task, "minhash_lsh", 0.8, lsh_threshold=0.8, lsh_tables=8)


def test_candidate_method_union(task):
    r_union = _run(task, "union", 0.95, union_of=["field_blocks", "minhash_lsh"])
    L, R, truth, labelled = task
    parts = [candidates.propose(m, L, R, make_cfg(entity={"fields": FIELDS}, candidates={"k": 3, "gram_cap": 50}))
             for m in ("field_blocks", "minhash_lsh")]
    both = candidates.propose("union", L, R, make_cfg(entity={"fields": FIELDS}, candidates={
        "method": "union", "union_of": ["field_blocks", "minhash_lsh"], "k": 3, "gram_cap": 50}))
    assert both.count() >= max(p.count() for p in parts)                  # a union proposes at least each part


def test_rescore_gives_zero_to_pairs_without_a_shared_gram(spark):
    cfg = make_cfg(candidates={"gram_cap": 10})
    mk = lambda rows: spark.createDataFrame(rows, "id string, _grams array<string>")
    left, right = mk([("a", ["x", "y"])]), mk([("b", ["x"]), ("c", ["z"])])
    props = spark.createDataFrame([("a", "b"), ("a", "c")], "l_id string, r_id string")
    got = {r.r_id: r.cand_score for r in candidates.rescore(props, left, right, cfg).collect()}
    assert got["c"] == 0.0 and 0 < got["b"] <= 1
