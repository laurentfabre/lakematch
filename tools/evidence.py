"""Shared, read-only evidence identity. No git worktree mutation."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


LOCAL_TOOLS = {"accept_zr1.py", "connect_tests.py", "evidence.py", "experiment.py", "offline.sb",
               "offline_run.py", "package_check.py", "prepare_febrl.py", "verify.py"}


def source_files(phase=None):
    paths = [ROOT / n for n in ("pyproject.toml", ".python-version", "requirements-local.lock", "verify_zr.sh")]
    for directory in ("src", "tests", "tools", "examples"):
        paths += [p for p in (ROOT / directory).rglob("*") if p.is_file() and
                  "__pycache__" not in p.parts and p.suffix in {".py", ".yaml", ".csv", ".sb"} and
                  (phase != "ZR-1" or directory != "tools" or p.name in LOCAL_TOOLS)]
    return [p for p in sorted(set(paths)) if p.exists()]


def source_digest(phase=None):
    digest = hashlib.sha256()
    for path in source_files(phase):
        digest.update(str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()
