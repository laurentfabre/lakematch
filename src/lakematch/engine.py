"""Job orchestrator. The imported transforms themselves remain lazy."""
import json
from pathlib import Path
import time

from pyspark.sql import functions as F

from . import candidates, decision, embeddings, entity, features, feature_stats, matcher
from .quality import apply_and_split
from .runtime import Materializer, create_session, probe


def read_records(spark, path, config):
    if not path:
        raise ValueError("Set input.left and input.right to prepared local corpus paths")
    if config["input"]["format"] == "csv" and any(s.get("multiple") for s in config["entity"]["fields"].values()):
        raise ValueError("Array-valued fields require JSON or Parquet input, not CSV")
    schema = f"`{config['entity']['id_column']}` string, " + ", ".join(
        f"`{n}` " + ("array<string>" if s.get("multiple") else "string") for n, s in config["entity"]["fields"].items())
    return spark.read.schema(schema).option("header", True).format(config["input"]["format"]).load(path)


def execute(config, *, command="run"):
    started = time.perf_counter()  # Includes session startup; caller also records process wall time.
    config.require_implemented()
    if config["decision"]["threshold"] == "from_validation":
        raise ValueError("ZR-1 requires an explicit decision.threshold; validation selection lands in ZR-3")
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
            if training:
                if not config["input"]["labels"]:
                    raise ValueError("Training requires input.labels")
                labels = spark.read.option("header", True).schema("a_id string, b_id string, label double").csv(config["input"]["labels"])
            if "idf_token_cosine" in config["features"]["multi_token"]:
                vocab_path = str(model_path.resolve() / "idf")
                if training:
                    labelled = [frame.join(labels.select(F.col(key).alias("rec_id")).distinct(), "rec_id", "semi")
                                for frame, key in ((left, "a_id"), (right, "b_id"))]
                    feature_stats.fit_idf(labelled, config).write.mode("overwrite").parquet(vocab_path)
                vocabulary = materializer.materialize(spark.read.parquet(vocab_path), "idf")
                left, right = [materializer.materialize(feature_stats.attach_idf(frame, vocabulary, config), f"weighted_{side}")
                               for side, frame in (("left", left), ("right", right))]
            embedding_reports = {}
            prepared = []
            for side, frame in (("left", left), ("right", right)):
                frame, embedding_reports[side] = embeddings.prepare(frame, config,
                    Path(config["output"]["root"]) / "embeddings" / f"{side}.jsonl")
                prepared.append(frame)
            left, right = prepared
            candidate_plan = candidates.build(left, right, config)
            budget = candidate_plan.validate_budget()
            comparisons = materializer.materialize(features.build(candidate_plan.pairs, left, right, config), "features")
            if training:
                model = matcher.train(comparisons, labels, config)
                model.write().overwrite().save(str(model_path.resolve() / "pipeline"))
                model_path.mkdir(parents=True, exist_ok=True)
                (model_path / "contract.json").write_text(json.dumps({"config": config.data, "features": features.feature_order(config)}, indent=2) + "\n")
            else:
                from pyspark.ml import PipelineModel
                contract = json.loads((model_path / "contract.json").read_text())
                if contract["features"] != features.feature_order(config) or any(
                    contract["config"][key] != config[key] for key in ("entity", "candidates", "features", "decision")):
                    raise ValueError("Model contract differs from scoring config")
                model = PipelineModel.load(str(model_path.resolve() / "pipeline"))
            result = decision.links(matcher.score(comparisons, model), config)
            out = Path(config["output"]["root"])
            result.write.mode("overwrite").parquet(str(out / "links"))
            quarantine_counts = {}
            for side, q in zip(("left", "right"), quality):
                q.quarantined.write.mode("overwrite").parquet(str(out / f"quarantine_{side}"))
                quarantine_counts[side] = q.quarantined.count()
            report = {"capabilities": capabilities.to_dict(), "candidate_budget": budget,
                      "links": result.count(), "quarantine": quarantine_counts, "embedding_preparation": embedding_reports,
                      "enabled_paid_features": config.enabled_paid, "materialization": materializer.events}
        report["cleanup"] = "succeeded"
    finally:
        spark.stop()
    report["wall_seconds_including_spark_start_stop"] = time.perf_counter() - started
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
