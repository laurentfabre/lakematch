"""MLflow, the system of record for models (ZR-5): one composite model per run, its datasets and its evaluation.

    log_run      logs the run: params (every method choice), the input datasets (mlflow.data), the label set, the
                 composite pyfunc (model_code.py: Spark pipeline + config + label-set digest + thresholds) with a
                 pair-level signature, then mlflow.models.evaluate on a static scored dataset with pairwise metrics.
                 An accepted run (model under matcher.max_model_mb, F1 >= mlflow.accept_min_f1 when set) is then
                 published: on the laptop its run id goes to the pointer file (mlflow.pointer, models/current.json);
                 with a registry it is registered and the alias moves to the new version.
    load_current resolves the model scoring uses: runs:/<id>/model from the pointer (no registry, D17), or the
                 version behind models:/<name>@<alias>, pinned to that immutable version.

The logging code is the same everywhere; only register() is registry-specific (Unity Catalog on Databricks).
Relative sqlite tracking URIs and the pointer resolve against the config's directory, so a run gives the same store
from any working directory; artifacts sit next to the database (mlruns/), not wherever the process started.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path

from pyspark.sql import DataFrame, functions as F

from .config import Config

os.environ.setdefault("MLFLOW_DISABLE_TELEMETRY", "true")     # laptop runs are offline; no usage pings
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

log = logging.getLogger("lakematch")

MODEL_CODE = Path(__file__).with_name("model_code.py")


def tracking_uri(cfg: Config) -> str:
    uri = cfg.get("mlflow.tracking_uri")
    prefix = "sqlite:///"
    if uri.startswith(prefix) and not uri.startswith(prefix + "/"):
        return prefix + str(cfg.path(uri[len(prefix):]))
    return uri


def registered_name(cfg: Config) -> str:
    name = cfg.get("mlflow.model_name") or f"lakematch_{cfg.get('entity.name') or 'record'}"
    if "." in name:                    # already catalog.schema.name (laptop compute, UC registry: no storage.catalog)
        return name
    catalog = cfg.get("storage.catalog")
    return f"{catalog}.{name}" if catalog and (cfg.get("mlflow.registry_uri") or "").startswith("databricks-uc") else name


def configure(cfg: Config):
    """Point MLflow at the config's tracking store (and registry) and select the experiment. Returns the client."""
    import mlflow
    uri = tracking_uri(cfg)
    if uri.startswith("databricks://"):
        # MLflow 3.16's SDK artifact repository ignores the URI's profile and authenticates with the default one:
        # name it for the SDK too (measured 2026-10-02: the upload failed on DEFAULT's expired OAuth token)
        os.environ["DATABRICKS_CONFIG_PROFILE"] = uri[len("databricks://"):].split(":")[0]
    mlflow.set_tracking_uri(uri)
    if cfg.get("mlflow.registry"):
        mlflow.set_registry_uri(cfg.get("mlflow.registry_uri"))
    if cfg.get("mlflow.dfs_tmp"):
        os.environ["MLFLOW_DFS_TMP"] = cfg.get("mlflow.dfs_tmp")
    client = mlflow.MlflowClient()
    name = cfg.get("mlflow.experiment")
    if client.get_experiment_by_name(name) is None and uri.startswith("sqlite:///"):
        # the default artifact root is ./mlruns of whatever directory the first run started in: pin it to the store
        root = Path(uri[len("sqlite:///"):]).parent / "mlruns"
        client.create_experiment(name, artifact_location=root.as_uri())
    mlflow.set_experiment(name)
    return client


def label_set_digest(lab: DataFrame, cfg: Config) -> dict:
    """sha256 over the sorted (l_id, r_id, label) triples: two runs trained on the same labels share it."""
    rows = sorted((r.l_id, r.r_id, float(r.label)) for r in lab.select("l_id", "r_id", "label").collect())
    blob = "\n".join(f"{a}\t{b}\t{y:g}" for a, b, y in rows)
    return {"sha256": hashlib.sha256(blob.encode()).hexdigest(), "pairs": len(rows),
            "matches": sum(1 for *_, y in rows if y == 1.0), "source": cfg.get("labels.source"),
            "llm": cfg.get("labels.llm"), "n": cfg.get("labels.n")}


