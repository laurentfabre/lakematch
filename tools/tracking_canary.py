#!/usr/bin/env python3
"""Synthetic model-contract acceptance, never benchmark-quality evidence."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import time

import mlflow
import pandas as pd
from pyspark.sql import functions as F

from lakematch import decision, entity, features, feature_stats, matcher, tracking
from lakematch.config import from_dict
from lakematch.runtime import active_or_create


def fixture(spark, config, prefix, names):
    raw = spark.createDataFrame([(f"{prefix}a{i}", n, str(i)) for i, n in enumerate(names)],
                               "rec_id string, name string, code string")
    right = spark.createDataFrame([(f"{prefix}b{i}", n, str(i)) for i, n in enumerate(names)], raw.schema)
    pairs = spark.createDataFrame([(f"{prefix}a{i}", f"{prefix}b{j}", .5, j + 1, 0.)
                                   for i in range(len(names)) for j in range(len(names))],
                                  "a_id string, b_id string, cos double, rank long, gap double")
    labels = [{"a_id": f"{prefix}a{i}", "b_id": f"{prefix}b{j}", "label": float(i == j)}
              for i in range(len(names)) for j in range(len(names))]
    return raw, right, pairs, labels


def configuration(root, remote=False):
    raw = {"entity": {"name": "tracking_canary", "fields": {"name": {"type": "person_name"}, "code": {"type": "code"}}},
           "features": {"multi_token": ["idf_token_cosine"], "embeddings": {"provider": "none"}},
           "decision": {"threshold": .5}, "matcher": {"max_iter": 3, "max_depth": 2},
           "candidates": {"method": "gram_topk", "max_pairs": 100},
           "mlflow": {"tracking_uri": f"sqlite:///{root.resolve()}/mlflow.db"}}
    if remote:
        raw.update(profile="databricks", runtime={"mode": "serverless", "cli_profile": "fevm-gdpr2"},
            quality={"engine": "native"}, paid_features={"app": False, "genie": False},
            mlflow={"tracking_uri": "databricks", "registry": True,
                    "model_name": "gdpr2_catalog.lakematch_20260919.pair_model", "alias": "champion"})
    return from_dict(raw)


def train(root, remote=False):
    started = time.perf_counter()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    config = configuration(root, remote)
    spark = active_or_create(config)
    (root / "config.json").write_text(json.dumps(config.data, indent=2))
    left, right, pairs, labels = fixture(spark, config, "train", ["alice martin", "bob dupont", "carol smith", "dan evans"])
    a, b = entity.prepare(left, config), entity.prepare(right, config)
    idf = root / "training_idf"
    feature_stats.fit_idf([a, b], config).write.mode("overwrite").parquet(str(idf.resolve()))
    vocabulary = spark.read.parquet(str(idf.resolve()))
    a, b = [feature_stats.attach_idf(f, vocabulary, config) for f in (a, b)]
    model = matcher.train(features.build(pairs, a, b, config), spark.createDataFrame(labels), config)
    example = tracking.pair_snapshot(pairs, left, right, config).head(2)
    experiment = "/Users/laurent.fabre@databricks.com/lakematch/20260919/models" if remote else "lakematch-zr5"
    result = tracking.log_composite(model, config, labels=labels, input_example=example, experiment=experiment,
                                   staging_root=root / "staging", idf_path=idf)
    left, right, pairs, evaluation_labels = fixture(spark, config, "eval", ["elise ward", "fred otto", "gina chan", "hugo roy"])
    snapshot = tracking.pair_snapshot(pairs, left, right, config)
    snapshot.to_json(root / "pairs.json", orient="records", indent=2)
    (root / "labels.json").write_text(json.dumps(evaluation_labels))
    a, b = [feature_stats.attach_idf(entity.prepare(f, config), vocabulary, config) for f in (left, right)]
    scores = matcher.score(features.build(pairs, a, b, config), model)
    links = decision.links(scores, config).select("a_id", "b_id", F.lit(True).alias("is_link"))
    expected = scores.select("a_id", "b_id", "p").join(links, ["a_id", "b_id"], "left").fillna(False).toPandas()
    expected = expected.sort_values(["a_id", "b_id"]).reset_index(drop=True)
    loaded = tracking.load_composite(result["model_uri"], config, root / "loaded")
    actual = loaded.predict(snapshot)
    assert actual[["a_id", "b_id", "is_link"]].equals(expected[["a_id", "b_id", "is_link"]])
    assert (actual.p - expected.p).abs().max() < 1e-12
    actual.to_json(root / "expected.json", orient="records", double_precision=15)
    with mlflow.start_run(run_id=result["run_id"]):
        evaluation = tracking.evaluate_pairs(actual, evaluation_labels)
    assert evaluation["pairwise_f1"] == 1., evaluation
    result.update(evaluation=evaluation, native_pyfunc_equivalence=True, config=config.data,
                  training_evaluation_records_disjoint=True, spark=spark.version,
                  execution_seconds=time.perf_counter() - started)
    if remote:
        result.update(tracking.register_uc(result["model_uri"], config))
        assert tracking.resolve_model(config) == result["immutable_model_uri"]
    (root / "train.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def reload(root):
    root = Path(root)
    result = json.loads((root / "train.json").read_text())
    config = from_dict(result["config"])
    uri = tracking.resolve_model(config) if result["registry"] else result["model_uri"]
    loaded = tracking.load_composite(uri, config, root / "fresh_loaded")
    actual = loaded.predict(pd.read_json(root / "pairs.json"))
    expected = pd.read_json(root / "expected.json")
    assert actual[["a_id", "b_id", "is_link"]].equals(expected[["a_id", "b_id", "is_link"]])
    delta = float((actual.p - expected.p).abs().max())
    assert delta < 1e-12, delta
    # Reject conflicting payloads and duplicate pairs before Spark execution.
    duplicate = pd.concat([pd.read_json(root / "pairs.json")] * 2, ignore_index=True)
    try:
        loaded.predict(duplicate)
    except ValueError as exc:
        assert "unique pair keys" in str(exc)
    else:
        raise AssertionError("Duplicate pair snapshot was accepted")
    result.update(fresh_session_equivalence=True, maximum_probability_difference=delta,
                  resolved_model_uri=uri, status="completed", cleanup="succeeded")
    if not result["registry"]:
        pointer = root / "models" / "current.json"
        tracking.accept_local(result, config, result["evaluation"], minimum_f1=1., pointer=pointer)
        assert tracking.resolve_model(config, pointer) == uri
        before = pointer.read_bytes()
        try:
            tracking.accept_local(result, config, result["evaluation"], minimum_f1=1.1, pointer=pointer)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid acceptance gate was accepted")
        assert before == pointer.read_bytes()
        result["accepted_pointer"] = str(pointer)
        result["local_registered_models"] = len(mlflow.MlflowClient().search_registered_models())
        assert result["local_registered_models"] == 0
    (root / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["train", "reload"])
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    from offline_run import assert_offline
    assert_offline()
    try:
        result = train(Path(args.root)) if args.mode == "train" else reload(args.root)
        print(json.dumps(result, indent=2))
    finally:
        from pyspark.sql import SparkSession
        session = SparkSession.getActiveSession()
        if session:
            session.stop()
