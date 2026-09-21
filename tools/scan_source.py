"""Run vibe-doctor offline against a Git-aware snapshot of source files only."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = ("src/", "app/", "tests/", "tools/", "resources/", "deployment/", "integration/",
            ".github/", ".githooks/", ".vibe-doctor/", "genie/")
TOP_LEVEL = {"README.md", "goal.md", "pyproject.toml", "databricks.yml", ".gitignore", ".pre-commit-config.yaml"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="reports/source-scan")
    args = parser.parse_args()
    output = (ROOT / args.out).resolve()
    output.mkdir(parents=True, exist_ok=True)
    raw = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT)
    files = sorted({p.decode() for p in raw.split(b"\0") if p})
    selected = [p for p in files if (p in TOP_LEVEL or p.startswith(PREFIXES))
                and (ROOT / p).is_file() and not (ROOT / p).is_symlink()]
    with tempfile.TemporaryDirectory(prefix="lakematch-source-scan-") as directory:
        snapshot = Path(directory)
        # A real disposable Git repository prevents false 'no version control'
        # findings caused solely by copying files out of their original repo.
        subprocess.run(["git", "init", "--quiet", str(snapshot)], check=True)
        for name in selected:
            target = snapshot / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        command = ["vibe-doctor", "scan", str(snapshot), "--out", str(output), "--no-bundle-validate"]
        result = subprocess.run(command, cwd=ROOT, timeout=120)
        markdown = output / "findings.md"
        if markdown.exists():
            markdown.write_text(markdown.read_text().rstrip() + "\n")
        (output / "scope.json").write_text(json.dumps({
            "mode": "offline source snapshot", "source_root": str(ROOT), "files": selected,
            "files_copied": len(selected), "scanner_exit_code": result.returncode,
            "source_sha256": {name: hashlib.sha256((snapshot / name).read_bytes()).hexdigest() for name in selected},
            "excludes": ["Git-ignored files", "data/", "mlruns/", "experiments/", "reports/", "historical spec/bench/"],
            "original_findings_preserved": "reports/findings.json",
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "snapshot_git_metadata": "empty disposable repository; includes current working-tree edits",
        }, indent=2) + "\n")
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
