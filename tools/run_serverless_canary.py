#!/usr/bin/env python3
"""Submit one bounded serverless canary, monitor, collect, cancel on timeout."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()
    root = "/Workspace/Users/laurent.fabre@databricks.com/lakematch/20260919"
    report = {"profile": args.profile, "started_at": datetime.now(timezone.utc).isoformat(),
              "commands": [], "run_id": None, "state": "not submitted", "observed_cost": None}
    destination = Path(args.report)

    def save():
        destination.write_text(json.dumps(report, indent=2) + "\n")

    def cli(*parts, payload=None):
        command = ["databricks", *parts, "--profile", args.profile, "--output", "json"]
        if payload is not None:
            command += ["--json", json.dumps(payload)]
        report["commands"].append(command)
        save()
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        if parts[:2] == ("workspace", "import-dir"):
            # import-dir emits a stream of progress objects even with -o json.
            return {"imported": True}
        return json.loads(result.stdout) if result.stdout.strip() else {}

    run_id, terminal = None, False
    try:
        cli("workspace", "import-dir", "src", root + "/src", "--overwrite")
        cli("workspace", "import", root + "/serverless_canary", "--file", "tools/serverless_canary.py",
            "--format", "SOURCE", "--language", "PYTHON", "--overwrite")
        request = {"run_name": "lakematch-20260919-platform-canary", "timeout_seconds": 900,
                   "performance_target": "STANDARD",
                   "tasks": [{"task_key": "canary", "timeout_seconds": 600,
                              "notebook_task": {"notebook_path": root + "/serverless_canary"}, "environment_key": "canary"}],
                   "environments": [{"environment_key": "canary", "spec": {"client": "4", "dependencies": ["mlflow==3.16.0", "pyyaml==6.0.3"]}}]}
        report["request"] = request
        created = cli("jobs", "submit", "--no-wait", payload=request)
        run_id = report["run_id"] = created["run_id"]
        save()
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            run = cli("jobs", "get-run", str(run_id))
            report["run"] = run
            state = run["state"]["life_cycle_state"]
            report["state"] = state
            save()
            print(f"serverless {run_id}: {state}", flush=True)
            if state in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}:
                terminal = True
                if run.get("tasks"):
                    report["output"] = cli("jobs", "get-run-output", str(run["tasks"][0]["run_id"]))
                save()
                if run["state"].get("result_state") != "SUCCESS":
                    raise RuntimeError(f"Canary failed: {run['state']}")
                break
            time.sleep(10)
        else:
            raise TimeoutError("Canary exceeded 900-second submission/startup/execution envelope")
    finally:
        if run_id is not None and not terminal:
            cli("jobs", "cancel-run", str(run_id))
            for _ in range(30):
                run = cli("jobs", "get-run", str(run_id))
                report["run"] = run
                if run["state"]["life_cycle_state"] in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}:
                    terminal = True
                    break
                time.sleep(5)
        report["cleanup"] = "terminal serverless run; no persistent compute" if terminal else "no returned run ID or termination unverified"
        report["ended_at"] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == "__main__":
    main()
