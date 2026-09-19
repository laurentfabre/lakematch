import importlib.util
from pathlib import Path
import signal
import sys
from types import SimpleNamespace

import pytest


def runner():
    sys.path.insert(0, str(Path("tools").resolve()))
    spec = importlib.util.spec_from_file_location("lakematch_experiment", "tools/experiment.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cleanup_inventory_ignores_zombies_and_other_groups(monkeypatch):
    module = runner()
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=" 10 20 Z\n 11 20 S\n 12 21 R\n"))
    assert module.live_group_members(20) == [11]
    assert module.live_group_members(99) == []


def test_signal_permission_denial_requires_independent_empty_inventory(monkeypatch):
    module = runner()
    def denied(*args):
        raise PermissionError("signal denied")
    monkeypatch.setattr(module.os, "killpg", denied)
    monkeypatch.setattr(module, "live_group_members", lambda pgid: [42])
    with pytest.raises(PermissionError):
        module.signal_owned_group(42, signal.SIGTERM)
    monkeypatch.setattr(module, "live_group_members", lambda pgid: [])
    module.signal_owned_group(42, signal.SIGTERM)
