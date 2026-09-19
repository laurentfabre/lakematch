#!/usr/bin/env python3
"""Read-only phase verifier. No deployments, training, or evidence generation."""
import json
from pathlib import Path
import re
import sys
import tomllib
import xml.etree.ElementTree as ET

from evidence import ROOT, sha256, source_digest


def verify(phase):
    errors = []
    if phase not in range(1, 10):
        return ["Phase must be an integer from 1 to 9"]
    if phase != 1:
        return [f"ZR-{phase}: implementation and full acceptance evidence are pending; see goal.md"]
    package = tomllib.loads((ROOT / "pyproject.toml").read_text())
    names = {re.split(r"[<>=\[]", d)[0].lower() for d in package["project"]["dependencies"]}
    if names != {"pyspark", "mlflow", "pyyaml"}:
        errors.append("Mandatory dependencies must be exactly pyspark, mlflow, pyyaml")
    if "Apache License" not in (ROOT / "LICENSE").read_text():
        errors.append("Apache-2.0 LICENSE missing")
    for path in (ROOT / "src").rglob("*.py"):
        if path.name != "runtime.py" and re.search(r"sparkContext|_jvm|\.rdd\b|udf\.register|createGlobalTempView|\.(?:cache|persist|checkpoint)\(", path.read_text()):
            errors.append(f"Nonportable API in {path.relative_to(ROOT)}")
    ledger = ROOT / "experiments" / "runs.jsonl"
    records = [json.loads(line) for line in ledger.read_text().splitlines() if line] if ledger.exists() else []
    current = source_digest("ZR-1")
    required = {"tests-classic", "tests-connect", "offline-run", "febrl4-run", "package-build"}
    test_cases = {}
    for kind in sorted(required):
        eligible = [r for r in records if r["phase"] == "ZR-1" and r["kind"] == kind and r["source_digest"] == current]
        if not eligible:
            errors.append(f"Missing current-source evidence: {kind}")
            continue
        run = eligible[-1]
        manifest = json.loads((ROOT / run["manifest"]).read_text())
        if run["status"] != "passed" or manifest["exit_code"] != 0 or manifest["source_digest"] != current:
            errors.append(f"Latest {kind} did not pass")
            continue
        xml_found = False
        metrics = None
        stdout = ""
        private_repo = False
        wheel = False
        for artifact in manifest["artifacts"]:
            path = ROOT / artifact["path"]
            if not path.is_file() or sha256(path) != artifact["sha256"]:
                errors.append(f"Missing or modified evidence artifact: {path.relative_to(ROOT)}")
                continue
            if path.suffix == ".xml" and kind.startswith("tests-"):
                xml_found = True
                tree = ET.parse(path)
                cases = tree.findall(".//testcase")
                test_cases[kind] = {(c.get("classname"), c.get("name")) for c in cases}
                if len(cases) < 29 or tree.findall(".//skipped") or tree.findall(".//failure") or tree.findall(".//error"):
                    errors.append(f"Incomplete or failed pytest evidence: {kind}")
            elif path.name == "metrics.json":
                metrics = json.loads(path.read_text())
            elif path.name == "stdout.txt":
                stdout = path.read_text()
            elif path.name == "repository.json":
                private_repo = json.loads(path.read_text()).get("isPrivate") is True
            elif path.suffix == ".whl":
                wheel = True
        if kind.startswith("tests-") and not xml_found:
            errors.append(f"No pytest XML artifact: {kind}")
        if kind in {"offline-run", "febrl4-run"}:
            if not metrics or metrics.get("links", 0) <= 0 or metrics.get("cleanup") != "succeeded":
                errors.append(f"No completed link-producing run with cleanup: {kind}")
            elif metrics.get("enabled_paid_features"):
                errors.append(f"Paid features enabled in local acceptance run: {kind}")
        if kind == "offline-run" and "Verified OS denies non-loopback network access" not in stdout:
            errors.append("Missing OS network-denial assertion")
        if kind == "package-build" and (not private_repo or not wheel or '"installed_import": "passed"' not in stdout):
            errors.append("Missing wheel, isolated installed-import or private-repository evidence")
    if len(test_cases) == 2 and test_cases["tests-classic"] != test_cases["tests-connect"]:
        errors.append("Classic and Connect did not run the same test cases")
    return errors


if __name__ == "__main__":
    try:
        errors = verify(int(sys.argv[1]))
    except (ValueError, IndexError, KeyError, OSError, json.JSONDecodeError, ET.ParseError) as exc:
        errors = [f"Incomplete evidence: {exc}"]
    print("\n".join(errors) if errors else f"ZR-{sys.argv[1]} verified against the current source")
    sys.exit(bool(errors))
