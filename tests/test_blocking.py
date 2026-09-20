from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO

import pytest

from lakematch import blocking, candidates, entity
from lakematch.config import ConfigError, from_dict


def configured(config, **options):
    raw = deepcopy(config.data)
    raw["candidates"].update(options)
    return from_dict(raw)


def fixture(spark, config):
    left = spark.createDataFrame([("a1", "alice martin", "75"), ("a2", "bob smith", "69"),
                                   ("a3", "carol jones", "13")], "rec_id string, name string, code string")
    right = spark.createDataFrame([("b1", "alice martin", "75"), ("b2", "bob smith", "69"),
                                    ("b3", "carol jones", "13")], left.schema)
    labels = spark.createDataFrame([(f"a{i}", f"b{j}", float(i == j)) for i in range(1, 4) for j in range(1, 4)],
                                   "a_id string, b_id string, label double")
    return entity.prepare(left, config), entity.prepare(right, config), labels


@pytest.mark.parametrize("method", ["field_blocks", "learned_blocker", "minhash_lsh", "union"])
def test_methods_keep_identical_matches_and_reload_state(spark, config, tmp_path, method):
    cfg = configured(config, method=method, field_blocks=[["code"], ["soundex(name)"]],
                     union_of=["gram_topk", "field_blocks"], k=2, max_join_rows=10000)
    left, right, labels = fixture(spark, cfg)
    state = blocking.prepare_state(left, right, labels, cfg)
    path = tmp_path / method
    blocking.save_state(state, path)
    restored = blocking.load_state(path)
    plan = candidates.build(left, right, cfg, state=restored)
    report = plan.validate_budget()
    assert report["candidate_pairs"] <= 6
    rows = plan.pairs.orderBy("a_id", "rank").collect()
    assert {(f"a{i}", f"b{i}") for i in range(1, 4)} <= {(r.a_id, r.b_id) for r in rows}
    assert all(0 <= r.cos <= 1 and 1 <= r.rank <= 2 for r in rows)
    before = candidates.build(left, right, cfg, state=state).pairs.orderBy("a_id", "rank").collect()
    assert rows == before
    if method != "minhash_lsh":
        output = StringIO()
        with redirect_stdout(output):
            plan.pairs.explain(mode="extended")
        assert not any(node in output.getvalue() for node in ("PythonUDF", "BatchEvalPython", "ArrowEvalPython"))


def test_key_budgets_and_hot_key_loss_are_measured_before_topk(spark, config):
    cfg = configured(config, method="field_blocks", field_blocks=[["code"]], k=1, max_join_rows=5)
    frame = entity.prepare(spark.createDataFrame([(str(i), "common", "hot") for i in range(4)],
                                                 "rec_id string, name string, code string"), cfg)
    with pytest.raises(candidates.CandidateBudgetExceeded, match="Pre-top-k"):
        candidates.build(frame, frame, cfg).validate_budget()
    dropped = configured(cfg, gram_cap=2)
    report = candidates.build(frame, frame, dropped).validate_budget()
    assert report["join_rows_before_cap"] == 16 and report["join_rows_after_cap"] == 0
    assert report["candidate_pairs"] == 0 and report["dropped_grams"] == 1


def test_missing_keys_do_not_match_and_ties_use_pair_ids(spark, config):
    cfg = configured(config, method="field_blocks", field_blocks=[["code"]], k=1)
    left = entity.prepare(spark.createDataFrame([("a1", "same", "1"), ("a2", "same", None)],
                                                "rec_id string, name string, code string"), cfg)
    right = entity.prepare(spark.createDataFrame([("z", "same", "1"), ("b", "same", "1"), ("x", "same", None)],
                                                 "rec_id string, name string, code string"), cfg)
    rows = candidates.build(left, right, cfg).pairs.collect()
    assert [(r.a_id, r.b_id) for r in rows] == [("a1", "b")]


def test_learned_cover_can_select_complementary_rules(spark, config):
    cfg = configured(config, method="learned_blocker", field_blocks=[["code"], ["name"]], max_block_rules=2)
    left = entity.prepare(spark.createDataFrame([("a_é", "alice", "75"), ("a_王", "bob", "69")],
                                                "rec_id string, name string, code string"), cfg)
    right = entity.prepare(spark.createDataFrame([("b_é", "alyce", "75"), ("b_王", "bob", "99")],
                                                 "rec_id string, name string, code string"), cfg)
    labels = spark.createDataFrame([("a_é", "b_é", 1.), ("a_王", "b_王", 1.), ("a_é", "b_王", 0.)],
                                    "a_id string, b_id string, label double")
    state = blocking.prepare_state(left, right, labels, cfg)
    assert state["rules"] == [["code"], ["name"]]
    assert state["training_uncovered"] == 0 and state["training_positives"] == 2
    assert len(state["label_set_sha256"]) == 64
    with pytest.raises(ValueError, match="job task"):
        candidates.build(left, right, cfg)


def test_union_budget_is_the_sum_of_children(spark, config):
    cfg = configured(config, method="union", field_blocks=[["code"]], union_of=["field_blocks", "gram_topk"], max_join_rows=1)
    left, right, _ = fixture(spark, cfg)
    with pytest.raises(candidates.CandidateBudgetExceeded, match="Pre-top-k"):
        candidates.build(left, right, cfg).validate_budget()


def test_learned_rule_cost_excludes_discarded_hot_keys(spark, config):
    cfg = configured(config, method="learned_blocker", field_blocks=[["code"], ["name"]],
                     gram_cap=2, max_block_rules=1)
    schema = "rec_id string, name string, code string"
    left = entity.prepare(spark.createDataFrame([("a0", "alice", "cold"), ("a1", "alice", "hot"),
        ("a2", "bob", "hot"), ("a3", "carol", "hot")], schema), cfg)
    right = entity.prepare(spark.createDataFrame([("b0", "alice", "cold"), ("b1", "d", "hot"),
        ("b2", "e", "hot"), ("b3", "f", "hot")], schema), cfg)
    labels = spark.createDataFrame([("a0", "b0", 1.)], "a_id string, b_id string, label double")
    state = blocking.prepare_state(left, right, labels, cfg)
    assert state["rules"] == [["code"]]
    assert state["selection"][0]["estimated_join_rows"] == 1


@pytest.mark.parametrize("key", ["arbitrary(name)", "soundex(missing)", "year(name)", "name); DROP TABLE x"])
def test_blocking_keys_are_a_closed_typed_language(config, key):
    with pytest.raises(ConfigError, match="blocking key"):
        configured(config, field_blocks=[[key]])
