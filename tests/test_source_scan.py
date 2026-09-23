"""Source scans include new implementation files without copying generated trees."""
import importlib.util
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("scan_source", ROOT / "tools/scan_source.py")
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


def write(root, name, text="synthetic fixture\n"):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_source_snapshot_excludes_generated_copies_and_includes_new_sources(tmp_path):
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=True)
    write(tmp_path, ".gitignore", "data/\nmlruns/\n.build/\n.venv/\n")
    tracked = "src/lakematch/engine.py"
    write(tmp_path, tracked)
    subprocess.run(["git", "add", tracked], cwd=tmp_path, check=True)
    fresh = {
        "app/src/lakematch_review/backend/store.py", "src/lakematch/mastering/registry.py",
        "app/migrations/mastering/0002_registry.sql", "examples/mastering/pilot/domain.json",
        "requirements-postgres.lock", "genie/build_space.py", "tests/test_new_case.py",
        "runtime/src/lakematch_runtime/connection.py", "runtime/pyproject.toml",
        "runtime/tests/test_settings_credentials.py",
    }
    for name in fresh:
        write(tmp_path, name)
    for prefix in ("data/test-runs/run/replay", "data/test-runs/run/replay-v2",
                   "data/frozen_models", "data/remote_models", "data/serverless_runs", "mlruns",
                   "app/.build", "app/.venv", "runtime/.build", "runtime/.venv",
                   "reports", "experiments", "spec/bench"):
        write(tmp_path, f"{prefix}/src/lakematch/engine.py")
    # Tracked files are normally returned by ls-files even when now ignored.
    subprocess.run(["git", "add", "--force", "app/.build/src/lakematch/engine.py"],
                   cwd=tmp_path, check=True)
    (tmp_path / "src/external.py").symlink_to(tmp_path / tracked)
    assert set(scanner.source_files(tmp_path)) == {".gitignore", tracked, *fresh}


def test_scan_refuses_to_overwrite_existing_evidence(tmp_path):
    output = tmp_path / "previous-scan"
    receipt = write(output, "findings.json", '{"original": true}\n')
    with pytest.raises(SystemExit) as error:
        scanner.main(["--out", str(output)])
    assert error.value.code == 2
    assert receipt.read_text() == '{"original": true}\n'
