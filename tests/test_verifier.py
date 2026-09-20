import importlib.util
from pathlib import Path
import sys

import pytest


def verifier():
    sys.path.insert(0, str(Path("tools").resolve()))
    spec = importlib.util.spec_from_file_location("lakematch_verify", "tools/verify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("phase", [6, 7, 8, 9])
def test_unimplemented_phases_cannot_pass(phase):
    assert verifier().verify(phase)


def test_source_changes_invalidate_passing_evidence(monkeypatch):
    module = verifier()
    monkeypatch.setattr(module, "source_digest", lambda *args: "unobserved-source-digest")
    errors = module.verify(1)
    assert sum("Missing current-source evidence" in message for message in errors) == 5


def test_phase2_requires_compatible_hashed_experiment_artifacts(monkeypatch):
    module = verifier()
    monkeypatch.setattr(module, "sha256", lambda *args: "changed-content")
    errors = module.verify(2)
    assert sum("Missing compatible-source ablation-" in message for message in errors) == 4


def test_phase5_requires_hashed_local_and_remote_model_evidence(monkeypatch):
    module = verifier()
    monkeypatch.setattr(module, "sha256", lambda *args: "changed-content")
    errors = module.verify(5)
    assert sum("Missing compatible-source tracking-" in message for message in errors) == 4


def test_phase4_requires_matching_comparisons_identities_and_publication(monkeypatch):
    verifier()
    import verify_clusters
    monkeypatch.setattr(verify_clusters, 'sha256', lambda *args: 'changed-content')
    errors = verify_clusters.check()
    assert sum('Missing compatible-source' in message for message in errors) == 4


def test_phase3_rejects_modified_frozen_evidence(monkeypatch):
    verifier()
    import report_final
    import verify_benchmarks
    monkeypatch.setattr(report_final, 'sha256', lambda *args: 'changed-content')
    errors = verify_benchmarks.check()
    assert any('Missing/changed' in message for message in errors)
