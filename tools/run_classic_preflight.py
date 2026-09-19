#!/usr/bin/env python3
"""Distinct ENV probe: a policy-compatible job cluster, not all-purpose create.

The earlier two all-purpose requests timed out without IDs. This tests the Job
Compute policy via a bounded submitted job, and terminates only its exact cluster.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    if args.profile != "fevm-gdpr2":
        raise ValueError("Use the explicitly selected campaign profile")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = f"/Workspace/Users/laurent.fabre@databricks.com/lakematch/20260919/classic_{stamp}"
    destination = Path(args.report)
    report = {"profile": args.profile, "started_at": stamp, "workspace_root": root,
              "run_id": None, "cluster_id": None, "commands": [], "observed_cost": None}

    def save():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + "\n")

    def cli(*parts, payload=None):
        command = ["databricks", *parts, "--profile", args.profile, "--output", "json"]
        if payload is not None:
            command += ["--json", json.dumps(payload)]
        report["commands"].append(command)
        save()
        value = subprocess.run(command, capture_output=True, text=True, timeout=90)
        if value.returncode:
            raise RuntimeError(value.stderr.strip())
        return json.loads(value.stdout) if value.stdout.strip() else {}

    run_id, terminal, cluster_id = None, False, None
    try:
        active = cli("jobs", "list-runs", "--active-only")
        active = active if isinstance(active, list) else active.get("runs", [])
        if any(r.get("run_name", "").startswith("lakematch-") for r in active):
            raise RuntimeError("An active campaign run exists; refuse parallel remote experiments")
        cli("workspace", "mkdirs", root)
        notebook = '''# Databricks notebook source
import json, platform
frame = spark.range(10).cache()
try:
    count = frame.count()
    assert count == 10
finally:
    frame.unpersist(blocking=True)
dbutils.notebook.exit(json.dumps({"spark": spark.version, "python": platform.python_version(), "rows": count, "classic_cache": "passed"}))
'''
        with tempfile.TemporaryDirectory(prefix="lakematch-classic-") as temporary:
            source = Path(temporary) / "probe.py"
            source.write_text(notebook)
            cli("workspace", "import", root + "/probe", "--file", str(source), "--format", "SOURCE", "--language", "PYTHON")
        cluster = {"policy_id": "00024020C629AFB5", "apply_policy_default_values": True,
                   "spark_version": "18.x-scala2.13", "node_type_id": "i3.xlarge", "num_workers": 1,
                   "runtime_engine": "STANDARD", "data_security_mode": "SINGLE_USER",
                   "single_user_name": "laurent.fabre@databricks.com",
                   "custom_tags": {"project": "lakematch", "campaign": "20260919", "purpose": "ENV-job-cluster"}}
        # Job clusters terminate at task completion. All-purpose auto-termination
        # settings are not valid on job clusters; explicit cleanup below is required.
        request = {"run_name": "lakematch-20260919-classic-env-" + stamp, "timeout_seconds": 900,
                   "tasks": [{"task_key": "probe", "timeout_seconds": 900, "new_cluster": cluster,
                              "notebook_task": {"notebook_path": root + "/probe"}}]}
        report["request"] = request
        run_id = report["run_id"] = cli("jobs", "submit", "--no-wait", payload=request)["run_id"]
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            run = report["run"] = cli("jobs", "get-run", str(run_id))
            task = run.get("tasks", [{}])[0]
            cluster_id = report["cluster_id"] = task.get("cluster_instance", {}).get("cluster_id", cluster_id)
            state = run["state"]["life_cycle_state"]
            save()
            print(f"Classic ENV {run_id}: {state}, cluster={cluster_id}", flush=True)
            if state in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}:
                terminal = True
                if task.get("run_id"):
                    report["output"] = cli("jobs", "get-run-output", str(task["run_id"]))
                if run["state"].get("result_state") != "SUCCESS":
                    raise RuntimeError(f"Classic capability probe failed: {run['state']}")
                result = json.loads(report["output"]["notebook_output"]["result"])
                if result.get("classic_cache") != "passed" or not cluster_id:
                    raise RuntimeError("Classic execution/caching was not proved")
                report.update(status="completed", result=result)
                break
            time.sleep(10)
        else:
            raise TimeoutError("Classic job exceeded the 900-second startup/execution envelope")
    finally:
        if run_id and not terminal:
            try:
                cli("jobs", "cancel-run", str(run_id))
                for _ in range(24):
                    run = report["run"] = cli("jobs", "get-run", str(run_id))
                    task = run.get("tasks", [{}])[0]
                    cluster_id = report["cluster_id"] = task.get("cluster_instance", {}).get("cluster_id", cluster_id)
                    if run["state"]["life_cycle_state"] in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}:
                        terminal = True
                        break
                    time.sleep(5)
            except Exception as exc:
                # A job API failure must not bypass termination of a known cluster.
                report["cancellation_error"] = str(exc)
                save()
        if cluster_id:
            cli("clusters", "delete", cluster_id, "--no-wait")
            for _ in range(36):
                cluster = report["final_cluster"] = cli("clusters", "get", cluster_id)
                save()
                if cluster["state"] == "TERMINATED":
                    break
                time.sleep(5)
            if report.get("final_cluster", {}).get("state") != "TERMINATED":
                report["cleanup"] = "failed to verify owned cluster termination"
                save()
                raise RuntimeError(report["cleanup"])
        report["cleanup"] = "owned cluster TERMINATED; job terminal" if cluster_id and terminal else "no cluster returned; inspect job terminal state"
        report["ended_at"] = datetime.now(timezone.utc).isoformat()
        save()
        if run_id and not terminal:
            raise RuntimeError("Job termination remains unverified")


if __name__ == "__main__":
    main()
