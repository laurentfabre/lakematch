"""ZR-7 engine side: the review queue's order, the run history, and `labels.source: app` reading the label store."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from lakematch import config, review
from lakematch.labels import app_labelled, store

from conftest import make_cfg

FIELDS = {"name": {"type": "person_name"}}


def _cfg(tmp_path, **kw):
    kw.setdefault("labels", {"source": "app"})
    return make_cfg(tmp_path, entity={"name": "person", "fields": FIELDS},
                    inputs={"left": {"path": "l.csv", "id": "id"}, "right": {"path": "r.csv", "id": "id"}}, **kw)


def test_queue_order(spark, tmp_path):
    cfg = _cfg(tmp_path, review={"band": 0.1, "impact_min": 3})
    scored = spark.createDataFrame([
        ("a", "x", 0.95, 0.9, 1),    # linked, far from the threshold, merge of 3 records -> high_impact
        ("b", "y", 0.55, 0.5, 1),    # near the threshold -> near_threshold
        ("c", "z", 0.10, 0.95, 1),   # other, strong candidate the model rejects -> first among "other"
        ("d", "w", 0.10, 0.20, 2),   # other, weak candidate
        ("e", "v", 0.48, 0.3, 1),    # nearest to the threshold -> first
    ], "l_id string, r_id string, p double, cand_score double, cand_rank int")
    linked = spark.createDataFrame([("a", "x"), ("b", "y")], "l_id string, r_id string")
    crosswalk = {"left:a": "M1", "right:x": "M1", "left:q": "M1", "left:b": "M2", "right:y": "M2"}
    raws = {s: spark.createDataFrame([(i, f"n{i}") for i in "abcdeqxyzwv"], "id string, name string")
            for s in ("left", "right")}
    q, stats = review.build_queue(spark, cfg, scored=scored, linked=linked, threshold=0.5, model_version="run m",
                                  run_id="R", crosswalk=crosswalk, raws=raws)
    rows = q.orderBy("rank").collect()
    assert [(r.l_id, r.queue_reason) for r in rows] == [
        ("e", "near_threshold"), ("b", "near_threshold"), ("a", "high_impact"), ("c", "other"), ("d", "other")]
    assert rows[2].impact == 3 and rows[0].model_version == "run m" and json.loads(rows[0].l_record) == {"name": "ne"}
    assert stats["by_reason"] == {"high_impact": 1, "near_threshold": 2, "other": 2}
    assert q.columns == review.QUEUE_COLUMNS


def test_queue_is_capped(spark, tmp_path):
    cfg = _cfg(tmp_path, review={"max_pairs": 2})
    scored = spark.createDataFrame([(str(i), str(i), 0.1) for i in range(5)], "l_id string, r_id string, p double")
    raws = {s: spark.createDataFrame([(str(i), "n") for i in range(5)], "id string, name string") for s in ("left", "right")}
    q, stats = review.build_queue(spark, cfg, scored=scored, linked=scored.limit(0), threshold=0.5,
                                  model_version="v", run_id="R", crosswalk=None, raws=raws)
    assert q.count() == 2 and stats["pairs"] == 2


def _write_store(path, rows):
    import pyarrow as pa
    from deltalake import write_deltalake
    kinds = {"string": pa.string(), "double": pa.float64(), "timestamp": pa.timestamp("us", tz="UTC")}
    schema = pa.schema([(n, kinds[t]) for n, t in store.STORE_COLUMNS])
    t0 = datetime(2026, 10, 3, tzinfo=timezone.utc)
    full = [{**{n: None for n, _ in store.STORE_COLUMNS}, "labelled_at": t0 + timedelta(seconds=i),
             "label_id": f"id{i}", "reviewer": "me", "reason": "r", "model_version": "v", **r}
            for i, r in enumerate(rows)]
    write_deltalake(str(path), pa.Table.from_pylist(full, schema=schema), mode="append")


def test_app_labels_latest_wins_retract_and_unsure_drop(spark, tmp_path):
    cfg = _cfg(tmp_path, labels={"source": "app"})
    path = store.location(cfg)["path"]
    assert path == tmp_path / "data" / "review" / "labels"
    _write_store(path, [
        {"l_id": "a", "r_id": "x", "decision": "no_match", "is_match": 0.0},
        {"l_id": "a", "r_id": "x", "decision": "match", "is_match": 1.0},      # later: wins
        {"l_id": "b", "r_id": "y", "decision": "match", "is_match": 1.0},
        {"l_id": "b", "r_id": "y", "decision": "retract"},                      # withdrawn
        {"l_id": "c", "r_id": "z", "decision": "unsure"},                       # recorded, not a label
        {"l_id": "d", "r_id": "w", "decision": "no_match", "is_match": 0.0},   # not a candidate any more
    ])
    feats = spark.createDataFrame([("a", "x", 0.3), ("b", "y", 0.2), ("c", "z", 0.1)], "l_id string, r_id string, f double")
    usage: dict = {}
    got = {(r.l_id, r.r_id): r.label for r in app_labelled(spark, feats, cfg, usage).collect()}
    assert got == {("a", "x"): 1.0}
    assert usage["app_labels"]["decisions"] == 2 and usage["app_labels"]["used"] == 1
    assert usage["app_labels"]["not_candidates"] == 1


def test_app_labels_over_a_base(spark, tmp_path):
    lab = tmp_path / "base.csv"
    lab.write_text("l_id,r_id,is_match\na,x,0\nb,y,1\n")
    cfg = _cfg(tmp_path, labels={"source": "app", "app_base": "file", "path": str(lab)})
    _write_store(store.location(cfg)["path"], [{"l_id": "a", "r_id": "x", "decision": "match", "is_match": 1.0},
                                                {"l_id": "c", "r_id": "z", "decision": "no_match", "is_match": 0.0}])
    feats = spark.createDataFrame([("a", "x", 0.3), ("b", "y", 0.2), ("c", "z", 0.1)], "l_id string, r_id string, f double")
    usage: dict = {}
    got = {(r.l_id, r.r_id): r.label for r in app_labelled(spark, feats, cfg, usage).collect()}
    assert got == {("a", "x"): 1.0, ("b", "y"): 1.0, ("c", "z"): 0.0}
    assert usage["app_labels"]["overrode_base"] == 1


def test_missing_store_reads_empty(spark, tmp_path):
    cfg = _cfg(tmp_path, labels={"source": "app", "app_base": "none"})
    assert store.training_labels(spark, cfg).count() == 0


def test_store_location_on_databricks_and_lakebase():
    c = config.build({"profile": "databricks"})
    assert store.location(c) == {"table": "workspace.lakematch.lm_review_labels"}
    with pytest.raises(config.ConfigError, match="lakebase_label_store"):
        config.build({"profile": "databricks", "paid_features": {"lakebase_label_store": True}})
    c = config.build({"profile": "databricks", "paid_features": {"lakebase_label_store": True},
                      "labels": {"store": {"table": "lakematch_db.lakematch.review_labels"}}})
    assert store.location(c) == {"table": "lakematch_db.lakematch.review_labels"}


def test_review_config_rules():
    with pytest.raises(config.ConfigError, match="review.llm"):
        config.build({"review": {"llm": "jev"}})
    config.build({"review": {"llm": "jev"}, "paid_features": {"llm_labeller": True}})   # Jev allowed on the laptop
    with pytest.raises(config.ConfigError, match="review.band"):
        config.build({"review": {"band": 0.7}})
    with pytest.raises(config.ConfigError, match="app_base"):
        config.build({"labels": {"source": "app", "app_base": "jev"}})
    assert config.build({"labels": {"source": "app"}}).runnable_problems() == []


def test_run_record_from_summary(tmp_path):
    cfg = _cfg(tmp_path)
    rec = review.run_record(run_id="R", model_version="v", threshold=0.5, cfg=cfg, queue_stats={"pairs": 3, "by_reason": {"other": 3}},
                            summary={"evaluation": {"all": {"precision": 0.9, "recall": 0.8, "f1": 0.85}},
                                     "labels": {"train": 10, "validation": 3, "app": {"used": 2}},
                                     "quarantined": {"left": 1, "right": 0}})
    assert [n for n, _ in review.RUN_COLUMNS] == list(rec)
    assert rec["precision"] == 0.9 and rec["app_labels_used"] == 2 and rec["quarantined_left"] == 1
