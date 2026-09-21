"""Deploy the bundled app, read its APIs, and stop owned compute on every exit."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

import requests

from workspace_support import APP, WAREHOUSE_NAME, client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app/acceptance"))
from lifecycle import stop_when_ready


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    w = client(args.profile)
    warehouses = [x for x in w.warehouses.list() if x.name == WAREHOUSE_NAME]
    if len(warehouses) != 1:
        raise RuntimeError("Expected the single campaign-owned warehouse")
    warehouse = w.warehouses.get(warehouses[0].id)
    app = w.apps.get(APP)
    if app.compute_status.state.value != "STOPPED":
        raise RuntimeError("Owned app must be stopped before this smoke test")
    if warehouse.state.value not in {"STOPPED", "RUNNING"} or (warehouse.num_active_sessions or 0):
        raise RuntimeError("Owned warehouse must be stopped or idle before this smoke test")
    if any(r.run_name and "lakematch" in r.run_name for r in w.jobs.list_runs(active_only=True)):
        raise RuntimeError("Another campaign job is active")
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "profile": args.profile,
              "app": APP, "warehouse_id": warehouse.id, "status": "running", "checks": {}, "cleanup": {}}

    def save():
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")

    def interrupted(*_):
        raise KeyboardInterrupt("deployment smoke interrupted")

    signal.signal(signal.SIGTERM, interrupted)
    save()
    app_started = warehouse_started = False
    try:
        warehouse_started = True
        w.warehouses.start_and_wait(warehouse.id, timeout=timedelta(minutes=5))
        print("Owned warehouse ready", flush=True)
        app_started = True
        w.apps.start_and_wait(APP, timeout=timedelta(minutes=6))
        print("Owned app compute ready", flush=True)
        previous_id = app.active_deployment.deployment_id if app.active_deployment else None
        # bundle run carries the DAB's inline environment config, unlike a bare
        # apps deploy using only source_code_path.
        result = subprocess.run(["databricks", "bundle", "run", "review", "--no-wait",
            "--target", "dev", "--profile", args.profile, "--output", "json",
            "--var", "warehouse_id=" + warehouse.id],
            cwd=ROOT / "app", text=True, capture_output=True, timeout=90)
        if result.returncode:
            raise RuntimeError("App bundle run failed: " + result.stderr[:2000])
        # CLI 1.17's Apps runner emits no JSON even with --output json.
        # Read the acknowledged deployment from the Apps API instead.
        current = w.apps.get(APP).as_dict()
        deployments = [current.get(key) for key in ("pending_deployment", "active_deployment")]
        deployment = next((item for item in deployments if item and item.get("deployment_id") != previous_id), None)
        if not deployment:
            raise RuntimeError("Bundle run returned but no new app deployment was acknowledged")
        report["deployment_id"] = deployment["deployment_id"]
        save()
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            deployed = w.apps.get_deployment(APP, report["deployment_id"])
            state = deployed.status.state.value
            print("App deployment:", state, flush=True)
            if state == "SUCCEEDED":
                break
            if state in {"FAILED", "CANCELLED"}:
                raise RuntimeError(f"App deployment {state}: {deployed.status.message}")
            time.sleep(10)
        else:
            raise TimeoutError("App deployment exceeded 600 seconds")
        app = w.apps.get(APP)
        for path in ("/", "/api/session", "/api/queue?limit=1", "/api/reviews", "/api/statistics"):
            response = requests.get(app.url.rstrip("/") + path, headers=w.config.authenticate(),
                                    timeout=120, allow_redirects=False)
            report["checks"][path] = {"status_code": response.status_code}
            save()
            if response.status_code != 200:
                raise RuntimeError(f"App smoke {path}: HTTP {response.status_code}")
            if path == "/api/session":
                value = response.json()
                if value["storage"] != "delta" or not value["user"] or value["user"] == "local-reviewer":
                    raise RuntimeError("App did not use Delta and workspace proxy identity")
                report["checks"][path].update(storage=value["storage"], authenticated=True,
                                              genie_enabled=value["genie_enabled"])
            elif path in {"/api/queue?limit=1", "/api/reviews"}:
                report["checks"][path]["returned_rows"] = len(response.json())
            elif path == "/":
                if '<div id="root">' not in response.text:
                    raise RuntimeError("App did not serve the built frontend")
        report["status"] = "passed"
    except BaseException as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        errors = []
        for name, started, stop in (
            ("app", app_started, lambda: stop_when_ready(
                lambda: w.apps.get(APP).as_dict(), lambda: w.apps.stop(APP), timeout=240)),
            ("warehouse", warehouse_started, lambda: w.warehouses.stop_and_wait(warehouse.id, timeout=timedelta(minutes=3))),
        ):
            if started:
                try:
                    stopped = stop()
                    state = stopped["compute_status"]["state"] if name == "app" else stopped.state.value
                    report["cleanup"][name] = state
                    if state != "STOPPED":
                        raise RuntimeError(f"{name} termination unverified")
                except Exception as error:
                    errors.append(f"{name}: {error}")
        if errors:
            report.update(status="cleanup_failed", cleanup_errors=errors)
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save()
        if errors:
            raise RuntimeError("; ".join(errors))


if __name__ == "__main__":
    main()
