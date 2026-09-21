"""Recovery must reproduce the sealed inputs and refuse changed local files."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from restore_frozen_inputs import read_archive, restore


def test_restore_is_exact_and_repeatable(tmp_path):
    files = read_archive()
    restore(tmp_path)
    restore(tmp_path)
    assert {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == files


def test_changed_snapshot_is_never_overwritten(tmp_path):
    (tmp_path / "all").mkdir()
    changed = tmp_path / "all/left.jsonl"
    changed.write_text("changed")
    with pytest.raises(ValueError, match="Refusing to replace"):
        restore(tmp_path)
    assert changed.read_text() == "changed"
    assert not (tmp_path / "manifest.json").exists()
