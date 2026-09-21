"""Local commit checks; never starts Spark, cloud compute or a remote scan."""
import argparse
import ast
import fnmatch
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def violations(contents, rules):
    for name, source in contents.items():
        for rule in rules:
            if fnmatch.fnmatchcase(name, rule["scope_glob"]):
                match = re.search(rule["pattern"], source)
                if match:
                    line = source.count("\n", 0, match.start()) + 1
                    yield f"{name}:{line}: {rule['justification']}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Check working source, including untracked files")
    parser.add_argument("--patterns-only", action="store_true")
    args = parser.parse_args()
    paths = (git("ls-files", "-z", "--cached", "--others", "--exclude-standard") if args.all else
             git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"))
    names = sorted(set(p.decode() for p in paths.split(b"\0") if p))
    contents = {}
    for name in names:
        if name.startswith(("data/", "mlruns/", "experiments/", "reports/", "spec/bench/cache/")):
            continue
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            continue
        raw = path.read_bytes() if args.all else git("show", ":" + name)
        try:
            contents[name] = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
    rules_path = ".vibe-doctor/forbidden_patterns.json"
    rule_source = contents.get(rules_path, (ROOT / rules_path).read_text())
    rules = json.loads(rule_source)["patterns"]
    errors = list(violations(contents, rules))
    if not args.patterns_only:
        for name, source in contents.items():
            if name.endswith(".py"):
                try:
                    ast.parse(source, filename=name)
                except SyntaxError as error:
                    errors.append(f"{name}:{error.lineno}: {error.msg}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Regression guards passed ({len(contents)} source files).", flush=True)
    if args.patterns_only:
        return 0
    if not args.all:
        subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=True)
    checks = []
    if args.all or any(n.startswith(("src/lakematch/mastering/", "tests/test_mastering_",
                                     "examples/mastering/")) for n in contents):
        checks.append((ROOT / ".venv/bin/python", ROOT,
                       ["tests/test_mastering_contracts.py", "tests/test_mastering_policy.py"]))
    if any(n.startswith(("app/src/", "app/tests/", "app/acceptance/")) for n in contents):
        checks.append((ROOT / "app/.venv/bin/python", ROOT / "app", ["tests"]))
    if args.all or any(n in {"src/lakematch/publication.py", "tests/test_publication.py"} for n in contents):
        checks.append((ROOT / ".venv/bin/python", ROOT, ["tests/test_publication.py"]))
    if args.all or any(n.startswith("tools/check_changes") or n in {
            "tests/test_source_hygiene.py", ".vibe-doctor/forbidden_patterns.json"} for n in contents):
        checks.append((ROOT / ".venv/bin/python", ROOT, ["tests/test_source_hygiene.py"]))
    if args.all or any(n.startswith(("deployment/assets/", "tools/restore_frozen_inputs.py")) or
                      n == "tests/test_deployment_recovery.py" for n in contents):
        checks.append((ROOT / ".venv/bin/python", ROOT, ["tests/test_deployment_recovery.py"]))
    for python, cwd, tests in checks:
        if not python.exists():
            raise SystemExit(f"Missing {python}; prepare the documented project environment before committing.")
        subprocess.run([str(python), "-m", "pytest", "-q", *tests], cwd=cwd, check=True, timeout=120)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
