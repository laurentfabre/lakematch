"""One composite artifact, SQLite tracking locally, optional UC registration.

The pyfunc runs in a driver/job with Spark, never inside a Spark UDF. Its input
is a complete candidate snapshot: cardinality decisions need all competitors.
"""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import tempfile

import mlflow
from mlflow.models import ModelSignature
from mlflow.tracking import MlflowClient
from mlflow.types import ColSpec, Schema

from .features import feature_order


def artifact_hashes(path):
    path = Path(path)
    files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
    return {p.name if path.is_file() else str(p.relative_to(path)):
            hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def validate_artifacts(artifacts):
    expected = json.loads(Path(artifacts["integrity"]).read_text())
    if set(expected) != set(artifacts) - {"integrity"}:
        raise ValueError("Composite model artifact inventory differs from its manifest")
    for name, hashes in expected.items():
        if artifact_hashes(artifacts[name]) != hashes:
            raise ValueError(f"Composite model artifact changed: {name}")


def pair_snapshot(pairs, left, right, config):
    """Capture raw values and frozen retrieval features without losing arrays."""
    from pyspark.sql import functions as F
    frame = pairs.select("a_id", "b_id", "cos", "rank", "gap")
    for side, source, key in (("left", left, "a_id"), ("right", right, "b_id")):
        payload = source.select(F.col(config["entity"]["id_column"]).alias(key),
            F.to_json(F.struct(*[F.col(n) for n in config.fields]), {"ignoreNullFields": "false"}).alias(side))
        frame = frame.join(payload, key, "inner")
    rows = frame.orderBy("a_id", "b_id").limit(config["candidates"]["max_pairs"] + 1).toPandas()
    if len(rows) > config["candidates"]["max_pairs"]:
        raise ValueError("Pair snapshot exceeds the configured driver pair budget")
    rows["rank"] = rows["rank"].astype("int64")
    return rows[["a_id", "b_id", "left", "right", "cos", "rank", "gap"]]


def label_digest(rows):
    observed = {}
    for row in rows:
        row = row.asDict() if hasattr(row, "asDict") else dict(row)
        pair = row["a_id"], row["b_id"]
        if any(not isinstance(k, str) or not k for k in pair):
            raise ValueError("Label snapshots need nonempty string IDs")
        value = float(row["label"])
        if value not in (0., 1.):
            raise ValueError("Label snapshots must explicitly exclude unsure/unresolved labels")
        if pair in observed and observed[pair] != value:
            raise ValueError("Conflicting label snapshot")
        observed[pair] = value
    canonical = json.dumps([[a, b, y] for (a, b), y in sorted(observed.items())], separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest(), canonical


def pairwise_precision(predictions, targets, metrics=None):
    tp = int(((predictions == 1) & (targets == 1)).sum())
    return tp / max(1, int((predictions == 1).sum()))


def pairwise_recall(predictions, targets, metrics=None):
    tp = int(((predictions == 1) & (targets == 1)).sum())
    return tp / max(1, int((targets == 1).sum()))


def pairwise_f1(predictions, targets, metrics=None):
    p, r = pairwise_precision(predictions, targets), pairwise_recall(predictions, targets)
    return 2 * p * r / (p + r) if p + r else 0.


def evaluate_pairs(predictions, labels, *, context="validation"):
    """Evaluate static pair decisions, including missed candidates as false negatives.

    Predictions must be computed on the complete candidate snapshot BEFORE
    restricting metrics to labelled pairs. Unlabelled pairs are not negatives.
    """
    import pandas as pd
    digest, snapshot = label_digest(labels)
    truth = pd.DataFrame(json.loads(snapshot), columns=["a_id", "b_id", "label"])
    if not len(truth) or set(truth.label) != {0., 1.}:
        raise ValueError("Evaluation needs an explicit static dataset with both classes")
    if predictions.duplicated(["a_id", "b_id"]).any():
        raise ValueError("Evaluation predictions contain duplicate pair keys")
    data = truth.merge(predictions[["a_id", "b_id", "is_link"]], on=["a_id", "b_id"], how="left")
    data["prediction"] = data.pop("is_link").eq(True).astype("int64")
    data["label"] = data["label"].astype("int64")
    dataset = mlflow.data.from_pandas(data, name=f"{context}_pairs", targets="label",
                                     predictions="prediction", digest=digest[:32])
    mlflow.log_input(dataset, context=context, tags={"label_set_sha256": digest})
    result = mlflow.models.evaluate(data=dataset, model_type="classifier",
        extra_metrics=[mlflow.models.make_metric(eval_fn=fn, greater_is_better=True)
                       for fn in (pairwise_precision, pairwise_recall, pairwise_f1)],
        evaluator_config={"log_model_explainability": False})
    mlflow.log_dict({"context": context, "label_set_sha256": digest, "rows": len(data),
                     "unlabelled_pairs_are_negatives": False}, "evaluation_contract.json")
    return {str(k): float(v) for k, v in result.metrics.items()}


def signature():
    return ModelSignature(inputs=Schema([ColSpec("string", n) for n in ("a_id", "b_id", "left", "right")] +
        [ColSpec("double", "cos"), ColSpec("long", "rank"), ColSpec("double", "gap")]),
        outputs=Schema([ColSpec("string", "a_id"), ColSpec("string", "b_id"), ColSpec("double", "p"), ColSpec("boolean", "is_link")]))


def log_composite(model, config, *, labels, input_example, experiment, staging_root, idf_path=None, metrics=None):
    if config["decision"]["threshold"] == "from_validation":
        raise ValueError("Freeze a validation threshold before logging a deployable model")
    if config["profile"] == "databricks" and not str(Path(staging_root)).startswith("/Volumes/"):
        raise ValueError("Remote model staging must be on an owned UC volume")
    if config["profile"] == "laptop" and not config["mlflow"]["tracking_uri"].startswith("sqlite:///"):
        raise ValueError("Laptop model tracking requires SQLite, without a registry")
    mlflow.set_tracking_uri(config["mlflow"]["tracking_uri"])
    mlflow.set_experiment(experiment)
    digest, label_snapshot = label_digest(labels)
    Path(staging_root).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lakematch-model-", dir=staging_root) as temporary:
        root = Path(temporary)
        pipeline = root / "pipeline"
        model.write().save(str(pipeline))
        (root / "labels.json").write_text(label_snapshot + "\n")
        contract = {"schema_version": 1, "config": config.data, "feature_order": feature_order(config),
                    "label_set_sha256": digest, "input_scope": "complete candidate-pair snapshot; frozen retriever features supplied",
                    "decision_scope": "cardinality over the complete input snapshot, not across separate predict calls"}
        (root / "contract.json").write_text(json.dumps(contract, indent=2) + "\n")
        artifacts = {"pipeline": str(pipeline), "contract": str(root / "contract.json"), "labels": str(root / "labels.json")}
        if "idf_token_cosine" in config["features"]["multi_token"]:
            if not idf_path:
                raise ValueError("Composite IDF features require the immutable training vocabulary artifact")
            artifacts["idf"] = str(idf_path)
        embedding = config["features"]["embeddings"]
        if embedding["fields_of_type"] and embedding["provider"] != "none":
            if not embedding["model"] or not Path(embedding["model"]).is_dir():
                raise ValueError("Logging enabled embedding features requires their prepared local model snapshot")
            artifacts["embedding_model"] = embedding["model"]
        integrity = {name: artifact_hashes(path) for name, path in artifacts.items()}
        (root / "integrity.json").write_text(json.dumps(integrity, sort_keys=True) + "\n")
        artifacts["integrity"] = str(root / "integrity.json")
        size = sum(p.stat().st_size for value in artifacts.values() for p in
                   ([Path(value)] if Path(value).is_file() else Path(value).rglob("*")) if p.is_file())
        if size > config["matcher"]["max_model_mb"] * 1024 * 1024:
            raise ValueError("Complete model artifacts exceed the recorded model-size cap")
        with mlflow.start_run(run_name=config["entity"]["name"]) as run:
            mlflow.log_params({"estimator": config["matcher"]["estimator"], "threshold": config["decision"]["threshold"],
                               "cardinality": config["decision"]["cardinality"], "label_set_sha256": digest,
                               "model_artifact_bytes": size})
            if metrics:
                mlflow.log_metrics(metrics)
            mlflow.log_dict(contract, "contract.json")
            import pandas as pd
            label_frame = pd.DataFrame(json.loads(label_snapshot), columns=["a_id", "b_id", "label"])
            mlflow.log_input(mlflow.data.from_pandas(label_frame, name="training_labels", digest=digest[:32], targets="label"),
                             context="training", tags={"label_set_sha256": digest})
            requirements = [f"{name}=={importlib.metadata.version(name)}" for name in ("mlflow", "pyspark", "pyyaml")]
            if "embedding_model" in artifacts:
                requirements += [f"sentence-transformers=={importlib.metadata.version('sentence-transformers')}"]
            info = mlflow.pyfunc.log_model(name="model", python_model=str(Path(__file__).with_name("composite_model.py")),
                artifacts=artifacts, signature=signature(), input_example=input_example,
                code_paths=[str(Path(__file__).parent)],
                pip_requirements=requirements,
                metadata={"label_set_sha256": digest, "candidate_spec": config["candidates"], "feature_spec": config["features"]})
            # Include code, signature, requirements and all MLflow metadata in the cap.
            downloaded = mlflow.artifacts.download_artifacts(artifact_uri=info.model_uri, dst_path=str(root / "logged"))
            size = sum(p.stat().st_size for p in Path(downloaded).rglob("*") if p.is_file())
            if size > config["matcher"]["max_model_mb"] * 1024 * 1024:
                raise ValueError("Complete logged model exceeds the recorded model-size cap")
            mlflow.log_metric("complete_model_bytes", size)
            result = {"run_id": run.info.run_id, "model_uri": f"runs:/{run.info.run_id}/model", "logged_model_uri": info.model_uri,
                      "label_set_sha256": digest, "artifact_bytes": size, "registry": False}
    return result


def load_composite(model_uri, config, staging_root=None):
    mlflow.set_tracking_uri(config["mlflow"]["tracking_uri"])
    if config["profile"] == "databricks":
        if not staging_root or not str(Path(staging_root)).startswith("/Volumes/"):
            raise ValueError("Remote model downloads require staging on an owned UC volume")
        mlflow.set_registry_uri("databricks-uc")
        Path(staging_root).mkdir(parents=True, exist_ok=True)
        path = mlflow.artifacts.download_artifacts(artifact_uri=model_uri, dst_path=str(staging_root))
        return mlflow.pyfunc.load_model(path)
    return mlflow.pyfunc.load_model(model_uri)


def accept_local(result, config, evaluation, *, minimum_f1, pointer="models/current.json"):
    """Atomically promote an evaluated run; never create a local registry."""
    score = evaluation.get("pairwise_f1", float("nan"))
    if not 0 <= minimum_f1 <= 1 or not score >= minimum_f1:
        raise ValueError("Model did not meet the declared acceptance F1")
    if config["profile"] != "laptop" or result.get("registry"):
        raise ValueError("The local accepted-run pointer is for tracking-only laptop models")
    client = MlflowClient(tracking_uri=config["mlflow"]["tracking_uri"])
    run = client.get_run(result["run_id"])
    if run.info.status != "FINISHED" or run.data.metrics.get("pairwise_f1") != score:
        raise ValueError("Acceptance needs a finished run and its recorded MLflow evaluation")
    path = Path(pointer)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {**result, "accepted": True, "tracking_uri": config["mlflow"]["tracking_uri"], "evaluation": evaluation,
            "minimum_f1": minimum_f1}
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as out:
        temporary = Path(out.name)
        out.write(json.dumps(body, indent=2) + "\n")
    os.replace(temporary, path)
    return body


def resolve_model(config, pointer="models/current.json"):
    """Resolve a mutable pointer once; callers score with the immutable result."""
    if config["mlflow"]["registry"]:
        if config["profile"] != "databricks":
            raise ValueError("Registry resolution requires the Databricks profile")
        spec = config["mlflow"]
        client = MlflowClient(tracking_uri=spec["tracking_uri"], registry_uri="databricks-uc")
        version = client.get_model_version_by_alias(spec["model_name"], spec["alias"])
        return f"models:/{spec['model_name']}/{version.version}"
    body = json.loads(Path(pointer).read_text())
    if body["tracking_uri"] != config["mlflow"]["tracking_uri"] or body.get("registry"):
        raise ValueError("Accepted model pointer refers to a different tracking context")
    if body["model_uri"] != f"runs:/{body['run_id']}/model":
        raise ValueError("Accepted local model must resolve by immutable run ID")
    return body["model_uri"]


def register_uc(model_uri, config):
    if config["profile"] != "databricks" or not config["mlflow"]["registry"]:
        raise ValueError("UC registration is enabled only by an explicit Databricks registry config")
    spec = config["mlflow"]
    if len(spec["model_name"].split(".")) != 3 or not spec["alias"]:
        raise ValueError("UC registration needs catalog.schema.model and an alias")
    mlflow.set_registry_uri("databricks-uc")
    version = mlflow.register_model(model_uri, spec["model_name"], await_registration_for=120)
    client = MlflowClient(registry_uri="databricks-uc")
    client.set_registered_model_alias(spec["model_name"], spec["alias"], version.version)
    resolved = client.get_model_version_by_alias(spec["model_name"], spec["alias"])
    if str(resolved.version) != str(version.version):
        raise RuntimeError("Registry alias read-back differs from the version just promoted")
    return {"registry": True, "name": spec["model_name"], "version": str(resolved.version), "alias": spec["alias"],
            "immutable_model_uri": f"models:/{spec['model_name']}/{resolved.version}"}
