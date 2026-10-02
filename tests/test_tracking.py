"""ZR-5: a run logs one composite MLflow model; the laptop resolves it by run id (pointer file, no registry); with a
registry the alias moves to the new version and scoring pins that version. The registry test uses MLflow's own
SQLite registry, so the registry code path runs offline; Unity Catalog differs only in the URIs."""
import json

import mlflow
import pandas as pd
import pytest

from conftest import make_cfg
from lakematch import tracking
from lakematch.config import ConfigError, build
from lakematch.pipeline import run
from lakematch.runtime import Runtime
from test_pipeline import _write

FIELDS = {"given": {"type": "person_name"}, "surname": {"type": "person_name"}, "street": {"type": "address"},
          "postcode": {"type": "code"}, "dob": {"type": "date"}}


def _cfg(tmp_path, **mlflow_cfg):
    return make_cfg(tmp_path,
                    inputs={"left": {"path": "left.csv", "id": "rid"}, "right": {"path": "right.csv", "id": "rid"}},
                    entity={"name": "person", "fields": FIELDS}, candidates={"k": 3},
                    matcher={"estimator": "logistic_regression"}, labels={"source": "truth_sample", "n": 200},
                    evaluation={"truth": {"path": "truth.csv", "left_id": "l_id", "right_id": "r_id"}},
                    mlflow=mlflow_cfg)


def test_run_logs_one_composite_model_resolved_by_run_id(spark, tmp_path):
    _write(tmp_path)
    cfg = _cfg(tmp_path)
    summary = run(cfg, rt=Runtime(cfg, spark))
    ml = summary["mlflow"]
    assert ml["accepted"] and ml["reload_parity"]["max_abs_diff_p"] == 0.0
    assert ml["tracking_uri"] == f"sqlite:///{tmp_path / 'mlflow.db'}"        # relative URI -> the config's directory
    pointer = json.loads((tmp_path / "models" / "current.json").read_text())
    assert pointer["run_id"] == ml["run_id"] and pointer["label_set_sha256"] == ml["label_set"]["sha256"]
    # the custom pairwise metrics are the run's own evaluation
    assert ml["metrics"]["pairwise_f1"] == pytest.approx(summary["evaluation"]["all"]["f1"], abs=1e-4)
    assert ml["metrics"]["candidate_recall"] == pytest.approx(summary["evaluation"]["candidate_recall"], abs=1e-4)

    model, uri = tracking.load_current(cfg)
    assert uri == f"runs:/{ml['run_id']}/model"
    sig = model.metadata.signature
    assert sig.inputs.input_names() == ["l_id", "r_id", *summary["features"]]
    assert sig.outputs.input_names() == ["l_id", "r_id", "p", "above_threshold"]

    client = mlflow.MlflowClient()
    r = client.get_run(ml["run_id"])
    contexts = sorted(t.value for i in r.inputs.dataset_inputs for t in i.tags if t.key == "mlflow.data.context")
    assert contexts == ["input_left", "input_right", "training", "validation"]
    assert r.data.tags["lakematch.label_set_sha256"] == ml["label_set"]["sha256"]
    assert {"pairwise_precision", "pairwise_recall", "pairwise_f1", "candidate_recall"} <= set(r.data.metrics)
    art = mlflow.artifacts.download_artifacts(f"runs:/{ml['run_id']}/model/artifacts", dst_path=str(tmp_path / "dl"))
    names = {p.name for p in __import__("pathlib").Path(art).iterdir()}
    assert names == {"spark_pipeline", "config.json", "label_set.json", "thresholds.json"}

    # the bundle scores a pair the way the run did: above_threshold follows the logged threshold
    row = {c: 0.0 for c in summary["features"]} | {"l_id": "x", "r_id": "y"}
    out = model.predict(pd.DataFrame([row]))
    assert list(out.columns) == ["l_id", "r_id", "p", "above_threshold"]
    assert bool(out.at[0, "above_threshold"]) == (out.at[0, "p"] >= summary["decision"]["threshold"])

    # same labels -> same digest; the pointer moves to the newer accepted run
    again = run(cfg, rt=Runtime(cfg, spark))["mlflow"]
    assert again["label_set"]["sha256"] == ml["label_set"]["sha256"] and again["run_id"] != ml["run_id"]
    assert json.loads((tmp_path / "models" / "current.json").read_text())["run_id"] == again["run_id"]


def test_rejected_run_leaves_the_pointer_and_root_redirects_the_store(spark, tmp_path):
    _write(tmp_path)
    cfg = _cfg(tmp_path, accept_min_f1=1.0)       # unreachable: nothing is accepted
    scratch = tmp_path / "scratch"
    ml = run(cfg, root=scratch, rt=Runtime(cfg, spark))["mlflow"]
    if ml["metrics"]["pairwise_f1"] < 1.0:
        assert not ml["accepted"] and "rejected_because" in ml
        assert not (scratch / "models" / "current.json").exists()
    assert ml["tracking_uri"] == f"sqlite:///{scratch / 'mlflow.db'}"
    assert not (tmp_path / "mlflow.db").exists() and not (tmp_path / "models").exists()


def test_registry_moves_the_alias_and_scoring_pins_the_version(spark, tmp_path):
    _write(tmp_path)
    db = f"sqlite:///{tmp_path / 'registry.db'}"
    cfg = _cfg(tmp_path, tracking_uri=db, registry=True, registry_uri=db, alias="champion")
    first = run(cfg, rt=Runtime(cfg, spark))["mlflow"]
    assert first["registered"] == {"name": "lakematch_person", "version": "1", "alias": "champion"}
    second = run(cfg, rt=Runtime(cfg, spark))["mlflow"]
    assert second["registered"]["version"] == "2"
    assert not (tmp_path / "models").exists()                  # a registry run never writes the laptop pointer
    model, uri = tracking.load_current(cfg)
    assert uri == "models:/lakematch_person/2" and model.metadata.signature is not None


def test_registered_name_uses_the_catalog_only_for_unity_catalog():
    cfg = build({"entity": {"name": "person"}, "storage": {"catalog": "workspace.lakematch"}})
    assert tracking.registered_name(cfg) == "lakematch_person"
    uc = build({"entity": {"name": "person"}, "storage": {"catalog": "workspace.lakematch"},
                "mlflow": {"tracking_uri": "databricks", "registry": True, "registry_uri": "databricks-uc",
                           "alias": "champion"}})
    assert tracking.registered_name(uc) == "workspace.lakematch.lakematch_person"


@pytest.mark.parametrize("bad", [{"registry": True}, {"pointer": None}, {"accept_min_f1": 2},
                                 {"eval_max_pairs": 0}, {"tracking_uri": ""}])
def test_mlflow_config_is_validated(bad):
    with pytest.raises(ConfigError):
        build({"mlflow": bad})