def signature(feature_cols: list[str]):
    from mlflow.models import ModelSignature
    from mlflow.types import ColSpec, Schema
    inputs = Schema([ColSpec("string", "l_id"), ColSpec("string", "r_id"), *[ColSpec("double", c) for c in feature_cols]])
    outputs = Schema([ColSpec("string", "l_id"), ColSpec("string", "r_id"), ColSpec("double", "p"),
                      ColSpec("boolean", "above_threshold")])
    return ModelSignature(inputs=inputs, outputs=outputs)


def _dir_mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 2 ** 20


def _pairwise_metrics(n_true: int):
    """Custom metrics over the static dataset: prediction = linked (after the cardinality policy), target = true
    pair. Recall divides by every true pair, the ones no candidate proposed included."""
    from mlflow.models import make_metric

    # MLflow maps eval_fn arguments by name: predictions, targets, metrics
    def tp(predictions, targets):
        return int(((predictions == 1) & (targets == 1)).sum())

    def precision(predictions, targets, metrics):
        n = int((predictions == 1).sum())
        return tp(predictions, targets) / n if n else 0.0

    def recall(predictions, targets, metrics):
        return tp(predictions, targets) / n_true if n_true else 0.0

    def f1(predictions, targets, metrics):
        p, r = precision(predictions, targets, metrics), recall(predictions, targets, metrics)
        return 2 * p * r / (p + r) if p + r else 0.0

    def cand_recall(predictions, targets, metrics):
        return int((targets == 1).sum()) / n_true if n_true else 0.0

    return [make_metric(eval_fn=fn, greater_is_better=True, name=name)
            for name, fn in (("pairwise_precision", precision), ("pairwise_recall", recall), ("pairwise_f1", f1),
                             ("candidate_recall", cand_recall))]


def evaluation_frame(cfg: Config, scored: DataFrame, linked: DataFrame, threshold: float, valid_lab: DataFrame,
                     truth: DataFrame | None):
    """The static dataset mlflow.models.evaluate scores, and the number of true pairs recall divides by.
    With a truth set: every scored candidate pair (prediction = linked, target = true pair), while they fit in
    mlflow.eval_max_pairs. Otherwise the validation labels (prediction = p >= threshold)."""
    cap = cfg.get("mlflow.eval_max_pairs")
    if truth is not None:
        truth = truth.select("l_id", "r_id").distinct()
        n_scored = scored.count()
        if n_scored <= cap:
            frame = (scored.select("l_id", "r_id", "p")
                     .join(linked.select("l_id", "r_id", F.lit(1).alias("prediction")), ["l_id", "r_id"], "left")
                     .join(truth.withColumn("label", F.lit(1)), ["l_id", "r_id"], "left")
                     .fillna(0, ["prediction", "label"]))
            return frame.toPandas(), truth.count(), "candidates_vs_truth"
        log.warning("mlflow: %d scored pairs exceed mlflow.eval_max_pairs %d — evaluating on the validation labels",
                    n_scored, cap)
    frame = (valid_lab.select("l_id", "r_id", "p", F.col("label").cast("int").alias("label"))
             .withColumn("prediction", (F.col("p") >= threshold).cast("int")))
    pdf = frame.toPandas()
    return pdf, int(pdf["label"].sum()), "validation_labels"


