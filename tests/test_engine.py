from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import math

import pytest
from pyspark.sql import functions as F

from lakematch import candidates, decision, entity, features, matcher
from lakematch.config import from_dict
from lakematch.quality import apply_and_split
from lakematch.runtime import Capabilities, Materializer, probe


def altered(config, section, **values):
    data = deepcopy(config.data)
    data[section].update(values)
    return from_dict(data)


def test_quarantine_duplicates_warnings_and_row_checks(spark, config):
    config = altered(config, "quality", checks=[
        {"name": "name_required", "kind": "not_null", "column": "name"},
        {"name": "code_format", "kind": "regex", "column": "code", "pattern": "^[0-9]{2}$", "criticality": "warn"},
    ])
    rows = [("good", "Alice", "75"), ("warn", "Bob", "x"), ("dup", "Dan", "69"),
            ("dup", "Dana", "69"), ("missing", " ", "13"), (None, "Carol", "44")]
    split = apply_and_split(spark.createDataFrame(rows, "rec_id string, name string, code string"), config)
    valid = {r.rec_id: r for r in split.valid.collect()}
    assert set(valid) == {"good", "warn"}
    assert valid["good"].lm_reasons == []
    assert valid["warn"].lm_reasons[0].criticality == "warn"
    quarantined = split.quarantined.collect()
    assert len(quarantined) == 4
    assert {r.rec_id for r in quarantined} == {"dup", "missing", None}
    assert all(any(x.criticality == "error" for x in r.lm_reasons) for r in quarantined)


def test_dataset_level_minimum_rows(spark, config):
    cfg = altered(config, "quality", checks=[{"name": "minimum", "kind": "min_rows", "value": 3}])
    result = apply_and_split(spark.createDataFrame([("a", "A", "1"), ("b", "B", "2")], "rec_id string, name string, code string"), cfg)
    assert result.valid.count() == 0
    assert result.quarantined.count() == 2


def test_idf_cosine_matches_independent_hand_calculation(spark, config):
    cfg = altered(config, "candidates", q=1, k=2, gram_cap=10)
    cfg = altered(cfg, "entity", fields={"name": {"type": "person_name"}})
    a = spark.createDataFrame([("a1", "xy"), ("a2", "x")], "rec_id string, name string")
    b = spark.createDataFrame([("b1", "xz"), ("b2", "y")], "rec_id string, name string")
    plan = candidates.build(a, b, cfg)
    report = plan.validate_budget()
    assert report["join_rows_before_cap"] == 3
    assert report["join_rows_after_cap"] == 3
    assert report["candidate_pairs"] == 3
    x, y, z = 1 + math.log(5 / 4), 1 + math.log(5 / 3), 1 + math.log(5 / 2)
    expected = {("a1", "b1"): x*x / math.sqrt((x*x+y*y)*(x*x+z*z)),
                ("a1", "b2"): y / math.sqrt(x*x+y*y), ("a2", "b1"): x / math.sqrt(x*x+z*z)}
    actual = {(r.a_id, r.b_id): r.cos for r in plan.pairs.collect()}
    assert actual == pytest.approx(expected, abs=1e-12)
    # x is removed entirely from both norms when its left-side frequency exceeds cap.
    capped = candidates.build(a, b, altered(cfg, "candidates", gram_cap=1))
    rows = capped.pairs.collect()
    assert len(rows) == 1 and rows[0].a_id == "a1" and rows[0].b_id == "b2" and rows[0].cos == 1.0


def test_join_budget_fails_before_pair_execution(spark, config):
    cfg = altered(config, "candidates", q=1, max_join_rows=5, k=1)
    rows = [(str(i), "hot", "") for i in range(4)]
    frame = spark.createDataFrame(rows, "rec_id string, name string, code string")
    with pytest.raises(candidates.CandidateBudgetExceeded, match="Pre-top-k"):
        candidates.build(frame, frame, cfg).validate_budget()


def test_pair_budget_and_deterministic_topk(spark, config):
    a = spark.createDataFrame([("a", "Alice", "75")], "rec_id string, name string, code string")
    b = spark.createDataFrame([("z", "Alice", "75"), ("b", "Alice", "75")], a.schema)
    one = candidates.build(a, b, altered(config, "candidates", k=1)).pairs.collect()
    assert [(r.a_id, r.b_id) for r in one] == [("a", "b")]
    with pytest.raises(candidates.CandidateBudgetExceeded, match="pair budget"):
        candidates.build(a, b, altered(config, "candidates", max_pairs=1)).validate_budget()


