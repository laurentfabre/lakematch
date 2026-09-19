#!/usr/bin/env python3
"""One bounded serverless model experiment with two sequential fresh tasks."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    if args.profile != "fevm-gdpr2":
        raise ValueError("This campaign is authorized only for the selected fevm-gdpr2 profile")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    workspace = f"/Workspace/Users/laurent.fabre@databricks.com/lakematch/20260919/tracking_{stamp}"
    volume = f"/Volumes/gdpr2_catalog/lakematch_20260919/artifacts/tracking_{stamp}"
    report = {"profile": args.profile, "workspace_root": workspace, "volume_root": volume,
              "started_at": stamp, "run_id": None, "commands": [], "observed_cost": None}
    destination = Path(args.report)
    destination.parent.mkdir(parents=True, exist_ok=True)

    def save():
        destination.write_text(json.dumps(report, indent=2) + "\n")

    def cli(*parts, payload=None):
        command = ["databricks", *parts, "--profile", args.profile, "--output", "json"]
        if payload is not None:
            command += ["--json", json.dumps(payload)]
        report["commands"].append(command)
        save()
        value = subprocess.run(command, capture_output=True, text=True, timeout=120)
        if value.returncode:
            raise RuntimeError(value.stderr.strip())
        if parts[:2] in {("workspace", "import-dir"), ("fs", "cp")}:
            return {"completed": True}
        return json.loads(value.stdout) if value.stdout.strip() else {}

    run_id, terminal = None, False
    try:
        active = cli("jobs", "list-runs", "--active-only")
        active = active if isinstance(active, list) else active.get("runs", [])
        if any(r.get("run_name", "").startswith("lakematch-") for r in active):
            raise RuntimeError("An active campaign run exists; refusing a concurrent remote experiment")
        cli("workspace", "import-dir", "src", workspace + "/src", "--overwrite")
        cli("workspace", "mkdirs", workspace + "/tools")
        cli("workspace", "import", workspace + "/tools/tracking_canary.py", "--file", "tools/tracking_canary.py",
            "--format", "RAW", "--overwrite")
        cli("workspace", "import", workspace + "/tracking", "--file", "tools/tracking_notebook.py",
            "--format", "SOURCE", "--language", "PYTHON", "--overwrite")
        tasks = [{"task_key": mode, "timeout_seconds": 600,
                  "notebook_task": {"notebook_path": workspace + "/tracking", "base_parameters": {
                      "mode": mode, "root": volume, "workspace_root": workspace}}, "environment_key": "model"}
                 for mode in ("train", "reload")]
        tasks[1]["depends_on"] = [{"task_key": "train"}]
        request = {"run_name": "lakematch-20260919-zr5-" + stamp, "timeout_seconds": 1500,
                   "performance_target": "STANDARD", "tasks": tasks,
                   "environments": [{"environment_key": "model", "spec": {"client": "4",
                       "dependencies": ["mlflow==3.16.0", "pyyaml==6.0.3"]}}]}
        report["request"] = request
        run_id = report["run_id"] = cli("jobs", "submit", "--no-wait", payload=request)["run_id"]
        save()
        deadline = time.monotonic() + 1500
        while time.monotonic() < deadline:
            run = report["run"] = cli("jobs", "get-run", str(run_id))
            state = run["state"]["life_cycle_state"]
            save()
            print(f"ZR-5 serverless {run_id}: {state}", flush=True)
            if state in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}:
                terminal = True
                report["outputs"] = {t["task_key"]: cli("jobs", "get-run-output", str(t["run_id"]))
                                     for t in run.get("tasks", []) if t.get("run_id")}
                save()
                if run["state"].get("result_state") != "SUCCESS":
                    raise RuntimeError(f"Model acceptance failed: {run['state']}")
                result = json.loads(report["outputs"]["reload"]["notebook_output"]["result"])
                if not result.get("fresh_session_equivalence") or not result.get("registry"):
                    raise RuntimeError("Remote output lacks model acceptance assertions")
                report["result"] = result
                local = Path("data/remote_models") / stamp
                local.mkdir(parents=True, exist_ok=True)
                cli("fs", "cp", "dbfs:" + volume, str(local), "--recursive")
                import hashlib
                report["exported_artifacts"] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                                for p in sorted(local.rglob("*")) if p.is_file()}
                report["status"] = "completed"
                break
            time.sleep(10)
        else:
            raise TimeoutError("Remote model run exceeded its 1500-second envelope")
    finally:
        if run_id is not None and not terminal:
            cli("jobs", "cancel-run", str(run_id))
            for _ in range(30):
                run = report["run"] = cli("jobs", "get-run", str(run_id))
                if run["state"]["life_cycle_state"] in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}:
                    terminal = True
                    break
                time.sleep(5)
        report["cleanup"] = "terminal serverless run; no persistent compute" if terminal else "no returned run ID or termination unverified"
        report["ended_at"] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == "__main__":
    main()
