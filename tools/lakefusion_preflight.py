#!/usr/bin/env python3
"""Bounded metadata-only feasibility checks; never starts or creates resources."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import time


def summarize(name, value):
    if name == "identity":
        return {"authenticated": bool(value.get("id"))}
    if name in {"lakebase", "ai_search", "model_serving"}:
        if isinstance(value, list):
            items = value
        else:
            items = next((value[k] for k in ("projects", "endpoints") if k in value), [])
        return {"returned_resources": len(items), "limit": 1,
                "creation_permission": "untested", "data_plane": "untested"}
    if name == "app":
        return {"name": value.get("name"), "compute_status": value.get("compute_status"),
                "forward_user_access_token": value.get("forward_user_access_token"),
                "delegated_flow": "untested"}
    if name == "warehouse":
        return {k: value.get(k) for k in ("id", "state", "warehouse_type",
                                        "enable_serverless_compute", "auto_stop_mins")}
    if name == "genie":
        return {"space_id": value.get("space_id"), "conversation_execution": "not_requested"}
    if name == "schema":
        return {"full_name": value.get("full_name"), "write_permission": "untested"}
    raise ValueError(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh report path; earlier evidence is immutable")
    version = subprocess.check_output(["databricks", "--version"], text=True, timeout=10).strip()
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match or tuple(map(int, match.groups())) < (1, 0, 0):
        parser.error("Databricks CLI >=1.0.0 is required")
    probes = [
        ("identity", ["current-user", "me"]),
        ("lakebase", ["postgres", "list-projects", "--limit", "1"]),
        ("ai_search", ["vector-search-endpoints", "list-endpoints", "--limit", "1"]),
        ("model_serving", ["serving-endpoints", "list", "--limit", "1"]),
        ("app", ["apps", "get", "lakematch-review-20260919"]),
        ("warehouse", ["warehouses", "get", "ec3b6df6c1cabcd4"]),
        ("genie", ["genie", "get-space", "01f1b55eb48a1c0bae6f117fbdbc064e"]),
        ("schema", ["schemas", "get", "gdpr2_catalog.lakematch_20260919"]),
    ]
    report = {"schema_version": 1, "phase": "LF-A", "profile": args.profile,
              "cli": version, "started_at": datetime.now(timezone.utc).isoformat(),
              "resource_mutations": [], "checks": []}
    for name, command in probes:
        full = ["databricks", *command, "--profile", args.profile, "--output", "json"]
        check = {"capability": name, "command": full}
        started = time.monotonic()
        try:
            result = subprocess.run(full, capture_output=True, text=True, timeout=45)
            if result.returncode:
                # Only allowlisted read APIs above can reach this path; no credentials API.
                check.update(status="check_failed", exit_code=result.returncode,
                             error=(result.stderr or result.stdout).strip()[:500])
            else:
                check.update(status="metadata_access_verified", detail=summarize(name, json.loads(result.stdout)))
        except subprocess.TimeoutExpired:
            check.update(status="timeout", error="Read-only CLI call exceeded 45 seconds")
        except (ValueError, TypeError, KeyError) as error:
            check.update(status="response_unrecognized", error=type(error).__name__)
        check["wall_seconds"] = round(time.monotonic() - started, 3)
        report["checks"].append(check)
        print(f"{name}: {check['status']}", flush=True)
        if name == "identity" and check["status"] != "metadata_access_verified":
            break
    report["ended_at"] = datetime.now(timezone.utc).isoformat()
    report["note"] = "Metadata access is not creation permission, inference, SQL, index, database or delegated app acceptance."
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    return int(any(c["status"] != "metadata_access_verified" for c in report["checks"]))


if __name__ == "__main__":
    raise SystemExit(main())
