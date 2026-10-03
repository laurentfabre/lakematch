"""ZR-7 platform evidence -> the "apx" and "deployed" sections of bench/results/app_e2e.json.

    python bench/app_deploy.py apx                     APX still maintained? (CLI version, repository activity)
    python bench/app_deploy.py deployed [--labels N]   the Databricks App on fourth-pat: state, SQL-warehouse
                                                       resource, N labels over HTTP read back from the Delta table,
                                                       statistics; then the app and the warehouse are stopped

The deployed check calls the app with an OAuth token of a service principal that holds CAN_USE on the app
(LAKEMATCH_APP_CLIENT_ID / LAKEMATCH_APP_CLIENT_SECRET; Databricks Apps refuse personal access tokens). It labels the first N queued pairs as `unsure` (recorded
with full provenance, never a training label) and retracts them again, so it leaves the label set unchanged.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from redact import redact  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "bench" / "results" / "app_e2e.json"
PROFILE, APP, WAREHOUSE, SCHEMA = "fourth-pat", "lakematch", "79dfcc5bc7019dd3", "workspace.lakematch"


def cli(*args: str) -> dict | list | str:
    r = subprocess.run(["databricks", *args, "--profile", PROFILE, "-o", "json"], capture_output=True, text=True,
                       timeout=600)
    if r.returncode:
        raise RuntimeError(f"databricks {' '.join(args)}: {r.stderr.strip()[:500]}")
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return r.stdout


def save(section: str, payload: dict) -> None:
    d = json.loads(OUT.read_text()) if OUT.exists() else {}
    d[section] = payload
    OUT.write_text(redact(json.dumps(d, indent=2, default=str)) + "\n")
    print(json.dumps(payload, indent=1, default=str)[:4000])


def apx() -> None:
    ver = subprocess.run(["apx", "--version"], capture_output=True, text=True).stdout.strip()
    gh = lambda path, q: subprocess.run(["gh", "api", path, "--jq", q], capture_output=True, text=True).stdout.strip()
    repo = json.loads(gh("repos/databricks-solutions/apx", "{pushed_at, updated_at, archived, open_issues_count}"))
    rel = json.loads(gh("repos/databricks-solutions/apx/releases", ".[0] | {tag_name, published_at}"))
    last = json.loads(gh("repos/databricks-solutions/apx/commits", ".[0] | {sha: .sha[0:7], date: .commit.author.date}"))
    age = (time.time() - time.mktime(time.strptime(repo["pushed_at"], "%Y-%m-%dT%H:%M:%SZ"))) / 86400
    save("apx", {"cli": ver, "checked_at": time.strftime("%Y-%m-%d"), "repository": repo, "latest_release": rel,
                 "last_commit": last, "days_since_push": round(age),
                 "verdict": ("not archived, but no push since " + repo["pushed_at"][:10] +
                             f" ({round(age)} days): treat as slow-moving; the generated code is vendored in app/, "
                             "so the app does not depend on new APX releases") if age > 90 else "active",
                 "license": "Databricks License (app/ is a separate sub-project; the engine never imports it)"})


class App:
    def __init__(self, url: str, token: str):
        self.url, self.token, self.calls = url.rstrip("/"), token, 0

    def req(self, method: str, path: str, body: dict | None = None, query: list | None = None):
        url = self.url + path + ("?" + urllib.parse.urlencode(query) if query else "")
        r = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                   headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        self.calls += 1
        with urllib.request.urlopen(r, timeout=240) as resp:
            return resp.status, json.loads(resp.read())


def token() -> str:
    """An OAuth access token: Databricks Apps refuse personal access tokens. LAKEMATCH_APP_CLIENT_ID / _SECRET name a
    service principal holding CAN_USE on the app (machine-to-machine, client credentials)."""
    import base64
    import configparser
    import os
    cp = configparser.ConfigParser()
    cp.read(Path.home() / ".databrickscfg")
    host = cp[PROFILE]["host"].rstrip("/")
    cid, secret = os.environ["LAKEMATCH_APP_CLIENT_ID"], os.environ["LAKEMATCH_APP_CLIENT_SECRET"]
    req = urllib.request.Request(f"{host}/oidc/v1/token", data=b"grant_type=client_credentials&scope=all-apis",
                                 headers={"Authorization": "Basic " + base64.b64encode(f"{cid}:{secret}".encode()).decode(),
                                          "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["access_token"]


def deployed(n: int) -> None:
    app = cli("apps", "get", APP)
    deadline = time.time() + 900
    while app["compute_status"]["state"] != "ACTIVE" or app["app_status"]["state"] != "RUNNING":
        if time.time() > deadline:
            raise TimeoutError(f"app not running after 15 min: {app['app_status']} {app['compute_status']}")
        if app["compute_status"]["state"] in ("STOPPED", "ERROR"):
            subprocess.run(["databricks", "apps", "start", APP, "--profile", PROFILE, "--no-wait"], capture_output=True)
        time.sleep(15)
        app = cli("apps", "get", APP)
    out: dict = {"name": app["name"], "url": app["url"], "app_status": app["app_status"]["state"],
                 "compute_status": app["compute_status"]["state"],
                 "resources": app.get("resources"), "service_principal": app.get("service_principal_name"),
                 "active_deployment": (app.get("active_deployment") or {}).get("deployment_id")}
    client = App(app["url"], token())
    try:
        _, session = client.req("GET", "/api/session")
        out["session"] = session
        _, nxt = client.req("GET", "/api/queue/next", query=[("n", n)])
        pairs = [(i["l_id"], i["r_id"], i["model_version"]) for i in nxt["items"]]
        rows = []
        for l, r, _ in pairs:
            _, row = client.req("POST", "/api/labels", {"l_id": l, "r_id": r, "decision": "unsure",
                                                       "reason": "deployment check (bench/app_deploy.py): unsure, "
                                                                 "never a training label; retracted next"})
            rows.append(row)
        _, stats = client.req("GET", "/api/stats")
        for l, r, _ in pairs:
            client.req("POST", "/api/labels/retract", {"l_id": l, "r_id": r, "reason": "deployment check cleanup"})
        out["labelled_via_http"] = len(rows)
        out["label_rows"] = rows
        out["stats"] = stats
        ids = ", ".join(f"'{x['label_id']}'" for x in rows)
        back = cli("experimental", "aitools", "tools", "query", "--warehouse", WAREHOUSE,
                   f"SELECT label_id, reviewer, labelled_at, model_version, reason FROM {SCHEMA}.lm_review_labels "
                   f"WHERE label_id IN ({ids})")
        out["rows_in_delta_table"] = back
        out["provenance_complete"] = len(rows) == n and all(
            all(x.get(k) for k in ("reviewer", "labelled_at", "model_version", "reason")) for x in rows)
        out["ok"] = True
    except Exception as e:                      # recorded, never silent
        out["ok"] = False
        out["error"] = f"{type(e).__name__}: {str(e)[:500]}"
    finally:
        subprocess.run(["databricks", "apps", "stop", APP, "--profile", PROFILE, "--no-wait"], capture_output=True)
        subprocess.run(["databricks", "warehouses", "stop", WAREHOUSE, "--profile", PROFILE, "--no-wait"],
                       capture_output=True)
        out["stopped_after"] = {"app": "stop requested", "warehouse": "stop requested"}
    out["http_calls"] = client.calls
    out["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    save("deployed", out)
    if not out["ok"]:
        sys.exit(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["apx", "deployed"])
    ap.add_argument("--labels", type=int, default=3)
    a = ap.parse_args()
    apx() if a.what == "apx" else deployed(a.labels)
    return 0


if __name__ == "__main__":
    sys.exit(main())
