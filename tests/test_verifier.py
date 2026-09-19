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


@pytest.mark.parametrize("phase", range(3, 10))
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
