"""ZR-6: pipelines/flows.py runs on OPEN-SOURCE Spark Declarative Pipelines (`spark-pipelines`, no Databricks) and
its links equal `lakematch run`'s on the same inputs — the pipeline and the one-process laptop run are one engine.

The plan task (jobs.task_plan) writes candidate_plan.json, a laptop run trains and logs the model, its compiled
scoring expression becomes champion.json (what the train task hands the pipeline on Databricks), then the pipeline
runs gate -> entity -> candidates -> features -> scores -> links as materialized views."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from conftest import CONNECT, make_cfg
from test_pipeline import _write

pytestmark = pytest.mark.skipif(CONNECT, reason="spawns its own Spark Connect server; one pass is enough")

FIELDS = {"given": {"type": "person_name"}, "surname": {"type": "person_name"}, "street": {"type": "address"},
          "postcode": {"type": "code"}, "dob": {"type": "date"}}


def test_flows_run_on_open_source_pipelines_and_match_the_laptop_run(spark, tmp_path):
    import mlflow
    from lakematch import jobs, tracking
    from lakematch.config import load
    from lakematch.pipeline import run
    from lakematch.runtime import Runtime
    bin_dir = Path(sys.executable).parent
    if not (bin_dir / "spark-pipelines").exists():
        pytest.skip("spark-pipelines (pyspark[pipelines]) is not installed")
    _write(tmp_path)
    user = {"profile": "laptop", "storage": {"root": str(tmp_path / "root")},
            "inputs": {"left": {"path": str(tmp_path / "left.csv"), "id": "rid"},
                       "right": {"path": str(tmp_path / "right.csv"), "id": "rid"}},
            "entity": {"name": "person", "fields": FIELDS},
            "quality": {"checks": [{"check": "is_not_null", "column": "given", "side": "right"}]},
            "candidates": {"k": 3}, "matcher": {"estimator": "logistic_regression"},
            "labels": {"source": "truth_sample", "n": 200},
            "evaluation": {"truth": {"path": str(tmp_path / "truth.csv"), "left_id": "l_id", "right_id": "r_id"}}}
    (tmp_path / "lm.yaml").write_text(yaml.safe_dump(user))
    cfg = load(tmp_path / "lm.yaml")

    jobs.task_plan(cfg, Runtime(cfg, spark))                       # -> root/candidate_plan.json
    summary = run(load(tmp_path / "lm.yaml"), rt=Runtime(cfg, spark))
    mlflow.set_tracking_uri(summary["mlflow"]["tracking_uri"])
    scoring = json.loads(Path(mlflow.artifacts.download_artifacts(
        f"{summary['mlflow']['model_uri']}/artifacts/scoring.json", dst_path=str(tmp_path / "dl"))).read_text())
    (tmp_path / "root" / "champion.json").write_text(json.dumps({"version": "laptop", **scoring}))

    (tmp_path / "transformations").mkdir()                        # the spec's globs are relative to it
    (tmp_path / "transformations" / "flows.py").write_text(
        (Path(tracking.__file__).parent / "pipelines" / "flows.py").read_text())
    spec = {"name": "lakematch", "storage": (tmp_path / "pipeline_storage").as_uri(),       # a URI, not a path
            "configuration": {"lakematch.config": str(tmp_path / "lm.yaml")},
            "libraries": [{"glob": {"include": "transformations/**"}}]}
    (tmp_path / "spec.yml").write_text(yaml.safe_dump(spec))
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
           "JAVA_TOOL_OPTIONS": "-Djava.net.preferIPv4Stack=true"}
    done = subprocess.run([str(bin_dir / "spark-pipelines"), "run", "--spec", str(tmp_path / "spec.yml")],
                          cwd=tmp_path, env=env, capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-3000:]

    def pairs(path):
        return {(r.l_id, r.r_id) for r in spark.read.parquet(str(path)).select("l_id", "r_id").collect()}
    piped = pairs(tmp_path / "spark-warehouse" / "lm_links")
    assert piped and piped == pairs(tmp_path / "root" / "links")
    quarantined = spark.read.parquet(str(tmp_path / "spark-warehouse" / "lm_right_quarantine")).count()
    assert quarantined == summary["quarantined"]["right"] == 3
