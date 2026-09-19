import json

import pytest

from lakematch import tracking


def test_label_digest_is_order_and_duplicate_invariant():
    rows = [{"a_id": "a", "b_id": "b", "label": 1.}, {"a_id": "a", "b_id": "c", "label": 0.}]
    assert tracking.label_digest(rows) == tracking.label_digest([*reversed(rows), rows[0]])
    with pytest.raises(ValueError, match="Conflicting"):
        tracking.label_digest([*rows, {**rows[0], "label": 0.}])
    with pytest.raises(ValueError, match="unsure"):
        tracking.label_digest([{**rows[0], "label": .5}])
    with pytest.raises(ValueError, match="IDs"):
        tracking.label_digest([{**rows[0], "a_id": None}])


def test_artifact_integrity_rejects_changed_or_missing_files(tmp_path):
    pipeline = tmp_path / "pipeline"
    pipeline.mkdir()
    (pipeline / "part").write_text("original")
    integrity = tmp_path / "integrity.json"
    integrity.write_text(json.dumps({"pipeline": tracking.artifact_hashes(pipeline)}))
    artifacts = {"pipeline": str(pipeline), "integrity": str(integrity)}
    tracking.validate_artifacts(artifacts)
    (pipeline / "part").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        tracking.validate_artifacts(artifacts)
    (pipeline / "part").unlink()
    with pytest.raises(ValueError, match="changed"):
        tracking.validate_artifacts(artifacts)


def test_pairwise_metrics_include_false_positives_and_false_negatives():
    import pandas as pd
    predictions, targets = pd.Series([1, 1, 0, 0]), pd.Series([1, 0, 1, 0])
    assert tracking.pairwise_precision(predictions, targets) == .5
    assert tracking.pairwise_recall(predictions, targets) == .5
    assert tracking.pairwise_f1(predictions, targets) == .5


def test_composite_predictions_and_acceptance_on_active_spark(spark, config, tmp_path):
    """Same test runs against classic and Connect, exercising actual model I/O."""
    from copy import deepcopy
    import mlflow
    from lakematch import entity, features, matcher
    from lakematch.config import from_dict
    raw = deepcopy(config.data)
    raw["mlflow"]["tracking_uri"] = f"sqlite:///{tmp_path}/mlflow.db"
    cfg = from_dict(raw)
    left = spark.createDataFrame([("a1", "alice", "1"), ("a2", "bob", "2")], "rec_id string, name string, code string")
    right = spark.createDataFrame([("b1", "alice", "1"), ("b2", "bob", "2")], left.schema)
    pairs = spark.createDataFrame([(f"a{i}", f"b{j}", .5, j, 0.) for i in (1, 2) for j in (1, 2)],
                                  "a_id string, b_id string, cos double, rank long, gap double")
    labels = [{"a_id": f"a{i}", "b_id": f"b{j}", "label": float(i == j)} for i in (1, 2) for j in (1, 2)]
    frame = features.build(pairs, entity.prepare(left, cfg), entity.prepare(right, cfg), cfg)
    model = matcher.train(frame, spark.createDataFrame(labels), cfg)
    snapshot = tracking.pair_snapshot(pairs, left, right, cfg)
    result = tracking.log_composite(model, cfg, labels=labels, input_example=snapshot.head(1),
                                   experiment="unit-model", staging_root=tmp_path / "staging")
    loaded = tracking.load_composite(result["model_uri"], cfg)
    predictions = loaded.predict(snapshot)
    native = matcher.score(frame, model).orderBy("a_id", "b_id").select("p").toPandas().p
    assert predictions.p.tolist() == pytest.approx(native.tolist(), abs=1e-12)
    with mlflow.start_run(run_id=result["run_id"]):
        evaluation = tracking.evaluate_pairs(predictions, labels, context="training_diagnostic")
    pointer = tmp_path / "models/current.json"
    tracking.accept_local(result, cfg, evaluation, minimum_f1=1., pointer=pointer)
    assert json.loads(pointer.read_text())["accepted"] is True
    assert tracking.resolve_model(cfg, pointer) == result["model_uri"]
    assert not list(mlflow.MlflowClient().search_registered_models())
    dataset_names = {d.dataset.name for d in mlflow.MlflowClient().get_run(result["run_id"]).inputs.dataset_inputs}
    assert dataset_names == {"training_labels", "training_diagnostic_pairs"}
    broken = snapshot.copy()
    broken.loc[0, "left"] = json.dumps({"name": "changed", "code": "1"})
    with pytest.raises(ValueError, match="conflicting payloads"):
        loaded.predict(broken)
    before = pointer.read_bytes()
    with pytest.raises(ValueError, match="recorded MLflow evaluation"):
        tracking.accept_local(result, cfg, {"pairwise_f1": .9}, minimum_f1=.8, pointer=pointer)
    assert before == pointer.read_bytes()
