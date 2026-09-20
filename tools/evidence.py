"""Shared, read-only evidence identity. No git worktree mutation."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


LOCAL_TOOLS = {"accept_zr1.py", "connect_tests.py", "evidence.py", "experiment.py", "offline.sb",
               "offline_run.py", "package_check.py", "prepare_febrl.py", "verify.py",
               "run_methods.py", "report_methods.py", "spark_event_metrics.py"}


def source_files(phase=None):
    paths = [ROOT / n for n in ("pyproject.toml", ".python-version", "requirements-local.lock", "verify_zr.sh")]
    for directory in ("src", "tests", "tools", "examples", "bench"):
        paths += [p for p in (ROOT / directory).rglob("*") if p.is_file() and
                  "__pycache__" not in p.parts and p.suffix in {".py", ".yaml", ".csv", ".sb"} and
                  (phase != "ZR-1" or directory != "tools" or p.name in LOCAL_TOOLS)]
    if phase != "ZR-1":
        paths += [ROOT / "bench" / n for n in ("PROTOCOL.md", "ABLATION_PLAN.md", "METHOD_PLAN.md", "CLASSIFIER_PLAN.md", "CLUSTER_PLAN.md", "requirements-splink.lock")]
    return [p for p in sorted(set(paths)) if p.exists()]


def source_digest(phase=None):
    digest = hashlib.sha256()
    for path in source_files(phase):
        digest.update(str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()
