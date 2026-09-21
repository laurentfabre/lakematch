"""The regression guard catches a reintroduced append without banning SQLite."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_changes", ROOT / "tools/check_changes.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
RULES = json.loads((ROOT / ".vibe-doctor/forbidden_patterns.json").read_text())["patterns"]


def test_remote_append_regression_fails_but_sqlite_remains_allowed():
    path = "app/src/lakematch_review/backend/store.py"
    safe = 'class SQLiteStore: sql = "INSERT INTO commits VALUES (?)"\nclass DeltaStore: pass\n'
    assert not list(module.violations({path: safe}, RULES))
    unsafe = 'class DeltaStore:\n    sql = "INSERT INTO review_labels VALUES (:id)"\n'
    assert len(list(module.violations({path: unsafe}, RULES))) == 1


def test_guard_is_scoped_and_catches_remote_fixture_append():
    sql = 'query("INSERT INTO review_metadata VALUES (:key, :payload)")'
    assert not list(module.violations({"tests/fixture.py": sql}, RULES))
    assert len(list(module.violations({"app/acceptance/remote.py": sql}, RULES))) == 1
