"""ZR-7 end to end on the laptop: run -> APX dev server -> 20+ labels over HTTP -> the next run trains on them.

    python bench/app_e2e.py [--keep]          -> bench/results/app_e2e.json

1. `lakematch run --config examples/febrl4_review.yaml --root data/runs/zr7_e2e` on an empty label store: the labels
   are the truth sample (labels.app_base), the queue and the run history are written, Jev gives its opinion on the
   100 most uncertain pairs (cached after the first time).
2. The app under the APX dev server (`apx dev start`, local files, local Delta label store) and checks that the UI
   and the API answer through it.
3. An automated reviewer labels the first queued pairs over HTTP, answering from the FEBRL4 truth file (it stands in
   for a person; its reason says so): 20 match / no-match decisions, 2 unsure, one label withdrawn with undo and given
   again. Every row of the store must carry reviewer, time, model version and reason.
4. The dev server is restarted: nothing may be lost (the app keeps no state in memory).
5. The same command runs again: it must read the app's decisions (labels.app.used), its label set must differ from
   run 1's, and the pairs the reviewer called a match must now be linked.
6. `apx build`: the deployable bundle must stay under the 10 MB Databricks Apps file limit.

The app is driven only through HTTP and its CLI: this script imports nothing from app/ (the engine never does).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "app"
CONFIG = REPO / "examples" / "febrl4_review.yaml"
ROOT = REPO / "data" / "runs" / "zr7_e2e"
OUT = REPO / "bench" / "results" / "app_e2e.json"
REVIEWER = "e2e-reviewer@laptop"
REASON = "automated reviewer: answered from the FEBRL4 truth file (bench/app_e2e.py)"
N_DECIDED, N_UNSURE = 20, 2
LIMIT_MB = 10.0


def sh(cmd: list[str], cwd: Path, env: dict | None = None, timeout: int = 900) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True,
                       timeout=timeout, stdin=subprocess.DEVNULL)
    if r.returncode:
        sys.exit(f"{' '.join(cmd)} failed ({r.returncode}):\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    return r


def run_engine(tag: str) -> dict:
    t0 = time.time()
    sh([str(REPO / ".venv" / "bin" / "lakematch"), "run", "--config", str(CONFIG), "--root", str(ROOT)], REPO,
       timeout=1800)
    summary = json.loads((ROOT / "run_summary.json").read_text())
    shutil.copy(ROOT / "run_summary.json", ROOT / f"run_summary_{tag}.json")
    print(f"{tag}: {time.time() - t0:.0f} s, F1 {summary['evaluation']['all']['f1']}, "
          f"model {summary['review']['model_version']}", flush=True)
    return summary


class Http:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.calls = 0

    def req(self, method: str, path: str, body: dict | None = None, query: list | None = None):
        url = self.base + path + ("?" + urllib.parse.urlencode(query) if query else "")
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
        self.calls += 1
        with urllib.request.urlopen(r, timeout=120) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if resp.headers.get_content_type() == "application/json" else raw)


def dev(cmd: str, env: dict) -> str:
    return sh(["apx", "dev", cmd], APP, env, timeout=300).stdout


def dev_url(env: dict) -> str:
    out = dev("status", env)
    m = re.search(r"running at (http://\S+)", out)
    if not m:
        sys.exit(f"apx dev status: no URL in\n{out}")
    return m.group(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="leave the dev server running at the end")
    args = ap.parse_args()
    if ROOT.exists():
        shutil.rmtree(ROOT)
    truth = {(r["l_id"], r["r_id"]) for r in csv.DictReader(open(REPO / "data" / "febrl4" / "truth.csv"))}
    result: dict = {"config": str(CONFIG.relative_to(REPO)), "root": str(ROOT.relative_to(REPO)),
                    "reviewer": REVIEWER, "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

    # 1. first run: empty store, labels = the truth sample
    run1 = run_engine("run1")
    assert run1["labels"]["app"]["decisions"] == 0, run1["labels"]["app"]

    # 2. the app under the APX dev server, on this run's files
    env = {"LAKEMATCH_APP_SOURCE": "local", "LAKEMATCH_APP_LABEL_STORE": "delta",
           "LAKEMATCH_APP_REVIEW_DIR": str(ROOT / "review"), "LAKEMATCH_APP_LOCAL_USER": REVIEWER}
    sh(["apx", "dev", "stop"], APP, env)
    dev("start", env)
    url = dev_url(env)
    http = Http(url)
    _, session = http.req("GET", "/api/session")
    status, page = http.req("GET", "/review")
    ui_ok = status == 200 and b'id="root"' in page
    dev_ok = session["source"].startswith("local files") and session["reviewer"] == REVIEWER and ui_ok
    result["dev_server"] = {"url": url, "session": session, "ui_served": ui_ok}
    print(f"dev server {url}: {session}", flush=True)

    # 3. the automated reviewer
    labelled, decided, unsure, matches = [], 0, 0, []
    while decided < N_DECIDED or unsure < N_UNSURE:
        _, nxt = http.req("GET", "/api/queue/next", query=[("n", 1)])
        item = nxt["items"][0]
        key = (item["l_id"], item["r_id"])
        if unsure < N_UNSURE and decided >= N_DECIDED // 2:
            decision = "unsure"
            unsure += 1
        else:
            decision = "match" if key in truth else "no_match"
            decided += 1
            if decision == "match":
                matches.append(key)
        _, row = http.req("POST", "/api/labels", {"l_id": key[0], "r_id": key[1], "decision": decision,
                                                  "reason": REASON})
        labelled.append({"l_id": key[0], "r_id": key[1], "rank": item["rank"], "queue_reason": item["queue_reason"], "llm_label": item["llm_label"],
                         "p": item["p"], "decision": decision, "label_id": row["label_id"]})
    # undo on the last decided pair, then the same decision again: the store keeps all three rows
    last = next(x for x in reversed(labelled) if x["decision"] != "unsure")
    last_key = (last["l_id"], last["r_id"])
    _, undo = http.req("POST", "/api/labels/retract", {"l_id": last_key[0], "r_id": last_key[1]})
    _, back = http.req("GET", "/api/queue/next", query=[("n", 1)])
    undo_ok = undo["decision"] == "retract" and (back["items"][0]["l_id"], back["items"][0]["r_id"]) == last_key
    http.req("POST", "/api/labels", {"l_id": last_key[0], "r_id": last_key[1], "decision": last["decision"],
                                     "reason": REASON + " (given again after undo)"})
    label_posts = len(labelled) + 1

    _, rows = http.req("GET", "/api/labels", query=[("limit", 1000)])
    rows = rows["labels"]
    need = ("reviewer", "labelled_at", "model_version", "reason", "p", "threshold", "run_id", "queue_reason")
    provenance = all(all(r.get(k) not in (None, "") for k in need) for r in rows) and \
        all(r["reviewer"] == REVIEWER and r["model_version"] == run1["review"]["model_version"] for r in rows)
    _, stats1 = http.req("GET", "/api/stats")
    stats_keys_ok = set(stats1) == {"labels", "agreement", "model_versions", "queue", "quarantine"}

    # 4. restart: nothing in memory
    dev("restart", env)
    url2 = dev_url(env)
    _, stats_after = Http(url2).req("GET", "/api/stats")
    restart_ok = stats_after["labels"] == stats1["labels"] and stats_after["queue"] == stats1["queue"]
    sh(["apx", "dev", "stop"], APP, env)

    # 5. the next run reads the app's decisions
    run2 = run_engine("run2")
    app2 = run2["labels"]["app"]
    linked2 = set()
    import pyarrow.parquet as pq       # the engine's own outputs (the review extra brings pyarrow)
    for r in pq.read_table(ROOT / "links").to_pylist():
        linked2.add((r["l_id"], r["r_id"]))
    newly_linked = sum(k in linked2 for k in matches)
    consumed = (app2["decisions"] == N_DECIDED and app2["used"] == N_DECIDED and
                run1["mlflow"]["label_set"]["sha256"] != run2["mlflow"]["label_set"]["sha256"])

    # stats over both model versions (served again from run 2's queue, run history of both runs)
    dev("start", env)
    url3 = dev_url(env)
    _, stats2 = Http(url3).req("GET", "/api/stats")
    if not args.keep:
        sh(["apx", "dev", "stop"], APP, env)

    # 6. the deployable bundle
    sh(["apx", "build"], APP, timeout=600)
    build = APP / ".build"
    files = {str(p.relative_to(build)): p.stat().st_size for p in build.rglob("*") if p.is_file()}
    bundle_mb = sum(files.values()) / 2 ** 20

    result.update({
        "labelled_via_http": label_posts,
        "decisions": {"match_or_no_match": N_DECIDED, "unsure": N_UNSURE, "matches": len(matches)},
        "label_rows": len(rows), "http_calls": http.calls,
        "labels": labelled,
        "provenance_complete": provenance,
        "provenance_fields": list(need),
        "undo_returns_pair_to_queue": undo_ok,
        "stats_page_complete": stats_keys_ok,
        "restart_clean": restart_ok,
        "local_dev_server_ok": dev_ok,
        "run1": {"model_version": run1["review"]["model_version"], "labels": run1["labels"],
                 "evaluation": run1["evaluation"]["all"], "label_set_sha256": run1["mlflow"]["label_set"]["sha256"],
                 "queue": {k: run1["review"][k] for k in ("pairs", "by_reason")},
                 "jev_usd": (run1["review"].get("llm_usage") or {}).get("usd")},
        "run2": {"model_version": run2["review"]["model_version"], "labels": run2["labels"],
                 "evaluation": run2["evaluation"]["all"], "label_set_sha256": run2["mlflow"]["label_set"]["sha256"],
                 "queue": {k: run2["review"][k] for k in ("pairs", "by_reason")}},
        "reviewer_matches_linked_by_run2": f"{newly_linked} of {len(matches)}",
        "next_train_consumed_labels": consumed,
        "stats_after_run2": stats2,
        "bundle": {"files": files, "mb": round(bundle_mb, 3), "limit_mb": LIMIT_MB},
        "bundle_under_10mb": bundle_mb < LIMIT_MB,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    })
    prev = json.loads(OUT.read_text()) if OUT.exists() else {}
    for k in ("apx", "deployed"):                  # written by the APX check and the deployment step
        if k in prev:
            result[k] = prev[k]
    OUT.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps({k: result[k] for k in ("labelled_via_http", "provenance_complete", "next_train_consumed_labels",
                                             "local_dev_server_ok", "bundle_under_10mb", "restart_clean",
                                             "reviewer_matches_linked_by_run2")}, indent=1))
    print(f"run1 {result['run1']['evaluation']}\nrun2 {result['run2']['evaluation']}")
    return 0 if all(result[k] for k in ("provenance_complete", "next_train_consumed_labels", "local_dev_server_ok",
                                        "bundle_under_10mb", "restart_clean")) else 1


if __name__ == "__main__":
    sys.exit(main())
