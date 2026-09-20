#!/usr/bin/env python3
"""Bounded local experiment runner; verification never calls this script."""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import signal
import shutil
import subprocess
import sys
import time
from uuid import uuid4

from evidence import ROOT, sha256, source_digest, source_files


def live_group_members(pgid):
    """macOS may return EPERM while a just-exited group's zombies are reaped."""
    result = subprocess.run(["ps", "-axo", "pid=,pgid=,stat="], check=True, capture_output=True, text=True)
    members = []
    for line in result.stdout.splitlines():
        pid, group, state = line.split()
        if int(group) == pgid and not state.startswith("Z"):
            members.append(int(pid))
    return members


def signal_owned_group(pgid, sig, *, exit_grace_seconds=2.):
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass
    except PermissionError:
        # Never interpret permission denial as successful cleanup without an
        # independent process inventory. A live owned process remains an error.
        deadline = time.monotonic() + exit_grace_seconds
        while live_group_members(pgid):
            if time.monotonic() >= deadline:
                raise
            time.sleep(.1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--hypothesis", required=True)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--config")
    parser.add_argument("--dataset", default="synthetic unit fixtures unless command/config declares a prepared public corpus")
    parser.add_argument("--baseline", default="specification; no accepted implementation baseline")
    parser.add_argument("--primary-metric", default="command exit status plus recorded assertions/artifacts")
    parser.add_argument("--seed", type=int, action="append")
    parser.add_argument("--workspace", help="Explicit remote workspace profile, when the child submits remote work")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or not 1 <= args.timeout <= 3600:
        parser.error("A command and a timeout in [1, 3600] seconds are required")
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%SZ") + "-" + args.kind + "-" + uuid4().hex[:6]
    directory = ROOT / "experiments" / run_id
    directory.mkdir(parents=True)
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    manifest = {
        "schema_version": 1, "run_id": run_id, "phase": args.phase, "kind": args.kind,
        "hypothesis": args.hypothesis, "baseline": args.baseline, "dataset": args.dataset,
        "primary_metric": args.primary_metric,
        "source_commit": git.stdout.strip(), "source_digest": source_digest(args.phase),
        "source_files": {str(p.relative_to(ROOT)): sha256(p) for p in source_files(args.phase)},
        "command": command, "started_at": started.isoformat(), "status": "running",
        "versions": {"python": platform.python_version(), **{p: importlib.metadata.version(p) for p in ("pyspark", "mlflow", "pyyaml", "pytest")}},
        "runtime": {"platform": platform.platform(), "test_mode": os.environ.get("LAKEMATCH_TEST_MODE", "classic"),
                    "java_home": os.environ.get("JAVA_HOME"), "workspace": args.workspace},
        "budget": {"timeout_seconds": args.timeout, "remote_spend": None if args.workspace or args.phase == "ENV" else 0,
                   "cost_status": "unreconciled" if args.workspace or args.phase == "ENV" else "local only", "parallel_experiments": 1},
        "config": {"path": args.config, "sha256": sha256(args.config)} if args.config else None,
        "seeds": args.seed or [0], "model_run_ids": [], "artifacts": [], "cleanup": "pending",
    }
    for optional in ("sentence-transformers", "torch", "transformers", "recordlinkage"):
        try:
            manifest["versions"][optional] = importlib.metadata.version(optional)
        except importlib.metadata.PackageNotFoundError:
            pass
    path = directory / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(run_id, flush=True)
    t0 = time.perf_counter()
    exit_code = 1
    child = None
    cleanup = "not started"
    try:
        with (directory / "stdout.txt").open("w") as out, (directory / "stderr.txt").open("w") as err:
            child = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=err, start_new_session=True)
            manifest["process_group_id"] = child.pid
            path.write_text(json.dumps(manifest, indent=2) + "\n")
            try:
                exit_code = child.wait(timeout=args.timeout)
                manifest["status"] = "passed" if exit_code == 0 else "failed"
            except subprocess.TimeoutExpired:
                manifest["status"] = "timeout"
            except KeyboardInterrupt:
                manifest["status"] = "canceled"
            finally:
                cleanup = "pending owned-process cleanup"
                # Terminate any JVM children, including orphaned Connect servers, in
                # this experiment's process group only, even after the parent exits.
                signal_owned_group(child.pid, signal.SIGTERM)
                if child.poll() is None:
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        signal_owned_group(child.pid, signal.SIGKILL)
                        child.wait()
                # The Python parent may exit before the JVM finishes its shutdown
                # hooks. Wait for the entire owned group before hashing its logs.
                # Otherwise a late JVM log write invalidates a sealed manifest.
                deadline = time.monotonic() + 10
                while True:
                    if not live_group_members(child.pid):
                        break
                    if time.monotonic() >= deadline:
                        signal_owned_group(child.pid, signal.SIGKILL)
                        time.sleep(.2)  # SIGKILL closes inherited output descriptors.
                        if live_group_members(child.pid):
                            raise RuntimeError("Owned processes remain alive after SIGKILL")
                        break
                    time.sleep(.1)
                cleanup = "owned process group terminated; no live members in process inventory"
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        manifest.update(exit_code=exit_code, wall_seconds=time.perf_counter() - t0,
                        ended_at=datetime.now(timezone.utc).isoformat(), cleanup=cleanup)
        for artifact in [str(directory / "stdout.txt"), str(directory / "stderr.txt"), *args.artifact]:
            p = Path(artifact).resolve()
            if p.is_file():
                if p.parent != directory:
                    destination = directory / "evidence" / p.name
                    destination.parent.mkdir(exist_ok=True)
                    shutil.copy2(p, destination)
                    p = destination
                manifest["artifacts"].append({"path": str(p.relative_to(ROOT)), "sha256": sha256(p), "bytes": p.stat().st_size})
        path.write_text(json.dumps(manifest, indent=2) + "\n")
        event = {k: manifest[k] for k in ("run_id", "phase", "kind", "status", "exit_code", "source_digest", "wall_seconds", "ended_at")}
        event["manifest"] = str(path.relative_to(ROOT))
        with (ROOT / "experiments" / "runs.jsonl").open("a") as ledger:
            ledger.write(json.dumps(event, sort_keys=True) + "\n")
        print(json.dumps(event), flush=True)
    return 0 if manifest["status"] == "passed" and exit_code == 0 else (exit_code or 1)


if __name__ == "__main__":
    sys.exit(main())
