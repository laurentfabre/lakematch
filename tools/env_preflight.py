#!/usr/bin/env python3
"""Bounded ENV capability check using the explicitly selected CLI profile.

No shared resources are started or stopped. The sole classic cluster created by
this command is terminated in finally, including on error and interruption.
"""
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
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {"profile": args.profile, "observed_at": datetime.now(timezone.utc).isoformat(),
              "operations": [], "owned_resources": {}, "classic_state": "untested",
              "budget": {"classic_nodes": 1, "autotermination_minutes": 10, "startup_timeout_seconds": 600,
                         "cleanup_timeout_seconds": 600, "dollar_cap": None,
                         "authorization": "Laurent: FEVM are dev workspace so do not worry about that (2026-09-19)"},
              "quota": "unavailable: official FEVM MCP is not connected",
              "genie_app_obo": "untested: requires a campaign app, user delegation and fixture tables"}

    def save():
        report_path.write_text(json.dumps(report, indent=2) + "\n")

    def cli(*parts, payload=None):
        command = ["databricks", *parts, "--profile", args.profile, "--output", "json"]
        if payload is not None:
            command += ["--json", json.dumps(payload)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=240 if parts[:2] == ("clusters", "create") else 90)
        except subprocess.TimeoutExpired:
            report["operations"].append({"command": command, "exit_code": None, "error": "CLI request timed out; inventory reconciliation required"})
            save()
            raise
        report["operations"].append({"command": command, "exit_code": result.returncode,
                                     "observed_at": datetime.now(timezone.utc).isoformat(),
                                     "error": result.stderr.strip() if result.returncode else None})
        save()
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        return json.loads(result.stdout) if result.stdout.strip() else {}

    cluster_id = None
    try:
        user = cli("current-user", "me")
        report["user"] = user["userName"]
        policies = cli("cluster-policies", "list")
        report["policies"] = [{k: p.get(k) for k in ("policy_id", "name", "definition")} for p in policies]
        personal = next(p for p in policies if p["name"] == "Personal Compute")
        schema = {"name": "lakematch_20260919", "catalog_name": "gdpr2_catalog",
                  "comment": "lakematch campaign; public/synthetic corpora only; owned by Laurent Fabre"}
        existing = cli("schemas", "list", schema["catalog_name"])
        created = next((s for s in existing if s["name"] == schema["name"]), None)
        if created is None:
            created = cli("schemas", "create", payload=schema)
        elif created.get("owner") != user["userName"] or not created.get("comment", "").startswith("lakematch campaign;"):
            raise RuntimeError("Campaign schema exists but its ownership/description differs")
        report["owned_resources"]["schema"] = created["full_name"]
        volumes = cli("volumes", "list", schema["catalog_name"], schema["name"])
        volume = next((v for v in volumes if v["name"] == "artifacts"), None)
        if volume is None:
            volume = cli("volumes", "create", payload={"catalog_name": schema["catalog_name"],
                     "schema_name": schema["name"], "name": "artifacts", "volume_type": "MANAGED",
                         "comment": "Public/synthetic experiment artifacts and model staging"})
        report["owned_resources"]["volume"] = volume["full_name"]
        root = f"/Workspace/Users/{user['userName']}/lakematch/20260919"
        cli("workspace", "mkdirs", root)
        report["owned_resources"]["workspace_root"] = root
        report["planned_model"] = "gdpr2_catalog.lakematch_20260919.person"
        spec = {"cluster_name": "lakematch-20260919-env", "spark_version": "18.x-scala2.13",
                "node_type_id": "i3.xlarge", "num_workers": 0, "runtime_engine": "STANDARD",
                "policy_id": personal["policy_id"], "apply_policy_default_values": True,
                "autotermination_minutes": 10, "data_security_mode": "SINGLE_USER", "single_user_name": user["userName"],
                "spark_conf": {"spark.databricks.cluster.profile": "singleNode", "spark.master": "local[*, 4]"},
                "custom_tags": {"ResourceClass": "SingleNode", "project": "lakematch", "campaign": "20260919", "purpose": "ENV"}}
        report["classic_spec"] = spec
        created = cli("clusters", "create", "--no-wait", payload=spec)
        cluster_id = created["cluster_id"]
        report["owned_resources"]["cluster_id"] = cluster_id
        save()
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            current = cli("clusters", "get", cluster_id)
            state = current["state"]
            report["classic_state"] = state
            save()
            print(f"classic {cluster_id}: {state}", flush=True)
            if state == "RUNNING":
                report["classic_create_capability"] = "supported: policy-compatible single-node cluster reached RUNNING"
                break
            if state in {"ERROR", "TERMINATED"}:
                report["classic_failure"] = current.get("termination_reason", current.get("state_message"))
                raise RuntimeError(f"Classic preflight failed: {report['classic_failure']}")
            time.sleep(10)
        else:
            raise TimeoutError("Classic startup exceeded the bounded 600-second window")
    finally:
        if cluster_id:
            cli("clusters", "delete", cluster_id)
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                current = cli("clusters", "get", cluster_id)
                report["classic_final_state"] = current["state"]
                save()
                if current["state"] == "TERMINATED":
                    break
                time.sleep(5)
            else:
                raise RuntimeError(f"Could not verify termination of owned cluster {cluster_id}")
        report["ended_at"] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == "__main__":
    main()
