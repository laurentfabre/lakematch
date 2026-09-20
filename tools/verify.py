#!/usr/bin/env python3
"""Read-only phase verifier. No deployments, training, or evidence generation."""
import json
from pathlib import Path
import re
import sys
import tomllib
import xml.etree.ElementTree as ET

from evidence import ROOT, sha256, source_digest


def verify_tracking():
    errors = verify(1)
    ledger = ROOT / "experiments" / "runs.jsonl"
    records = [json.loads(line) for line in ledger.read_text().splitlines() if line]
    package = {"src/lakematch/" + name + ".py" for name in (
        "__init__", "composite_model", "tracking", "config", "runtime", "entity", "features", "feature_stats",
        "similarity", "embeddings", "matcher", "decision")}
    shared = package | {"pyproject.toml", "tools/tracking_canary.py"}
    results = {}
    for kind, specific in {
        "tracking-train": {"tools/offline.sb", "tools/offline_run.py"},
        "tracking-reload": {"tools/offline.sb", "tools/offline_run.py"},
        "tracking-cli": {"src/lakematch/engine.py", "src/lakematch/candidates.py", "src/lakematch/blocking.py", "src/lakematch/cli.py",
                         "src/lakematch/quality/native.py", "src/lakematch/quality/__init__.py", "tools/tracking_cli_check.py"},
        "tracking-serverless": {"tools/run_tracking_remote.py", "tools/tracking_notebook.py"},
    }.items():
        dependencies = shared | specific
        eligible = []
        for event in records:
            if event["phase"] != "ZR-5" or event["kind"] != kind:
                continue
            manifest = json.loads((ROOT / event["manifest"]).read_text())
            recorded = manifest["source_files"]
            if all(p in recorded and (ROOT / p).is_file() and sha256(ROOT / p) == recorded[p] for p in dependencies):
                eligible.append((event, manifest))
        if not eligible:
            errors.append(f"Missing compatible-source {kind} evidence")
            continue
        event, manifest = eligible[-1]
        if event["status"] != "passed" or manifest["exit_code"] != 0 or "no live members" not in manifest["cleanup"]:
            errors.append(f"Latest {kind} did not complete with cleanup")
            continue
        stdout, report = "", None
        for artifact in manifest["artifacts"]:
            path = ROOT / artifact["path"]
            if not path.is_file() or sha256(path) != artifact["sha256"]:
                errors.append(f"Missing or changed tracking evidence: {path}")
                continue
            if path.name == "stdout.txt":
                stdout = path.read_text()
            if path.name in {"train.json", "report.json", "tracking-remote.json"}:
                report = json.loads(path.read_text())
        if not report:
            errors.append(f"Missing structured {kind} report")
            continue
        if kind != "tracking-serverless" and "Verified OS denies non-loopback network access" not in stdout:
            errors.append(f"Missing offline assertion: {kind}")
        if kind == "tracking-cli":
            if (report.get("status") != "completed" or report.get("cleanup") != "succeeded" or
                    report.get("fresh_cli_prediction_equivalence") is not True or not report["train"]["model"]["accepted"]):
                errors.append("CLI did not accept then reload the same evaluated model")
            continue
        if kind == "tracking-serverless":
            if (report.get("profile") != "fevm-gdpr2" or report.get("status") != "completed" or
                    report.get("cleanup") != "terminal serverless run; no persistent compute" or
                    report.get("run", {}).get("state", {}).get("result_state") != "SUCCESS"):
                errors.append("Remote tracking did not complete on the selected workspace")
            tasks = report.get("run", {}).get("tasks", [])
            if len(tasks) != 2 or len({t.get("run_id") for t in tasks}) != 2 or any(
                    t.get("state", {}).get("result_state") != "SUCCESS" for t in tasks):
                errors.append("Missing separate successful train/reload task evidence")
            exported = report.get("exported_artifacts", {})
            if not exported or any(not (ROOT / p).is_file() or sha256(ROOT / p) != h for p, h in exported.items()):
                errors.append("Remote model/evidence export is missing or changed")
            report = report.get("result", {})
            if (not report.get("registry") or report.get("alias") != "champion" or
                    report.get("resolved_model_uri") != f"models:/{report.get('name')}/{report.get('version')}"):
                errors.append("Champion alias did not resolve to the immutable UC version")
        if (report.get("native_pyfunc_equivalence") is not True or
                report.get("training_evaluation_records_disjoint") is not True or
                report.get("evaluation", {}).get("pairwise_f1") != 1. or not report.get("label_set_sha256") or
                not 0 < report.get("artifact_bytes", 0) < 100 * 1024 * 1024):
            errors.append(f"Incomplete composite model/evaluation/size evidence: {kind}")
        if kind != "tracking-train" and (report.get("fresh_session_equivalence") is not True or
                report.get("maximum_probability_difference", 1.) >= 1e-12):
            errors.append(f"Fresh-session predictions differ: {kind}")
        if kind == "tracking-reload" and (report.get("local_registered_models") != 0 or not report.get("accepted_pointer")):
            errors.append("Local model did not use accepted-run tracking without a registry")
        results[kind] = report
    if "tracking-train" in results and "tracking-reload" in results and (
            results["tracking-train"]["run_id"] != results["tracking-reload"]["run_id"]):
        errors.append("Fresh-session evidence reloads a different local MLflow run")
    if not (ROOT / "bench/MODELS.md").is_file():
        errors.append("Missing composite model report")
    return errors


