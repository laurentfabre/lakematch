"""Corruption regressions for SIM-3; these tests never create a Spark session."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("simbeat_audit", ROOT / "bench/simbeat_audit.py")
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)
WORK = ROOT / "data/runs/simbeat"
GATE = ROOT / "scripts/verify_simbeat.sh"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def reseal(result):
    """Keep checksums consistent so tests reach the semantic binding checks."""
    sha = digest(result["selection_lock"])
    result["meta"]["selection_sha256"] = sha
    for confirmation in result["confirmation"].values():
        confirmation["selection_sha256"] = sha


@pytest.fixture(scope="module")
def recorded():
    return json.loads((ROOT / "bench/results/simbeat.json").read_text())


@pytest.fixture
def result(recorded):
    return copy.deepcopy(recorded)


def test_recorded_json_replays_without_reading_current_catalogue(recorded, monkeypatch):
    original = Path.open

    def no_catalogue(path, *args, **kwargs):
        if path.name == "sota_candidates.json":
            raise AssertionError("audit must use the manifest's recorded shortlist")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", no_catalogue)
    assert audit_module.audit(recorded) is True


def test_current_artifacts_pass_authoritative_audit(recorded):
    if not WORK.is_dir():
        pytest.skip("local benchmark artifacts are not available")
    assert audit_module.audit(recorded, work_dir=WORK) is True


@pytest.mark.parametrize("field,value", [
    ("variant", "jaro_winkler"),
    ("threshold", 0.999),
    ("model_sha256", "0" * 64),
    ("columns", ["jw_name"]),
])
def test_chosen_valid_row_must_match_locked_model(result, field, value):
    # Update both copies: failure must not rely only on alias inequality.
    for variant in ("chosen", result["chosen_variant"]):
        result["valid"][variant]["abt_buy"][field] = value
    with pytest.raises(audit_module.AuditError):
        audit_module.audit(result)


@pytest.mark.parametrize("field,value", [
    ("chosen_variant", "jaro_winkler"),
    ("selected_on", "test"),
    ("forward_selection", []),
    ("variants", ["levenshtein", "jaro_winkler", "both"]),
])
def test_rehashed_fabricated_selection_lock_is_rejected(result, field, value):
    result["selection_lock"][field] = value
    reseal(result)
    with pytest.raises(audit_module.AuditError):
        audit_module.audit(result)


@pytest.mark.parametrize("target", ["result", "lock", "both"])
def test_selection_trace_is_replayed_not_trusted(result, target):
    if target in ("result", "both"):
        result["forward_selection"][0]["gain"] += 0.1
    if target in ("lock", "both"):
        result["selection_lock"]["forward_selection"][0]["gain"] += 0.1
    reseal(result)
    with pytest.raises(audit_module.AuditError):
        audit_module.audit(result)


@pytest.mark.parametrize("section", ["confirmation", "prepared", "models", "valid"])
@pytest.mark.parametrize("change", ["missing", "extra"])
def test_exact_corpus_coverage_is_required(result, section, change):
    mapping = (result["selection_lock"]["models"] if section == "models" else
               result["valid"]["both"] if section == "valid" else result[section])
    if change == "missing":
        del mapping["abt_buy"]
    else:
        mapping["fabricated_corpus"] = copy.deepcopy(mapping["abt_buy"])
    reseal(result)
    with pytest.raises(audit_module.AuditError):
        audit_module.audit(result)


def test_coordinated_jw_model_substitution_cannot_turn_verdict_into_beaten(result):
    # The old audit accepted this exploit: keep VALID selection, substitute the
    # JW model and TEST evidence, then consistently recompute every checksum.
    for corpus, per in result["confirmation"].items():
        lock = result["selection_lock"]["models"][corpus]
        lock["chosen"] = copy.deepcopy(lock["jaro_winkler"])
        per["chosen"] = copy.deepcopy(per["jaro_winkler"])
    reseal(result)
    result["test"]["chosen"] = copy.deepcopy(result["test"]["jaro_winkler"])
    result["test"]["delta_mean_f1"] = 0.0
    result["test"]["delta_ci95"] = [0.0, 0.0]
    result["verdict_checks"]["test_mean_not_below_jw"] = True
    assert all(result["verdict_checks"].values())
    result["verdict"] = "beaten"
    with pytest.raises(audit_module.AuditError):
        audit_module.audit(result)


@pytest.mark.parametrize("field,value", [
    ("udf_free", False),
    ("columns", ["jw_name"]),
    ("sha256", "not-a-sha256"),
])
def test_test_builtin_proof_is_validated(result, field, value):
    result["confirmation"]["abt_buy"]["plan"]["builtins"][field] = value
    with pytest.raises(audit_module.AuditError):
        audit_module.audit(result)


def test_test_predictions_hash_is_required(result):
    del result["confirmation"]["abt_buy"]["predictions_sha256"]
    with pytest.raises(audit_module.AuditError):
        audit_module.audit(result)


@pytest.fixture
def prediction_fixture(tmp_path):
    expected = {
        "selection_sha256": "1" * 64,
        "manifest_sha256": "2" * 64,
        "models": {
            "chosen": {"model_sha256": "3" * 64, "threshold": 0.5, "columns": ["lev_name"]},
            "jaro_winkler": {"model_sha256": "4" * 64, "threshold": 0.6, "columns": ["jw_name"]},
        },
        "inputs_sha256": {"pairs": "5" * 64, "left": "6" * 64, "right": "7" * 64},
    }
    rows = [{"l_id": "a", "r_id": "b", "label": 1.0, "p_chosen": 0.8, "p_jaro_winkler": 0.7}]
    plan = {
        "builtins": {"udf_free": True, "sha256": "8" * 64, "columns": ["lev_name"]},
        "jaro_winkler": {"udf_free": False, "sha256": "9" * 64, "columns": ["jw_name"]},
    }
    path = tmp_path / "test_predictions.json"
    payload = {"schema_version": 1, "provenance": expected, "plan": plan, "rows": rows}
    save(path, payload)
    return path, expected, payload


def test_prediction_envelope_can_resume_without_completed_confirmation(prediction_fixture):
    path, expected, payload = prediction_fixture
    assert audit_module.load_predictions(path, expected) == (payload["rows"], payload["plan"])


@pytest.mark.parametrize("binding", ["selection", "manifest", "model", "threshold", "columns", "inputs"])
def test_prediction_envelope_rejects_stale_provenance(prediction_fixture, binding):
    path, expected, payload = prediction_fixture
    stale = copy.deepcopy(payload)
    provenance = stale["provenance"]
    if binding in ("selection", "manifest"):
        provenance[binding + "_sha256"] = "f" * 64
    elif binding == "inputs":
        provenance["inputs_sha256"]["pairs"] = "f" * 64
    else:
        key = "model_sha256" if binding == "model" else binding
        provenance["models"]["chosen"][key] = {"model": "f" * 64, "threshold": 0.9, "columns": ["jw_name"]}[binding]
    save(path, stale)
    with pytest.raises(audit_module.AuditError):
        audit_module.load_predictions(path, expected)


def test_unknown_prediction_envelope_version_is_rejected(prediction_fixture):
    path, expected, payload = prediction_fixture
    payload["schema_version"] = 2
    save(path, payload)
    with pytest.raises(audit_module.AuditError):
        audit_module.load_predictions(path, expected)


def legacy_confirmation(path, expected, payload):
    return {
        "selection_sha256": expected["selection_sha256"],
        "predictions_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "plan": payload["plan"],
        **{label: {k: model[k] for k in ("model_sha256", "threshold")}
           for label, model in expected["models"].items()},
    }


def test_legacy_orphan_predictions_are_rejected(prediction_fixture):
    path, expected, payload = prediction_fixture
    save(path, payload["rows"])
    with pytest.raises(audit_module.AuditError):
        audit_module.load_predictions(path, expected)


def test_completed_legacy_predictions_remain_readable(prediction_fixture):
    path, expected, payload = prediction_fixture
    save(path, payload["rows"])
    confirmation = legacy_confirmation(path, expected, payload)
    assert audit_module.load_predictions(path, expected, confirmation) == (payload["rows"], payload["plan"])


@pytest.mark.parametrize("binding", ["selection", "hash", "model", "threshold"])
def test_legacy_predictions_require_matching_completed_confirmation(prediction_fixture, binding):
    path, expected, payload = prediction_fixture
    save(path, payload["rows"])
    confirmation = legacy_confirmation(path, expected, payload)
    if binding == "selection":
        confirmation["selection_sha256"] = "f" * 64
    elif binding == "hash":
        confirmation["predictions_sha256"] = "f" * 64
    elif binding == "model":
        confirmation["chosen"]["model_sha256"] = "f" * 64
    else:
        confirmation["chosen"]["threshold"] = 0.9
    with pytest.raises(audit_module.AuditError):
        audit_module.load_predictions(path, expected, confirmation)


@pytest.mark.parametrize("artifact", ["test_builtins.plan.txt", "test_predictions.json"])
def test_modified_test_artifact_is_rejected(recorded, tmp_path, artifact):
    if not WORK.is_dir():
        pytest.skip("local benchmark artifacts are not available")
    # An overlay redirects reads without changing any preserved evidence.
    overlay = tmp_path / "work"
    overlay.mkdir()
    for child in WORK.iterdir():
        if child.name != "abt_buy":
            (overlay / child.name).symlink_to(child, target_is_directory=child.is_dir())
    corpus = overlay / "abt_buy"
    corpus.mkdir()
    for child in (WORK / "abt_buy").iterdir():
        target = corpus / child.name
        if child.name == artifact:
            target.write_bytes(child.read_bytes() + b"\n")
        else:
            target.symlink_to(child, target_is_directory=child.is_dir())
    with pytest.raises(audit_module.AuditError):
        audit_module.audit(recorded, work_dir=overlay)


@pytest.fixture(scope="module")
def phase3_gate(recorded, tmp_path_factory):
    if not GATE.is_file() or not WORK.is_dir():
        pytest.skip("Repository phase gate and local benchmark artifacts are required")
    fixture = tmp_path_factory.mktemp("phase3_gate") / "repo"
    for directory in ("bench/results", "spec/research"):
        (fixture / directory).mkdir(parents=True)
    for source in (ROOT / "bench").glob("*.py"):
        shutil.copy2(source, fixture / "bench" / source.name)
    shutil.copy2(ROOT / "bench/SIMBEAT.md", fixture / "bench/SIMBEAT.md")
    shutil.copy2(ROOT / "spec/research/sota_candidates.json", fixture / "spec/research/sota_candidates.json")
    # Preserve pyvenv.cfg so subprocesses resolve the real environment's packages.
    (fixture / ".venv").symlink_to(ROOT / ".venv", target_is_directory=True)
    (fixture / "data").symlink_to(ROOT / "data", target_is_directory=True)
    output = fixture / "bench/results/simbeat.json"
    save(output, recorded)
    env = {**os.environ, "LAKEMATCH_REPO": str(fixture), "PYTHONDONTWRITEBYTECODE": "1"}

    def gate():
        return subprocess.run(["bash", str(GATE), "3"], env=env, capture_output=True, text=True, timeout=180)

    baseline = gate()
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    return output, gate


@pytest.mark.parametrize("corruption", [
    "selected_on", "fabricated_trace_empty_provenance", "missing_lock",
    "missing_confirmation", "wrong_chosen_model",
])
def test_phase3_gate_runs_authoritative_audit(recorded, phase3_gate, corruption):
    output, gate = phase3_gate
    corrupted = copy.deepcopy(recorded)
    if corruption == "selected_on":
        corrupted["selection_lock"]["selected_on"] = "test"
        reseal(corrupted)
    elif corruption == "fabricated_trace_empty_provenance":
        corrupted["forward_selection"] = [{"fabricated": True}]
        corrupted["meta"] = {}
        corrupted["selection_lock"] = {}
        corrupted["confirmation"] = {}
    elif corruption == "missing_lock":
        del corrupted["selection_lock"]
    elif corruption == "missing_confirmation":
        del corrupted["confirmation"]
    else:
        corrupted["selection_lock"]["models"]["abt_buy"]["chosen"]["model_sha256"] = "f" * 64
        corrupted["confirmation"]["abt_buy"]["chosen"]["model_sha256"] = "f" * 64
        corrupted["test"]["chosen"]["corpora"]["abt_buy"]["model_sha256"] = "f" * 64
        reseal(corrupted)
    save(output, corrupted)
    rejected = gate()
    assert rejected.returncode != 0, rejected.stdout + rejected.stderr
    assert "NOT DONE" in rejected.stdout
