"""ZR-8 scripted run: ask the Genie agent the ten reference questions and check each generated query's shape.

    python bench/genie_eval.py ask [--profile fourth-pat]       -> bench/results/genie.json  (questions_*)
    python bench/genie_eval.py app                              -> bench/results/genie.json  (app panel, local)
    python bench/genie_eval.py obo --profile <user oauth>       -> bench/results/genie.json  (deployed app, as a user)

ask   Through the Conversation API, as the profile's own user (paid_features.genie_auth_mode: user — Genie bills
      since July 2026 and only users get the free allowance). A question passes when Genie answered with a query that
      ran (status COMPLETED, a query attachment, no error), every expected table of genie/questions/<q>.yaml appears
      in it, every expected aggregate function is called, and every `mentions` regex matches. One fresh
      conversation per question; the generated SQL, the row count and the reason of any failure are recorded.
app   The app's Genie panel is gated by paid_features.genie: the app's own tests (app/tests/test_genie.py) run with
      the switch off and on; their outcome is recorded.
obo   The deployed app, called with a *user's* OAuth token (Databricks Apps forward it to the app as
      X-Forwarded-Access-Token, downscoped to the app's user_api_scopes): /api/genie/ask must answer as that user.
The warehouse is stopped at the end of `ask` and `obo`; the app is stopped at the end of `obo`.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "bench" / "results" / "genie.json"
SPACE = REPO / "bench" / "results" / "genie_space.json"
WAREHOUSE = "79dfcc5bc7019dd3"


def save(update: dict) -> dict:
    d = json.loads(OUT.read_text()) if OUT.exists() else {}
    d.update(update)
    OUT.write_text(json.dumps(d, indent=2, default=str) + "\n")
    return d


def check(sql: str, expected: dict) -> list[str]:
    """The reasons a generated query does not have the expected shape (empty = passes)."""
    low = sql.lower()
    used = set(re.findall(r"\b(lm_[a-z_]+)\b", low))
    bad = [f"table {t} not used" for t in expected.get("tables", []) if t.lower() not in used]
    bad += [f"no {a}()" for a in expected.get("aggregates", []) if not re.search(rf"\b{a}\s*\(", sql, re.I)]
    bad += [f"no /{m}/" for m in expected.get("mentions", []) if not re.search(m, sql, re.I)]
    return bad


def ask(profile: str) -> int:
    from databricks.sdk import WorkspaceClient
    from datetime import timedelta
    w = WorkspaceClient(profile=profile)
    space_id = json.loads(SPACE.read_text())["space_id"]
    me = w.current_user.me().user_name
    results = []
    try:
        for path in sorted((REPO / "genie" / "questions").glob("*.yaml")):
            q = yaml.safe_load(path.read_text())
            t0 = time.time()
            row: dict = {"id": q["id"], "question": q["question"], "expected": q["expected"]}
            try:
                msg = w.genie.start_conversation_and_wait(space_id, q["question"], timeout=timedelta(minutes=5))
                row["status"] = msg.status.value if msg.status else None
                att = next((a for a in (msg.attachments or []) if a.query), None)
                text = next((a.text.content for a in (msg.attachments or []) if a.text), None)
                row["text"] = text
                if msg.error:
                    row["error"] = str(msg.error.error)
                if att:
                    row["sql"] = att.query.query
                    row["description"] = att.query.description
                    try:
                        res = w.genie.get_message_attachment_query_result(space_id, msg.conversation_id, msg.id,
                                                                          att.attachment_id)
                        sr = res.statement_response
                        row["rows"] = (sr.manifest.total_row_count if sr and sr.manifest else None)
                        row["first_rows"] = ((sr.result.data_array or [])[:5] if sr and sr.result else [])
                    except Exception as e:                      # the query result is evidence, not the test
                        row["result_error"] = f"{type(e).__name__}: {str(e)[:200]}"
                reasons = [] if row["status"] == "COMPLETED" else [f"status {row['status']}"]
                reasons += ["no query attachment"] if not att else check(att.query.query, q["expected"])
                row["passed"], row["reasons"] = not reasons, reasons
                row["conversation_id"] = msg.conversation_id
            except Exception as e:
                row.update(passed=False, reasons=[f"{type(e).__name__}: {str(e)[:300]}"])
            row["seconds"] = round(time.time() - t0, 1)
            print(f"{'PASS' if row['passed'] else 'FAIL'} {q['id']} ({row['seconds']} s) {row.get('reasons')}",
                  flush=True)
            results.append(row)
    finally:
        w.warehouses.stop(WAREHOUSE)
    passed = sum(r["passed"] for r in results)
    save({"space_id": space_id, "asked_as": me, "auth_mode": "user (the profile's own user)",
          "questions_asked": len(results), "questions_passed": passed, "questions": results,
          "asked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
    print(f"{passed} / {len(results)} passed")
    return 0 if passed == len(results) else 1


def app() -> int:
    r = subprocess.run(["uv", "run", "--group", "dev", "pytest", "-q", "tests/test_genie.py", "-p", "no:cacheprovider"],
                       cwd=REPO / "app", capture_output=True, text=True)
    tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
    ok = r.returncode == 0
    save({"panel_hidden_when_off": ok, "panel_tests": {"command": "cd app && uv run pytest tests/test_genie.py",
                                                       "returncode": r.returncode, "tail": tail}})
    print(ok, tail)
    return 0 if ok else 1


def obo(profile: str, question: str) -> int:
    """Call the deployed app's /api/genie/ask as the user of `profile` (an OAuth U2M profile)."""
    def cli(*a):
        return json.loads(subprocess.run(["databricks", *a, "--profile", "fourth-pat", "-o", "json"],
                                         capture_output=True, text=True, check=True).stdout)
    out: dict = {}
    try:
        app_ = cli("apps", "get", "lakematch")
        deadline = time.time() + 900
        while app_["compute_status"]["state"] != "ACTIVE" or app_["app_status"]["state"] != "RUNNING":
            if time.time() > deadline:
                raise TimeoutError(f"app not running: {app_['app_status']} {app_['compute_status']}")
            if app_["compute_status"]["state"] in ("STOPPED", "ERROR"):
                subprocess.run(["databricks", "apps", "start", "lakematch", "--profile", "fourth-pat", "--no-wait"],
                               capture_output=True)
            time.sleep(15)
            app_ = cli("apps", "get", "lakematch")
        out["app_scopes"] = app_.get("effective_user_api_scopes")
        token = json.loads(subprocess.run(["databricks", "auth", "token", "--profile", profile], capture_output=True,
                                          text=True, check=True).stdout)["access_token"]

        def call(method, path, body=None):
            req = urllib.request.Request(app_["url"] + path, method=method,
                                         data=json.dumps(body).encode() if body is not None else None,
                                         headers={"Authorization": f"Bearer {token}",
                                                  "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=400) as resp:
                return json.loads(resp.read())
        out["config"] = call("GET", "/api/genie/config")
        t0 = time.time()
        ans = call("POST", "/api/genie/ask", {"question": question})
        out["answer"] = {k: ans.get(k) for k in ("asked_as", "status", "sql", "text", "columns", "rows", "error",
                                                 "conversation_id")}
        out["seconds"] = round(time.time() - t0, 1)
        out["ok"] = ans.get("status") == "COMPLETED" and bool(ans.get("asked_as")) and ans.get("auth") == "on_behalf_of_user"
        out["auth"] = ans.get("auth")
    except Exception as e:
        out["ok"] = False
        out["error"] = f"{type(e).__name__}: {str(e)[:500]}"
    finally:
        subprocess.run(["databricks", "apps", "stop", "lakematch", "--profile", "fourth-pat", "--no-wait"],
                       capture_output=True)
        subprocess.run(["databricks", "warehouses", "stop", WAREHOUSE, "--profile", "fourth-pat", "--no-wait"],
                       capture_output=True)
    out["at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    save({"app_obo": out})
    print(json.dumps(out, indent=1, default=str)[:3000])
    return 0 if out["ok"] else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["ask", "app", "obo"])
    ap.add_argument("--profile", default="fourth-pat")
    ap.add_argument("--question", default="How many links did the model make and what is their average match probability?")
    a = ap.parse_args()
    if a.what == "ask":
        return ask(a.profile)
    if a.what == "app":
        return app()
    return obo(a.profile, a.question)


if __name__ == "__main__":
    sys.exit(main())
