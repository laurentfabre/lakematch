"""Create or update the lakematch Genie agent from the versioned files in genie/ (ZR-8).

    python genie/space.py [--profile fourth-pat] [--grant user@example.com ...]

1. the evaluation table lm_eval_truth (the FEBRL4 truth file already on the volume) if missing;
2. comments.yaml -> COMMENT ON TABLE / COMMENT ON COLUMN in Unity Catalog (both work on the pipeline's materialized
   views, which refuse ALTER TABLE ... ALTER COLUMN);
3. the space: tables, column descriptions (the same comments), instructions.md as its text instruction,
   examples.yaml as example SQL, the ten reference questions as *benchmarks* only (the evaluation set never becomes
   context) and as sample questions in the UI; created through the API, updated in place on later runs (found by
   title); the space id lands in bench/results/genie_space.json;
4. --grant: the users who ask Genie as themselves (genie_auth_mode: user) get CAN_RUN on the space, CAN_USE on the
   warehouse, and SELECT on the tables (Genie runs their questions with their own rights).

Every SQL statement goes through the warehouse, which this script stops when it is done (shared with Alfred).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = REPO / "bench" / "results" / "genie_space.json"
WAREHOUSE = "79dfcc5bc7019dd3"
TRUTH = "/Volumes/workspace/lakematch/data/febrl4_seeded/truth.csv"


def hid(*parts: str) -> str:
    """A stable 32-hex id: the same file content gives the same id, so an update does not churn ids."""
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def load() -> dict:
    front, body = re.match(r"^---\n(.*?)\n---\n(.*)$", (HERE / "instructions.md").read_text(), re.S).groups()
    questions = [yaml.safe_load(p.read_text()) for p in sorted((HERE / "questions").glob("*.yaml"))]
    return {"meta": yaml.safe_load(front), "instructions": body.strip(),
            "comments": yaml.safe_load((HERE / "comments.yaml").read_text()),
            "examples": yaml.safe_load((HERE / "examples.yaml").read_text())["examples"], "questions": questions}


def serialized_space(spec: dict) -> dict:
    schema = spec["comments"]["schema"]
    tables = []
    for name, t in sorted(spec["comments"]["tables"].items()):
        cols = [{"column_name": c, "description": [d]} for c, d in sorted((t.get("columns") or {}).items())]
        entry = {"identifier": f"{schema}.{name}"}
        if cols:
            entry["column_configs"] = cols
        tables.append(entry)
    text = [line for line in spec["instructions"].splitlines()]
    payload = {
        "version": 2,
        "config": {"sample_questions": sorted(
            [{"id": hid("sample", q["id"]), "question": [q["question"]]} for q in spec["questions"]],
            key=lambda x: x["id"])},
        "data_sources": {"tables": tables},
        "instructions": {
            "text_instructions": [{"id": hid("instructions", str(spec["meta"]["version"])), "content": [
                "\n".join(text)]}],
            "example_question_sqls": sorted(
                [{"id": hid("example", e["question"]), "question": [e["question"]], "sql": [e["sql"].strip()]}
                 for e in spec["examples"]], key=lambda x: x["id"]),
        },
        "benchmarks": {"questions": sorted(
            [{"id": hid("benchmark", q["id"]), "question": [q["question"]],
              "answer": [{"format": "SQL", "content": [q["reference_sql"].strip()]}]} for q in spec["questions"]],
            key=lambda x: x["id"])},
    }
    return payload


def sql(w, statement: str) -> list:
    from databricks.sdk.service.sql import StatementState
    r = w.statement_execution.execute_statement(statement=statement, warehouse_id=WAREHOUSE, wait_timeout="50s")
    while r.status and r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(2)
        r = w.statement_execution.get_statement(r.statement_id)
    if not r.status or r.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"{statement[:120]}…: {r.status.error.message if r.status and r.status.error else r.status}")
    return (r.result.data_array if r.result else None) or []


def q(text: str) -> str:
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="fourth-pat")
    ap.add_argument("--grant", action="append", default=[], help="a user who asks Genie as themselves")
    args = ap.parse_args()
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient(profile=args.profile)
    spec = load()
    schema = spec["comments"]["schema"]
    out: dict = {"profile": args.profile, "instructions_version": spec["meta"]["version"],
                 "comments_version": spec["comments"]["version"], "questions": len(spec["questions"])}
    try:
        sql(w, f"CREATE TABLE IF NOT EXISTS {schema}.lm_eval_truth AS SELECT CAST(l_id AS STRING) AS l_id, "
               f"CAST(r_id AS STRING) AS r_id FROM read_files('{TRUTH}', format => 'csv', header => true)")
        out["eval_truth_rows"] = int(sql(w, f"SELECT COUNT(*) FROM {schema}.lm_eval_truth")[0][0])

        applied = []
        for name, t in spec["comments"]["tables"].items():
            fq = f"{schema}.{name}"
            sql(w, f"COMMENT ON TABLE {fq} IS {q(t['comment'])}")
            for col, text in (t.get("columns") or {}).items():
                sql(w, f"COMMENT ON COLUMN {fq}.{col} IS {q(text)}")
            applied.append({"table": fq, "columns": len(t.get("columns") or {})})
        out["comments_applied"] = applied

        payload = json.dumps(serialized_space(spec))
        title = spec["meta"]["space_title"]
        description = ("lakematch entity-resolution results (FEBRL4): links, entities, quality gate, review queue "
                       f"and labels. Built by genie/space.py from instructions v{spec['meta']['version']}.")
        existing = [s for s in (w.genie.list_spaces().spaces or []) if s.title == title]
        if existing:
            space = w.genie.update_space(existing[0].space_id, serialized_space=payload, title=title,
                                         description=description, warehouse_id=WAREHOUSE)
            out["action"] = "updated"
        else:
            space = w.genie.create_space(warehouse_id=WAREHOUSE, serialized_space=payload, title=title,
                                         description=description)
            out["action"] = "created"
        out["space_id"] = space.space_id
        out["title"] = title
        got = w.genie.get_space(space.space_id, include_serialized_space=True)
        ser = json.loads(got.serialized_space or "{}")
        out["space_check"] = {"tables": len(ser.get("data_sources", {}).get("tables", [])),
                              "benchmarks": len((ser.get("benchmarks") or {}).get("questions", [])),
                              "examples": len(ser.get("instructions", {}).get("example_question_sqls", [])),
                              "column_descriptions": sum(len(t.get("column_configs", []))
                                                         for t in ser.get("data_sources", {}).get("tables", []))}

        for user in args.grant:
            w.api_client.do("PATCH", f"/api/2.0/permissions/genie/{space.space_id}",
                            body={"access_control_list": [{"user_name": user, "permission_level": "CAN_RUN"}]})
            w.api_client.do("PATCH", f"/api/2.0/permissions/warehouses/{WAREHOUSE}",
                            body={"access_control_list": [{"user_name": user, "permission_level": "CAN_USE"}]})
            sql(w, f"GRANT USE CATALOG ON CATALOG workspace TO `{user}`")
            sql(w, f"GRANT USE SCHEMA, SELECT ON SCHEMA {schema} TO `{user}`")
        out["granted"] = args.grant
    finally:
        w.warehouses.stop(WAREHOUSE)
        out["warehouse"] = "stop requested"
    out["at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
