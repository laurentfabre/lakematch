"""Job orchestrator. The imported transforms themselves remain lazy."""
import json
from pathlib import Path
import time

from pyspark.sql import functions as F

from . import blocking, candidates, decision, embeddings, entity, features, feature_stats, matcher, tracking
from .config import from_dict
from .quality import apply_and_split
from .runtime import Materializer, create_session, probe


def read_records(spark, path, config):
    if not path:
        raise ValueError("Set input.left and input.right to prepared local corpus paths")
    if config["input"]["format"] == "csv" and any(s.get("multiple") for s in config["entity"]["fields"].values()):
        raise ValueError("Array-valued fields require JSON or Parquet input, not CSV")
    if config["input"]["format"] == "csv":
        # An explicit CSV schema is positional in Spark, even with header=True.
        # Read the header as names first so YAML ordering cannot relabel values.
        return spark.read.option("header", True).csv(path).select(*[
            F.col(name).cast("string").alias(name) for name in [config["entity"]["id_column"], *config.fields]])
    schema = f"`{config['entity']['id_column']}` string, " + ", ".join(
        f"`{n}` " + ("array<string>" if s.get("multiple") else "string") for n, s in config["entity"]["fields"].items())
    return spark.read.schema(schema).option("header", True).format(config["input"]["format"]).load(path)


def read_labels(spark, path):
    return spark.read.option("header", True).csv(path).select(
        F.col("a_id").cast("string"), F.col("b_id").cast("string"), F.col("label").cast("double"))


def assert_disjoint_labels(training, validation):
    # Include every training-input endpoint: even a noncandidate label can
    # select a record for fitting the IDF vocabulary before classifier fitting.
    for key in ("a_id", "b_id"):
        if training.select(key).intersect(validation.select(key)).limit(1).count():
            raise ValueError("CLI acceptance requires training/validation record-disjoint labels")


