"""Bounded acceptance of a freshly packaged synthetic APX app; no remote work."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import tempfile
import time
import traceback
from xml.etree import ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_inputs(config):
    for name, expected in config["files"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Pinned UI acceptance input changed: {name}")
    freeze = json.loads((ROOT / "spec/lakefusion/frozen/phase-a-v0.1.json").read_text())["files"]
    for name, expected in freeze.items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Frozen Phase A file changed: {name}")
    return len(freeze)


def run(command, *, timeout, cwd=ROOT, env=None):
    print(json.dumps({"command": [str(c) for c in command], "timeout_seconds": timeout}), flush=True)
    subprocess.run([str(c) for c in command], cwd=cwd, env=env, check=True, timeout=timeout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--preview", type=Path, required=True)
    args = parser.parse_args()
    report_path, junit, preview = (p.resolve() for p in (args.report, args.junit, args.preview))
    if any(p.exists() for p in (report_path, junit, preview)):
        raise SystemExit("Acceptance outputs must be fresh; preserve previous results")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    config = json.loads(args.config.read_text())
    start = time.perf_counter()
    report = {"kind": "fresh_packaged_synthetic_ui_acceptance", "phase": "LF-B", "slot": 9,
              "status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "config_sha256": sha(args.config), "source_files": config["files"],
              "remote_operations": False, "pilot_corpus_access": False,
              "confirmation_materialized": False, "model_fitting": False,
              "quality_qualified": False, "cleanup": "not started"}
    extracted_path = None
    try:
        runs = [json.loads(line) for line in (ROOT / "experiments/runs.jsonl").read_text().splitlines() if line.strip()]
        prior = sum(r["phase"] == "LF-B" for r in runs)
        if prior != config["expected_prior_lf_b_runs"]:
            raise ValueError("LF-B run count differs from the predeclared slot")
        report["frozen_files_verified"] = verify_inputs(config)
        report["versions"] = {"root_python": platform.python_version(), "platform": platform.platform(),
            "app_python": subprocess.check_output([ROOT / "app/.venv/bin/python", "--version"], text=True, timeout=10).strip(),
            "apx": subprocess.check_output(["apx", "--version"], text=True, timeout=10).strip(),
            "node": subprocess.check_output(["node", "--version"], text=True, timeout=10).strip()}
        module = os.environ.get("LAKEMATCH_PLAYWRIGHT_MODULE")
        if module:
            report["versions"]["playwright"] = json.loads((Path(module) / "package.json").read_text())["version"]
        run([sys.executable, ROOT / "tools/build_golden_demo.py", "--check"], timeout=30)
        run([ROOT / "app/.venv/bin/python", "build_deploy.py"], cwd=ROOT / "app", timeout=420)
        run(["node", "node_modules/typescript/bin/tsc", "--noEmit"], cwd=ROOT / "app", timeout=45)
        run([ROOT / "app/.venv/bin/ty", "check"], cwd=ROOT / "app", timeout=45)
        verify_inputs(config)
        build = [p for p in (ROOT / "app/.build").rglob("*") if p.is_file()]
        wheels = [p for p in build if p.suffix == ".whl"]
        if len(wheels) != 1 or any(p.stat().st_size >= 10 * 1024 * 1024 for p in build):
            raise ValueError("Expected one fresh wheel and deployment files below 10 MiB")
        report["build"] = {str(p.relative_to(ROOT)): {"sha256": sha(p), "bytes": p.stat().st_size} for p in build}
        wheel = wheels[0]
        with tempfile.TemporaryDirectory(prefix="lakematch-ui-acceptance-") as directory:
            package = Path(directory)
            extracted_path = package
            report["cleanup"] = "owned extracted wheel active"
            with zipfile.ZipFile(wheel) as archive:
                for name in archive.namelist():
                    if not (package / name).resolve().is_relative_to(package):
                        raise ValueError("Wheel member escapes the owned extraction directory")
                archive.extractall(package)
            demo_path = package / "lakematch_review/demo/company_lineage.json"
            if sha(demo_path) != config["demo_file_sha256"]:
                raise ValueError("Wheel demo differs from the frozen acceptance input")
            demo = json.loads(demo_path.read_text())
            if demo["bundle_sha256"] != config["demo_bundle_sha256"] or [p["snapshot_sha256"] for p in demo["publications"]] != config["publication_hashes"]:
                raise ValueError("Wheel publication identity differs from the frozen input")
            for source in (ROOT / "app/src/lakematch_review/backend").glob("*.py"):
                if sha(package / "lakematch_review/backend" / source.name) != sha(source):
                    raise ValueError(f"Packaged backend differs: {source.name}")
            if not (package / "lakematch_review/__dist__/index.html").is_file():
                raise ValueError("Fresh wheel has no built frontend")
            env = {**os.environ, "PYTHONPATH": str(package), "LAKEMATCH_REVIEW_STORE": "sqlite",
                   "LAKEMATCH_REVIEW_DATABASE": str(package / "unused-review.sqlite")}
            env.pop("DATABRICKS_APP_NAME", None)
            verify_import = ("import pathlib, sys; import lakematch_review.backend.golden_demo as demo; "
                "assert pathlib.Path(demo.__file__).resolve().is_relative_to(pathlib.Path(sys.argv[1])), demo.__file__; "
                "print('Backend import verified inside fresh wheel'); "
                "import pytest; raise SystemExit(pytest.main(sys.argv[2:]))")
            run([ROOT / "app/.venv/bin/python", "-c", verify_import, str(package), "-q", str(ROOT / "app/tests"),
                 "--junitxml=" + str(junit)], env=env, timeout=120)
            suite = ET.parse(junit).getroot().find("testsuite")
            if suite is None or int(suite.attrib["tests"]) != config["expected_app_tests"] or any(int(suite.attrib[k]) for k in ("errors", "failures", "skipped")):
                raise ValueError("Fresh-package app tests did not all pass")
            report["app_tests"] = {k: suite.attrib[k] for k in ("tests", "errors", "failures", "skipped", "time")}
            report["junit_sha256"] = sha(junit)
            run([sys.executable, ROOT / "tools/preview_golden_app.py", "--output", str(preview)], env=env, timeout=130)
            browser = json.loads((preview / "preview.json").read_text())
            if browser["page_errors"] or not all(browser[k] for k in ("mobile_fits", "keyboard_disclosure", "error_recovery")):
                raise ValueError("Fresh-package browser checks failed")
            report["browser"] = browser
            report["preview_artifacts"] = {str(p.relative_to(ROOT)): {"sha256": sha(p), "bytes": p.stat().st_size}
                                           for p in sorted(preview.iterdir()) if p.is_file()}
            report["package_import_verified"] = True
        report["cleanup"] = "extracted wheel and temporary stores removed; browser/server runner completed"
        verify_inputs(config)
        report.update(status="passed", gate="first_synthetic_apx_golden_record_detail",
                      companies=6, publications=2, field_explanations=96, explicit_pair_comparisons=12)
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        traceback.print_exc()
    finally:
        report["extracted_package_removed"] = extracted_path is None or not extracted_path.exists()
        report.update(ended_at=datetime.now(timezone.utc).isoformat(), wall_seconds=time.perf_counter() - start,
                      main_process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      memory_scope="main Python process on macOS; excludes child build/browser processes")
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "report": str(report_path.relative_to(ROOT))}), flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