def test_records_without_any_values_do_not_generate_candidates(spark, config):
    a = spark.createDataFrame([("a", "", "")], "rec_id string, name string, code string")
    b = spark.createDataFrame([("b", "", ""), ("c", "Alice", "75")], a.schema)
    plan = candidates.build(a, b, config)
    report = plan.validate_budget()
    assert report["candidate_pairs"] == 0
    assert report["join_rows_before_cap"] == 0


def test_native_plan_unicode_missing_and_similarity(spark, config):
    a = entity.prepare(spark.createDataFrame([("a", " ÉLISE  王! ", None)], "rec_id string, name string, code string"), config)
    b = entity.prepare(spark.createDataFrame([("b", "élise 王", "")], "rec_id string, name string, code string"), config)
    pairs = spark.createDataFrame([("a", "b", 1.0, 1, 0.0)], "a_id string, b_id string, cos double, rank int, gap double")
    frame = features.build(pairs, a, b, config)
    row = frame.first()
    assert row.lev_name == 1.0 and row.eq_name == 1.0
    assert row.lev_code == -1.0 and row.missing_code == 1.0
    output = StringIO()
    with redirect_stdout(output):
        frame.explain(mode="extended")
    assert not any(node in output.getvalue() for node in ("PythonUDF", "BatchEvalPython", "ArrowEvalPython"))


@pytest.mark.parametrize("mode,expected", [
    ("one_to_one", {("a1", "b1"), ("a3", "b2")}),
    ("many_to_one", {("a1", "b1"), ("a2", "b1"), ("a3", "b2")}),
    ("unrestricted", {("a1", "b1"), ("a1", "b2"), ("a2", "b1"), ("a3", "b2")}),
])
def test_cardinality_thresholds_and_ties(spark, config, mode, expected):
    rows = [("a2", "b1", .9), ("a1", "b2", .9), ("a1", "b1", .9),
            ("a3", "b2", .8), ("a4", "b3", .1), ("a5", "b4", float("nan")), ("a1", "b1", .7)]
    frame = spark.createDataFrame(rows, "a_id string, b_id string, p double")
    result = decision.links(frame, altered(config, "decision", cardinality=mode))
    assert {(r.a_id, r.b_id) for r in result.collect()} == expected


def test_materialization_cache_and_table_cleanup(spark, config):
    capabilities = probe(spark)
    assert capabilities.cache
    with Materializer(spark, config, capabilities) as m:
        assert m.materialize(spark.range(5), "cache_test").count() == 5
        assert m.events[-1]["strategy"] == "cache"
    # Force the non-caching capability branch and prove actual table round-trip + cleanup.
    no_cache = Capabilities(spark.version, capabilities.connect, False, "test forces serverless-style branch")
    with Materializer(spark, config, no_cache) as m:
        assert m.materialize(spark.range(7), "table_test").count() == 7
        table = m.events[-1]["table"]
        assert spark.catalog.tableExists(table)
    assert not spark.catalog.tableExists(table)


@pytest.mark.parametrize("estimator", ["gbt", "logistic_regression", "random_forest"])
def test_estimator_fit_score_save_reload(spark, config, tmp_path, estimator):
    from pyspark.ml import PipelineModel
    cfg = altered(config, "matcher", estimator=estimator, max_iter=5)
    order = features.feature_order(cfg)
    # Controlled separable comparison vectors; this checks model persistence, not benchmark quality.
    rows = [(f"a{i}", f"b{i}", *([float(i % 2)] * len(order))) for i in range(20)]
    frame = spark.createDataFrame(rows, "a_id string, b_id string, " + ", ".join(f"{n} double" for n in order))
    labels = spark.createDataFrame([(f"a{i}", f"b{i}", float(i % 2)) for i in range(20)], "a_id string, b_id string, label double")
    model = matcher.train(frame, labels, cfg)
    before = {r.a_id: r.p for r in matcher.score(frame, model).select("a_id", "p").collect()}
    assert all((v >= .5) == (int(k[1:]) % 2 == 1) for k, v in before.items())
    path = str(tmp_path / "pipeline")
    model.write().save(path)
    after = {r.a_id: r.p for r in matcher.score(frame, PipelineModel.load(path)).select("a_id", "p").collect()}
    assert before == pytest.approx(after, abs=1e-12)