def log_run(rt, cfg: Config, *, run_name: str, model, feature_cols: list[str], threshold: float, lab: DataFrame,
            train: DataFrame, valid_scored: DataFrame, scored: DataFrame, linked: DataFrame,
            truth: DataFrame | None, raw_inputs: dict[str, DataFrame], summary: dict,
            plan: dict | None = None) -> dict:
    import mlflow
    import pyspark

    configure(cfg)
    out: dict = {"tracking_uri": tracking_uri(cfg), "experiment": cfg.get("mlflow.experiment")}
    digest = label_set_digest(lab, cfg)
    tmp = Path(tempfile.mkdtemp(prefix="lakematch_model_"))
    try:
        with mlflow.start_run(run_name=run_name) as run:
            run_id = run.info.run_id
            mlflow.log_params({k: str(v) for k, v in summary["methods"].items()})
            mlflow.log_params({"candidates.k": cfg.get("candidates.k"), "labels.source": cfg.get("labels.source"),
                               "labels.n": cfg.get("labels.n"), "decision.threshold": threshold,
                               "cluster.method": cfg.get("cluster.method"), "features": len(feature_cols)})
            mlflow.set_tags({"lakematch.label_set_sha256": digest["sha256"], "lakematch.entity": cfg.get("entity.name"),
                             "lakematch.profile": cfg.get("profile"), "lakematch.remote": str(rt.remote)})

            # datasets: both inputs as read, then the labelled pairs the classifier trained / chose its threshold on
            for side, raw in raw_inputs.items():
                spec = cfg.get(f"inputs.{side}")
                mlflow.log_input(mlflow.data.from_spark(raw, path=str(cfg.path(spec["path"])), name=side),
                                 context=f"input_{side}")
            train_pdf = train.select("l_id", "r_id", "label", *feature_cols).toPandas()
            valid_pdf = valid_scored.select("l_id", "r_id", "label", "p", *feature_cols).toPandas()
            mlflow.log_input(mlflow.data.from_pandas(train_pdf, targets="label", name=f"labels_train_{digest['sha256'][:12]}"), context="training")
            mlflow.log_input(mlflow.data.from_pandas(valid_pdf, targets="label", name=f"labels_validation_{digest['sha256'][:12]}"), context="validation")

            # the bundle: Spark pipeline + config + label-set digest + thresholds
            pipe_dir = rt.save_ml(model, tmp / "spark_pipeline")
            model_mb = _dir_mb(pipe_dir)
            (tmp / "config.json").write_text(json.dumps(cfg.data, indent=2, sort_keys=True, default=str) + "\n")
            (tmp / "label_set.json").write_text(json.dumps(digest, indent=2) + "\n")
            (tmp / "thresholds.json").write_text(json.dumps(
                {"threshold": threshold, "rule": cfg.get("decision.threshold"),
                 "cardinality": cfg.get("decision.cardinality"), "cluster_method": cfg.get("cluster.method"),
                 "feature_cols": feature_cols}, indent=2) + "\n")
            # the same classifier as one Spark SQL expression: what a pipeline flow scores with (no MLlib there)
            from .scoring_sql import compile_saved
            expr = compile_saved(pipe_dir, feature_cols)
            scoring = {"expr": expr, "feature_cols": feature_cols, "threshold": threshold,
                       "cardinality": cfg.get("decision.cardinality"), "candidate_plan": plan}
            (tmp / "scoring.json").write_text(json.dumps(scoring, indent=2) + "\n")
            info = mlflow.pyfunc.log_model(
                name="model", python_model=str(MODEL_CODE),
                artifacts={"spark_pipeline": str(pipe_dir), "config": str(tmp / "config.json"),
                           "label_set": str(tmp / "label_set.json"), "thresholds": str(tmp / "thresholds.json"),
                           "scoring": str(tmp / "scoring.json")},
                signature=signature(feature_cols),
                pip_requirements=[f"mlflow=={mlflow.__version__}", f"pyspark=={pyspark.__version__}"],
                metadata={"lakematch_label_set_sha256": digest["sha256"]})
            mlflow.log_metrics({"model_mb": round(model_mb, 3), "threshold": threshold,
                                "labels_train": summary["labels"]["train"],
                                "labels_validation": summary["labels"]["validation"],
                                "candidate_pairs": summary["candidates"]["pairs"],
                                "links": summary["decision"]["links"]})

            pdf, n_true, kind = evaluation_frame(cfg, scored, linked, threshold, valid_scored, truth)
            result = mlflow.models.evaluate(
                data=pdf[["p", "prediction", "label"]], targets="label", predictions="prediction",
                model_type="classifier", extra_metrics=_pairwise_metrics(n_true),
                evaluator_config={"log_model_explainability": False})
            metrics = {k: float(v) for k, v in result.metrics.items() if isinstance(v, (int, float))}
            out.update({"run_id": run_id, "model_uri": f"runs:/{run_id}/model", "model_id": info.model_id,
                        "model_mb": round(model_mb, 3), "label_set": digest, "evaluation_dataset": kind,
                        "evaluation_pairs": len(pdf), "metrics": {k: round(metrics[k], 4) for k in sorted(metrics)
                                                                 if k.startswith(("pairwise_", "candidate_"))}})

            # the logged bundle, reloaded from the store, must reproduce the run's own validation scores
            sample = valid_pdf.head(50)
            reloaded = mlflow.pyfunc.load_model(out["model_uri"]).predict(sample.drop(columns=["label", "p"]))
            drift = float((reloaded["p"].to_numpy() - sample["p"].to_numpy()).__abs__().max()) if len(sample) else 0.0
            out["reload_parity"] = {"pairs": len(sample), "max_abs_diff_p": drift}
            mlflow.log_metric("reload_max_abs_diff_p", drift)
            # the compiled expression must give the model's p on every validation pair
            expr_drift = valid_scored.select(F.max(F.abs(F.col("p") - F.expr(expr)))).first()[0] or 0.0
            out["expression_parity"] = {"pairs": len(valid_pdf), "max_abs_diff_p": float(expr_drift)}
            mlflow.log_metric("expression_max_abs_diff_p", float(expr_drift))

            problems = []
            if drift > 1e-9:
                problems.append(f"the reloaded model differs from the run's scores by up to {drift:.3g}")
            if expr_drift > 1e-9:
                problems.append(f"the compiled scoring expression differs from the model by up to {expr_drift:.3g}")
            if model_mb > cfg.get("matcher.max_model_mb"):
                problems.append(f"model {model_mb:.1f} MB > matcher.max_model_mb {cfg.get('matcher.max_model_mb')}")
            floor = cfg.get("mlflow.accept_min_f1")
            if floor is not None and metrics.get("pairwise_f1", 0.0) < floor:
                problems.append(f"pairwise_f1 {metrics.get('pairwise_f1', 0.0):.4f} < mlflow.accept_min_f1 {floor}")
            out["accepted"] = not problems
            if problems:
                out["rejected_because"] = problems
            mlflow.set_tag("lakematch.accepted", str(out["accepted"]).lower())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if out["accepted"]:
        if cfg.get("mlflow.registry"):
            out["registered"] = register(cfg, out["model_uri"])
            out["handoff"] = write_handoff(cfg, out, scoring)
        else:
            pointer = cfg.path(cfg.get("mlflow.pointer"))
            pointer.parent.mkdir(parents=True, exist_ok=True)
            pointer.write_text(json.dumps({
                "run_id": out["run_id"], "model_uri": out["model_uri"], "tracking_uri": out["tracking_uri"],
                "experiment": out["experiment"], "accepted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "threshold": threshold, "label_set_sha256": digest["sha256"], "metrics": out["metrics"]},
                indent=2) + "\n")
            out["pointer"] = str(pointer)
    return out


def handoff_path(cfg: Config) -> Path:
    return cfg.path(cfg.get("storage.root")) / "champion.json"


def write_handoff(cfg: Config, out: dict, scoring: dict) -> str:
    """What a pipeline flow needs from the version the alias now names, written next to the run's outputs: the
    compiled scoring expression, threshold, cardinality and candidate plan, stamped with the registered version.
    The flow cannot ask the registry itself (importing MLflow in a serverless pipeline crashes it), so the job task
    that moved the alias writes this, and the cluster task checks the links carry the version @alias still names."""
    path = handoff_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({**out["registered"], "run_id": out["run_id"], **scoring}, indent=2) + "\n")
    return str(path)