def verify_features():
    errors = verify(1)
    ledger = ROOT / "experiments" / "runs.jsonl"
    records = [json.loads(line) for line in ledger.read_text().splitlines() if line]
    expected = {"native_all", "without_field_families", "without_idf", "without_grams", "without_monge", "plus_jaro_winkler", "plus_affine"}
    for corpus in ("febrl4", "bpid", "abt_buy", "affiliations"):
        kind = "ablation-" + corpus
        found = []
        for event in records:
            if event["phase"] != "ZR-2" or event["kind"] != kind:
                continue
            manifest = json.loads((ROOT / event["manifest"]).read_text())
            # Reports/verifier-only edits do not change the measured engine. Compare
            # every actual execution dependency recorded by the experiment runner.
            dependencies = {p: h for p, h in manifest["source_files"].items() if p.startswith("src/") or p in {
                "tools/run_ablation.py", "tools/offline_run.py", "tools/offline.sb", "pyproject.toml", "bench/ABLATION_PLAN.md"}}
            if dependencies and all((ROOT / p).is_file() and sha256(ROOT / p) == h for p, h in dependencies.items()):
                found.append((event, manifest))
        if not found:
            errors.append(f"Missing compatible-source {kind} evidence")
            continue
        event, manifest = found[-1]
        if event["status"] != "passed" or manifest["exit_code"] != 0:
            errors.append(f"Latest compatible {kind} did not pass")
            continue
        report, plans, predictions, stdout = None, {}, set(), ""
        for artifact in manifest["artifacts"]:
            path = ROOT / artifact["path"]
            if not path.is_file() or sha256(path) != artifact["sha256"]:
                errors.append(f"Missing or modified {kind} artifact: {path}")
                continue
            if path.name == "report.json":
                report = json.loads(path.read_text())
            elif path.name.endswith(".plan.txt"):
                plans[path.name[:-9]] = path.read_text()
            elif path.name.endswith(".predictions.json"):
                predictions.add(path.name[:-17])
            elif path.name == "stdout.txt":
                stdout = path.read_text()
        required = expected | ({"embedding_on"} if corpus in {"abt_buy", "affiliations"} else set())
        if (not report or report.get("status") != "completed" or report.get("cleanup") != "succeeded" or
                report.get("confirmation_scored") is not False):
            errors.append(f"Incomplete or confirmation-contaminated {kind} report")
            continue
        required |= {f"without_{spec['type']}_fields" for spec in report["config"]["entity"]["fields"].values()}
        rows = {r["variant"]: r for r in report["rows"]}
        if not required <= rows.keys() or not required <= predictions or not required <= plans.keys():
            errors.append(f"Missing variant report, predictions or explain plan for {kind}")
        for name in required & rows.keys():
            row = rows[name]
            if row.get("resamples") != 2000 or row.get("seed") != 2026091902 or not row.get("f1_95ci") or not row.get("paired_delta_95ci"):
                errors.append(f"Missing paired bootstrap evidence: {kind}/{name}")
            if name not in {"plus_jaro_winkler", "plus_affine"} and (not row.get("native_plan") or any(
                    token in plans.get(name, "") for token in ("PythonUDF", "BatchEvalPython", "ArrowEvalPython"))):
                errors.append(f"Default feature plan has a Python UDF: {kind}/{name}")
        if "embedding_on" in required and "embedding_on" in rows:
            observations = rows["embedding_on"].get("embedding_preparation", {})
            if set(observations) != {"left", "right"} or any(o.get("status") != "prepared" or not o.get("records") or
                    not o.get("seconds_per_100000_records_extrapolated") for o in observations.values()):
                errors.append(f"Missing actual local embedding execution/cost: {kind}")
        if "Verified OS denies non-loopback network access" not in stdout:
            errors.append(f"Missing offline assertion: {kind}")
        if corpus == "febrl4" and not report.get("training_record_partition_assertion"):
            errors.append("FEBRL supervised training partition was not asserted")
    if not (ROOT / "bench" / "ABLATION.md").is_file():
        errors.append("Missing bench/ABLATION.md")
    return errors


def verify(phase):
    errors = []
    if phase not in range(1, 10):
        return ["Phase must be an integer from 1 to 9"]
    if phase == 2:
        return verify_features()
    if phase == 3:
        from verify_benchmarks import check
        return verify(1) + check()
    if phase == 5:
        return verify_tracking()
    if phase == 4:
        from verify_clusters import check
        return verify(1) + check()
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
