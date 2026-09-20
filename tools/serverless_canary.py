# Databricks notebook source
"""Early platform probe, not ZR-5/6 acceptance. Public/synthetic inputs only."""
import json
from pathlib import Path
import platform
import sys
import time

sys.path.insert(0, "/Workspace/Users/laurent.fabre@databricks.com/lakematch/20260919/src")

import mlflow
from pyspark.ml import PipelineModel
from lakematch import candidates, decision, entity, features, matcher
from lakematch.config import from_dict
from lakematch.quality import apply_and_split
from lakematch.runtime import Materializer, probe

started = time.perf_counter()
schema = "gdpr2_catalog.lakematch_20260919"
volume = Path("/Volumes/gdpr2_catalog/lakematch_20260919/artifacts")
run_name = f"canary_{int(time.time())}"
config = from_dict({
    "profile": "databricks", "runtime": {"mode": "serverless", "cli_profile": "fevm-gdpr2"},
    "storage": {"scratch_schema": schema}, "quality": {"engine": "native"},
    "paid_features": {"app": False, "genie": False},
    "entity": {"fields": {"name": {"type": "person_name"}, "code": {"type": "code"}}},
    "features": {"multi_token": [], "embeddings": {"provider": "none"}},
    "candidates": {"method": "gram_topk", "q": 2, "k": 3, "max_join_rows": 1000, "max_pairs": 50},
    "matcher": {"max_iter": 3, "max_depth": 2}, "decision": {"threshold": .5},
})
spark.sql(f"ALTER SCHEMA {schema} DISABLE PREDICTIVE OPTIMIZATION").collect()
capabilities = probe(spark)
report = {"spark": spark.version, "python": platform.python_version(), "mlflow": mlflow.__version__,
          "capabilities": capabilities.to_dict(), "config": config.data, "run_name": run_name}
volume_probe = volume / f"{run_name}.txt"
volume_probe.write_text("lakematch synthetic canary\n")
assert volume_probe.read_text() == "lakematch synthetic canary\n"
volume_probe.unlink()
report["volume_round_trip"] = "passed"

left = spark.createDataFrame([("a1", "alice martin", "75"), ("a2", "bob dupont", "69"),
                              ("a3", "carol smith", "13")], "rec_id string, name string, code string")
right = spark.createDataFrame([("b1", "alice martyn", "75"), ("b2", "bob dupont", "69"),
                               ("b3", "carol smyth", "13")], "rec_id string, name string, code string")
with Materializer(spark, config, capabilities) as materializer:
    a, b = [materializer.materialize(entity.prepare(apply_and_split(frame, config).valid, config), side)
            for frame, side in ((left, "left"), (right, "right"))]
    plan = candidates.build(a, b, config)
    report["candidate_budget"] = plan.validate_budget()
    frame = materializer.materialize(features.build(plan.pairs, a, b, config), "features")
    labels = spark.createDataFrame([(f"a{i}", f"b{j}", float(i == j)) for i in range(1, 4) for j in range(1, 4)],
                                   "a_id string, b_id string, label double")
    model = matcher.train(frame, labels, config)
    path = str(volume / run_name / "pipeline")
    model.write().save(path)
    before = {(r.a_id, r.b_id): r.p for r in matcher.score(frame, model).select("a_id", "b_id", "p").collect()}
    after = {(r.a_id, r.b_id): r.p for r in matcher.score(frame, PipelineModel.load(path)).select("a_id", "b_id", "p").collect()}
    assert before.keys() == after.keys() and all(abs(before[k] - after[k]) < 1e-12 for k in before)
    report["prediction_reload_equivalence"] = "passed (same task; fresh-session acceptance still pending)"
    report["links"] = [r.asDict() for r in decision.links(matcher.score(frame, model), config).collect()]
    report["materialization"] = materializer.events
report["scratch_cleanup"] = "passed"
mlflow.set_experiment("/Users/laurent.fabre@databricks.com/lakematch/20260919/canary")
with mlflow.start_run(run_name=run_name) as run:
    mlflow.log_dict(report, "canary.json")
    mlflow.log_metric("links", len(report["links"]))
    report["mlflow_run_id"] = run.info.run_id
report["execution_seconds"] = time.perf_counter() - started
(volume / f"{run_name}.json").write_text(json.dumps(report, indent=2))
dbutils.notebook.exit(json.dumps(report))