def register(cfg: Config, model_uri: str) -> dict:
    """Registry only (Unity Catalog on Databricks): a new version of the registered model, then the alias moves."""
    import mlflow
    name, alias = registered_name(cfg), cfg.get("mlflow.alias")
    mv = mlflow.register_model(model_uri, name)
    mlflow.MlflowClient().set_registered_model_alias(name, alias, mv.version)
    log.info("mlflow: registered %s version %s, @%s", name, mv.version, alias)
    return {"name": name, "version": str(mv.version), "alias": alias}


def load_current(cfg: Config):
    """The model scoring uses. No registry: runs:/<id>/model from the pointer file. Registry: the version the alias
    names right now, loaded by its immutable version URI. Returns (pyfunc model, uri)."""
    import mlflow
    configure(cfg)
    if cfg.get("mlflow.registry"):
        name, alias = registered_name(cfg), cfg.get("mlflow.alias")
        version = mlflow.MlflowClient().get_model_version_by_alias(name, alias).version
        uri = f"models:/{name}/{version}"
    else:
        pointer = cfg.path(cfg.get("mlflow.pointer"))
        if not pointer.exists():
            raise FileNotFoundError(f"{pointer}: no accepted run yet — `lakematch run` writes it")
        uri = f"runs:/{json.loads(pointer.read_text())['run_id']}/model"
    return mlflow.pyfunc.load_model(uri), uri