def execute(config, *, command="run"):
    started = time.perf_counter()  # Includes session startup; caller also records process wall time.
    config.require_implemented()
    if config["decision"]["threshold"] == "from_validation":
        raise ValueError("Freeze an explicit decision.threshold before running or training a deployable model")
    spark = create_session(config)
    try:
        capabilities = probe(spark)
        with Materializer(spark, config, capabilities) as materializer:
            quality = [apply_and_split(read_records(spark, config["input"][side], config), config) for side in ("left", "right")]
            left, right = [materializer.materialize(entity.prepare(q.valid, config), side)
                           for q, side in zip(quality, ("left", "right"))]
            model_path = Path(config["model"]["path"])
            training = command == "train" or bool(config["input"]["labels"])
            labels = None
            evaluation_labels = None
            model_record, loaded = None, None
            candidate_state, state_path = None, None
            if training:
                if not config["input"]["labels"]:
                    raise ValueError("Training requires input.labels")
                labels = read_labels(spark, config["input"]["labels"])
                if config["input"]["validation_labels"]:
                    validation = read_labels(spark, config["input"]["validation_labels"])
                    assert_disjoint_labels(labels, validation)
                    evaluation_labels = validation.limit(config["candidates"]["max_pairs"] + 1).collect()
                    if len(evaluation_labels) > config["candidates"]["max_pairs"]:
                        raise ValueError("Evaluation label snapshot exceeds the configured driver pair budget")
            else:
                uri = tracking.resolve_model(config, config["model"]["pointer"])
                loaded = tracking.load_composite(uri, config, model_path / "loaded").unwrap_python_model()
                frozen = from_dict(loaded.contract["config"])
                if (frozen.fields != config.fields or loaded.contract["feature_order"] != features.feature_order(config) or any(
                    frozen[key] != config[key] for key in ("entity", "candidates", "features", "decision"))):
                    raise ValueError("Model contract differs from scoring config")
                model = loaded.native_model(spark)
                model_record = {"model_uri": uri, "registry": config["mlflow"]["registry"]}
            if blocking.needs_state(config):
                if training:
                    training_records = [frame.join(labels.select(F.col(key).alias("rec_id")).distinct(), "rec_id", "semi")
                                        for frame, key in ((left, "a_id"), (right, "b_id"))]
                    candidate_state = blocking.prepare_state(*training_records, labels, config)
                    state_path = str(model_path.resolve() / "retriever")
                    blocking.save_state(candidate_state, state_path)
                else:
                    candidate_state = blocking.load_state(loaded.artifacts["retriever"])
            if "idf_token_cosine" in config["features"]["multi_token"]:
                vocab_path = str(model_path.resolve() / "idf")
                if training:
                    labelled = [frame.join(labels.select(F.col(key).alias("rec_id")).distinct(), "rec_id", "semi")
                                for frame, key in ((left, "a_id"), (right, "b_id"))]
                    feature_stats.fit_idf(labelled, config).write.mode("overwrite").parquet(vocab_path)
                else:
                    vocab_path = loaded.artifacts["idf"]
                vocabulary = materializer.materialize(spark.read.parquet(vocab_path), "idf")
                left, right = [materializer.materialize(feature_stats.attach_idf(frame, vocabulary, config), f"weighted_{side}")
                               for side, frame in (("left", left), ("right", right))]
            embedding_reports = {}
            prepared = []
            for side, frame in (("left", left), ("right", right)):
                frame, embedding_reports[side] = embeddings.prepare(frame, loaded.config if loaded else config,
                    Path(config["output"]["root"]) / "embeddings" / f"{side}.jsonl")
                prepared.append(frame)
            left, right = prepared
            candidate_plan = candidates.build(left, right, config, state=candidate_state)
            budget = candidate_plan.validate_budget()
            comparisons = materializer.materialize(features.build(candidate_plan.pairs, left, right, config), "features")
            if training:
                # Track labels actually consumed by fitting, not every noncandidate
                # negative in a public Cartesian development-label file.
                consumed = labels.join(comparisons.select("a_id", "b_id"), ["a_id", "b_id"], "semi")
                label_rows = consumed.limit(config["candidates"]["max_pairs"] + 1).collect()
                if len(label_rows) > config["candidates"]["max_pairs"]:
                    raise ValueError("Label snapshot exceeds the configured driver pair budget")
                model = matcher.train(comparisons, labels, config)
                example = tracking.pair_snapshot(comparisons.orderBy("a_id", "b_id").limit(5), quality[0].valid, quality[1].valid, config)
                model_record = tracking.log_composite(model, config, labels=label_rows, input_example=example,
                    experiment=config["mlflow"]["experiment"], staging_root=model_path / "staging",
                    idf_path=vocab_path if "idf_token_cosine" in config["features"]["multi_token"] else None,
                    candidate_state_path=state_path)
            scored = matcher.score(comparisons, model)
            result = decision.links(scored, config)
            if training:
                import mlflow
                validation_path = config["input"]["validation_labels"]
                if not validation_path:
                    evaluation_labels = label_rows
                decisions = scored.select("a_id", "b_id").join(
                    result.select("a_id", "b_id", F.lit(True).alias("is_link")), ["a_id", "b_id"], "left").fillna(False).toPandas()
                with mlflow.start_run(run_id=model_record["run_id"]):
                    evaluation = tracking.evaluate_pairs(decisions, evaluation_labels,
                        context="validation" if validation_path else "training_diagnostic")
                model_record.update(evaluation=evaluation, accepted=False)
                acceptance = config["mlflow"]["acceptance_f1"]
                if acceptance is not None:
                    if not validation_path:
                        raise ValueError("Automatic acceptance requires input.validation_labels")
                    if evaluation["pairwise_f1"] < acceptance:
                        raise ValueError("Model did not meet its declared validation acceptance F1")
                    if config["mlflow"]["registry"]:
                        model_record.update(tracking.register_uc(model_record["model_uri"], config))
                    else:
                        tracking.accept_local(model_record, config, evaluation, minimum_f1=acceptance,
                                              pointer=config["model"]["pointer"])
                    model_record["accepted"] = True
            out = Path(config["output"]["root"])
            result.write.mode("overwrite").parquet(str(out / "links"))
            quarantine_counts = {}
            for side, q in zip(("left", "right"), quality):
                q.quarantined.write.mode("overwrite").parquet(str(out / f"quarantine_{side}"))
                quarantine_counts[side] = q.quarantined.count()
            report = {"capabilities": capabilities.to_dict(), "candidate_budget": budget,
                      "links": result.count(), "quarantine": quarantine_counts, "embedding_preparation": embedding_reports,
                      "enabled_paid_features": config.enabled_paid, "materialization": materializer.events, "model": model_record}
        report["cleanup"] = "succeeded"
    finally:
        spark.stop()
    report["wall_seconds_including_spark_start_stop"] = time.perf_counter() - started
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
