#!/usr/bin/env python3
"""Submit one owned serverless proof, collect evidence and remove workspace files."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from workspace_support import client

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Fresh report path required")
    w = client(args.profile)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8]
    namespace = "lfb_lineage_" + stamp
    report = {"phase": "LF-B", "packages": ["LM-006", "LM-009 foundation"], "status": "running", "profile": args.profile,
              "started_at": datetime.now(timezone.utc).isoformat(), "namespace": namespace, "observed_cost": None,
              "cost_status": "unreconciled", "confirmation_materialized": False, "commands": [], "cleanup": {}}
    run_id, terminal, workspace_root = None, False, None
    execution_deadline = time.monotonic() + 900
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def save(): args.output.write_text(json.dumps(report, indent=2) + "\n")
    def cli(*parts, payload=None):
        command = ["databricks", *parts, "--profile", args.profile, "--output", "json"]
        if payload is not None:
            command += ["--json", json.dumps(payload)]
        report["commands"].append(command)
        save()
        result = subprocess.run(command, capture_output=True, text=True, timeout=70)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        if parts[:2] == ("workspace", "import-dir"):
            return {"imported": True}
        return json.loads(result.stdout) if result.stdout.strip() else {}
    try:
        assert not any("lakematch" in (r.run_name or "").lower() for r in w.jobs.list_runs(active_only=True)), "Active campaign job"
        assert all(p.state.value == "IDLE" for p in w.pipelines.list_pipelines() if "lakematch" in (p.name or "").lower()), "Active campaign pipeline"
        user = cli("current-user", "me")["userName"]
        workspace_root = f"/Workspace/Users/{user}/lakematch/{namespace}"
        report["workspace_root"] = workspace_root
        paths = [ROOT / "tools/lakefusion_lineage_notebook.py", Path(__file__), ROOT / "bench/lakefusion/LINEAGE_PLAN.md",
                 *sorted((ROOT / "src/lakematch/mastering").glob("*.py")), ROOT / "src/lakematch/publication.py", ROOT / "src/lakematch/delta_publication.py"]
        report["source_hashes"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        retry_plan = ROOT / "bench/lakefusion/LINEAGE_RETRY_PLAN.md"
        report["source_hashes"][str(retry_plan.relative_to(ROOT))] = hashlib.sha256(retry_plan.read_bytes()).hexdigest()
        report["fixture_sha256"] = hashlib.sha256(args.fixture.read_bytes()).hexdigest()
        cli("workspace", "mkdirs", workspace_root)
        cli("workspace", "import-dir", "src", workspace_root + "/src")
        cli("workspace", "import", workspace_root + "/fixture.json", "--file", str(args.fixture), "--format", "RAW")
        cli("workspace", "import", workspace_root + "/proof", "--file", "tools/lakefusion_lineage_notebook.py", "--format", "SOURCE", "--language", "PYTHON")
        request = {"run_name": "lakematch-" + namespace, "timeout_seconds": 900, "performance_target": "STANDARD",
                   "idempotency_token": namespace,
                   "tasks": [{"task_key": "provenance", "timeout_seconds": 720,
                              "notebook_task": {"notebook_path": workspace_root + "/proof",
                                                "base_parameters": {"source_root": workspace_root, "namespace": namespace}},
                              "environment_key": "provenance"}],
                   "environments": [{"environment_key": "provenance", "spec": {"client": "4", "dependencies": []}}]}
        report["request"] = request
        run_id = report["run_id"] = cli("jobs", "submit", "--no-wait", payload=request)["run_id"]
        while time.monotonic() < execution_deadline:
            run = cli("jobs", "get-run", str(run_id))
            report["run"] = run
            state = run["state"]["life_cycle_state"]
            print(f"Provenance run {run_id}: {state}", flush=True)
            if state in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}:
                terminal = True
                output = cli("jobs", "get-run-output", str(run["tasks"][0]["run_id"]))
                report["output"] = output
                result = json.loads(output.get("notebook_output", {}).get("result", "null"))
                report["result"] = result
                if run["state"].get("result_state") != "SUCCESS" or not result or result["status"] != "passed":
                    raise RuntimeError("Remote provenance proof failed; see retained task output")
                assert result["fixture_sha256"] == report["fixture_sha256"]
                report["status"] = "passed"
                break
            save()
            time.sleep(10)
        else:
            raise TimeoutError("Remote provenance run exceeded its declared envelope")
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
    finally:
        if run_id is not None and not terminal:
            try:
                cli("jobs", "cancel-run", str(run_id))
                deadline = time.monotonic() + 150
                while time.monotonic() < deadline:
                    run = cli("jobs", "get-run", str(run_id))
                    report["run"] = run
                    if run["state"]["life_cycle_state"] in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}:
                        terminal = True
                        break
                    time.sleep(5)
            except Exception as error:
                report["cleanup"]["cancel_error"] = str(error)
        report["cleanup"]["run_terminal"] = terminal if run_id else "not submitted"
        if workspace_root and (terminal or run_id is None):
            try:
                cli("workspace", "delete", workspace_root, "--recursive")
                report["cleanup"]["workspace_files_removed"] = True
            except Exception as error:
                report["cleanup"]["workspace_error"] = str(error)
                report["status"] = "failed"
        report["cleanup"]["tables"] = (report.get("result") or {}).get("cleanup", "unverified; inspect exact experiment prefix")
        report["ended_at"] = datetime.now(timezone.utc).isoformat()
        save()
    print(json.dumps({k: report.get(k) for k in ("status", "run_id", "cleanup", "error")}), flush=True)
    return int(report["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
