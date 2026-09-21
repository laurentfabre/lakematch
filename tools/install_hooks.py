"""Install the local check beneath the existing managed Databricks hooks."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
git_dir = Path(subprocess.check_output(["git", "rev-parse", "--git-common-dir"], cwd=ROOT, text=True).strip())
if not git_dir.is_absolute():
    git_dir = ROOT / git_dir
source = ROOT / ".githooks/pre-commit"
target = git_dir / "hooks/pre-commit"
if target.exists() and target.read_bytes() != source.read_bytes():
    raise SystemExit(f"Existing custom hook preserved at {target}; compose it explicitly before installing.")
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(source, target)
target.chmod(0o755)
print(f"Installed {target}; core.hooksPath and managed secret scanning were left in place.")
