#!/usr/bin/env python3
"""ZR-6: the FEBRL4 benchmark on Databricks serverless (fourth-pat) against its laptop twin, the quality gate on seeded
bad rows, both deployment profiles, and the Photon report. -> bench/results/serverless.json, bench/PHOTON.md

    python bench/serverless.py all          # prepare -> laptop -> upload -> deploy+run default -> deploy+run free
                                            # -> report; ~40 min; stops the warehouse at the end
    python bench/serverless.py prepare|laptop|upload|run <config_file>|report

Data: FEBRL4 with half the partners removed (data/febrl4, public) plus SEEDED bad rows on both sides — no id, an id
that breaks the rec-<n>-org / rec-<n>-dup-<k> rule, and an id used twice — which the gate must quarantine, exactly
those and nothing else (data/febrl4_seeded/seeded_bad_rows.json). The seeded rows are not in the truth set, so they
change no metric when they are quarantined.

Laptop twin: examples/febrl4_databricks_free.yaml with profile laptop, the native gate and local paths, run by
pipeline.run() in one process; the Databricks run is the bundle's job (plan, pipeline, train, pipeline, cluster).
F1 delta = Databricks pairwise F1 (cluster task) - laptop pairwise F1 (run_summary), on the same seeded inputs.

Photon: query history (`databricks query-history list --include-metrics`) gives task time and Photon time for every
statement: a pipeline dataset is its `REFRESH MATERIALIZED VIEW` row, a job task the rows tagged with its task run id.
The query profile's operator tree is not in the public API (plans_state EXISTS, no endpoint returns it), so the
operators that fell back come from each stage's formatted physical plan on serverless (the explain task), the same
plan the profile renders: a plan node whose name does not start with Photon ran outside Photon.
"""
from __future__ import annotations

import csv
import datetime
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from redact import redact  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROFILE = "fourth-pat"
WAREHOUSE = "79dfcc5bc7019dd3"
VOL_DATA = "/Volumes/workspace/lakematch/data/febrl4_seeded"
VOL_RUNS = "/Volumes/workspace/lakematch/runs/febrl4"
LOCAL = ROOT / "data" / "febrl4_seeded"
OUT = ROOT / "data" / "runs" / "serverless"
RESULTS = ROOT / "bench" / "results" / "serverless.json"
PHOTON = ROOT / "bench" / "PHOTON.md"
CONFIGS = ("febrl4_databricks.yaml", "febrl4_databricks_free.yaml")
PIPELINE_STAGES = {"gate": ["lm_left_valid", "lm_right_valid", "lm_left_quarantine", "lm_right_quarantine"],
                   "entity": ["lm_left_entity", "lm_right_entity"], "candidates": ["lm_candidates"],
                   "features": ["lm_features"], "scores": ["lm_scores"], "links": ["lm_links"]}
JOB_STAGES = ("plan", "train", "cluster")

FIELDS = ["rec_id", "given_name", "surname", "street_number", "address_1", "address_2", "suburb", "postcode", "state",
          "date_of_birth", "soc_sec_id"]
SEEDS = {
    "left": [["", "zoe", "seeded", "1", "no id street", "", "nowhere", "2000", "nsw", "19800101", "1000001"],
             ["REC_BAD_1", "yann", "seeded", "2", "bad id street", "", "nowhere", "2000", "vic", "19800202", "1000002"],
             ["rec-90001-org", "ada", "twice", "3", "twin street", "", "nowhere", "2000", "qld", "19800303", "1000003"],
             ["rec-90001-org", "ada", "twice", "4", "twin street", "", "nowhere", "2000", "qld", "19800303", "1000004"]],
    "right": [["x-77", "bob", "seeded", "5", "bad id road", "", "nowhere", "3000", "wa", "19700505", "2000005"],
              ["", "cy", "seeded", "6", "no id road", "", "nowhere", "3000", "sa", "19700606", "2000006"]],
}


def sh(*cmd, check=True, capture=True, timeout=None) -> str:
    r = subprocess.run(list(cmd), capture_output=capture, text=True, timeout=timeout)
    if check and r.returncode:
        raise RuntimeError(f"{' '.join(cmd)} -> {r.returncode}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r.stdout


def dbx(*args, **kw) -> str:
    return sh("databricks", *args, "--profile", PROFILE, **kw)


# --- data ----------------------------------------------------------------------------------------------------------
def prepare() -> dict:
    LOCAL.mkdir(parents=True, exist_ok=True)
    src = ROOT / "data" / "febrl4"
    if not (src / "left.csv").exists():
        raise SystemExit("data/febrl4 is missing: python bench/prepare_febrl4.py")
    seeded = {}
    for side in ("left", "right"):
        rows = list(csv.reader(open(src / f"{side}.csv", newline="")))
        assert rows[0] == FIELDS, rows[0]
        with open(LOCAL / f"{side}.csv", "w", newline="") as fh:
            csv.writer(fh).writerows(rows + SEEDS[side])
        # as Spark reads them: CSV '' is null
        seeded[side] = [{k: (v if v != "" else None) for k, v in zip(FIELDS, r)} for r in SEEDS[side]]
    shutil.copy(src / "truth.csv", LOCAL / "truth.csv")
    (LOCAL / "seeded_bad_rows.json").write_text(json.dumps(seeded, indent=2) + "\n")
    return {s: len(v) for s, v in seeded.items()}


def laptop() -> dict:
    """The laptop twin: the free Databricks config, profile laptop, native gate, local paths, one process."""
    import yaml
    from lakematch.config import build
    from lakematch.pipeline import run
    user = yaml.safe_load((ROOT / "examples" / "febrl4_databricks_free.yaml").read_text())
    user.update(profile="laptop", runtime={"mode": "local"}, quality={**user["quality"], "engine": "native"},
                storage={"root": str(OUT / "laptop"), "catalog": None}, paid_features={},
                inputs={s: {"path": str(LOCAL / f"{s}.csv"), "id": "rec_id"} for s in ("left", "right")},
                mlflow={"model_name": user["mlflow"]["model_name"], "tracking_uri": f"sqlite:///{OUT / 'laptop' / 'mlflow.db'}",
                        "pointer": str(OUT / "laptop" / "models" / "current.json")})
    user["evaluation"]["truth"]["path"] = str(LOCAL / "truth.csv")
    shutil.rmtree(OUT / "laptop", ignore_errors=True)
    t0 = time.time()
    summary = run(build(user, ROOT))
    summary["wall_s"] = round(time.time() - t0, 1)
    (OUT / "laptop_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    return summary


def upload() -> None:
    for vol in ("data", "runs"):
        if vol not in dbx("volumes", "list", "workspace", "lakematch", "-o", "json"):
            dbx("volumes", "create", "workspace", "lakematch", vol, "MANAGED")
    dbx("fs", "mkdir", f"dbfs:{VOL_DATA}")
    for f in ("left.csv", "right.csv", "truth.csv", "seeded_bad_rows.json"):
        dbx("fs", "cp", "--overwrite", str(LOCAL / f), f"dbfs:{VOL_DATA}/{f}")


# --- deploy and run ------------------------------------------------------------------------------------------------
def _config(config_file: str) -> dict:
    import yaml
    return yaml.safe_load((ROOT / "examples" / config_file).read_text())


def deploy(config_file: str) -> dict:
    from lakematch.config import load
    cfg = load(ROOT / "examples" / config_file)
    target = "PERFORMANCE_OPTIMIZED" if cfg.get("paid_features.serverless_performance_mode") else "STANDARD"
    var = ["--var", f"config_file={config_file}", "--var", f"performance_target={target}"]
    t0 = time.time()
    sh("databricks", "bundle", "validate", "--strict", "-t", "serverless", *var, timeout=600)
    sh("databricks", "bundle", "deploy", "-t", "serverless", *var, timeout=900)
    summary = json.loads(sh("databricks", "bundle", "summary", "-t", "serverless", *var, "-o", "json"))
    job_id = summary["resources"]["jobs"]["lakematch_run"]["id"]
    pipeline_id = summary["resources"]["pipelines"]["lakematch_pipeline"]["id"]
    return {"config_file": config_file, "paid_features_enabled": cfg.enabled_paid_features(),
            "performance_target": target, "deploy_s": round(time.time() - t0, 1), "job_id": job_id,
            "pipeline_id": pipeline_id}


def run_job(job_id: str) -> dict:
    t0 = int(time.time() * 1000)
    raw = dbx("jobs", "run-now", str(job_id), "--timeout", "90m", "-o", "json", check=False, timeout=96 * 60)
    try:
        run = json.loads(raw)
    except json.JSONDecodeError:
        runs = json.loads(dbx("jobs", "list-runs", "--job-id", str(job_id), "--limit", "1", "-o", "json"))
        run = json.loads(dbx("jobs", "get-run", str(runs[0]["run_id"]), "-o", "json"))
    tasks = {t["task_key"]: {"run_id": t["run_id"], "state": t["state"].get("result_state"),
                             "message": t["state"].get("state_message", "")[:300],
                             "seconds": round((t.get("end_time", 0) - t.get("start_time", 0)) / 1000, 1)}
             for t in run.get("tasks", [])}
    return {"run_id": run["run_id"], "result": run["state"].get("result_state"), "url": run.get("run_page_url"),
            "start_ms": t0, "end_ms": int(time.time() * 1000), "tasks": tasks}


def fetch(tag: str) -> dict:
    """The task JSONs the job wrote under storage.root, and the explain plans."""
    dest = OUT / tag
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    dbx("fs", "cp", "-r", "--overwrite", f"dbfs:{VOL_RUNS}/tasks", str(dest / "tasks"), check=False)
    dbx("fs", "cp", "-r", "--overwrite", f"dbfs:{VOL_RUNS}/explain", str(dest / "explain"), check=False)
    return {p.stem: json.loads(p.read_text()) for p in sorted((dest / "tasks").glob("*.json"))}


# --- Photon --------------------------------------------------------------------------------------------------------
def query_metrics(start_ms: int, end_ms: int, task_runs: dict[str, int]) -> dict:
    rows, token = [], None
    while True:
        args = ["query-history", "list", "--include-metrics", "--max-results", "1000", "-o", "json"]
        if token:
            args += ["--page-token", token]
        page = json.loads(dbx(*args))
        res = page.get("res", []) if isinstance(page, dict) else page
        rows += res
        token = page.get("next_page_token") if isinstance(page, dict) else None
        oldest = min((r.get("query_start_time_ms", 0) for r in res), default=0)
        if not token or oldest < start_ms:
            break
    rows = [r for r in rows if start_ms <= r.get("query_start_time_ms", 0) <= end_ms]
    by_task = {str(v): k for k, v in task_runs.items()}
    stages: dict[str, dict] = {}

    def add(stage, r):
        m = r.get("metrics") or {}
        s = stages.setdefault(stage, {"statements": 0, "task_ms": 0, "photon_ms": 0})
        s["statements"] += 1
        s["task_ms"] += m.get("task_total_time_ms") or 0
        s["photon_ms"] += m.get("photon_total_time_ms") or 0
    for r in rows:
        text = r.get("query_text") or ""
        m = re.match(r"REFRESH MATERIALIZED VIEW \S*?\.?(lm_\w+)", text)
        if m:
            stage = next((st for st, ts in PIPELINE_STAGES.items() if m.group(1) in ts), None)
            if stage:
                add(stage, r)
            continue
        job = (r.get("query_source") or {}).get("job_info") or {}
        task = by_task.get(str(job.get("job_task_run_id")))
        if task:
            add(f"task:{task}", r)
    for s in stages.values():
        s["photon_share"] = round(s["photon_ms"] / s["task_ms"], 3) if s["task_ms"] else None
    return stages


NON_OPERATORS = {"AdaptiveSparkPlan", "ResultQueryStage", "ShuffleQueryStage", "BroadcastQueryStage",
                 "TableCacheQueryStage", "ReusedExchange", "Subquery", "SubqueryBroadcast", "AQEShuffleRead",
                 "InMemoryRelation", "LocalTableScan", "ColumnarToRow", "RowToColumnar"}   # transitions, not work


def plan_operators(text: str) -> dict:
    """Operators of a formatted physical plan: `(n) Name` headings. Photon* = Photon; anything else outside the
    AQE wrappers fell back (ColumnarToRow / RowToColumnar are the transitions that a fallback forces)."""
    ops = re.findall(r"^\((\d+)\) ([A-Za-z][A-Za-z0-9]*)", text, re.M)
    names = [n for _, n in ops]
    photon = sorted({n for n in names if n.startswith("Photon")})
    fell = sorted({n for n in names if not n.startswith("Photon") and n not in NON_OPERATORS})
    expl = text.split("== Photon Explanation ==", 1)[1].split("== Optimizer", 1)[0].strip() \
        if "== Photon Explanation ==" in text else None
    unsupported = sorted(set(re.findall(r"The expression `(\w+)`", expl or "")))
    if expl and "Casting from StructType" in expl:
        unsupported.append("cast(struct -> struct with collations)")
    return {"operators": len(names), "photon": photon, "fell_back": fell, "unsupported_expressions": unsupported,
            "fully_supported": bool(expl and "fully supported by Photon" in expl)}


# --- report --------------------------------------------------------------------------------------------------------
def stop_warehouse() -> str:
    dbx("warehouses", "stop", WAREHOUSE, "--no-wait", check=False)
    state = json.loads(dbx("warehouses", "get", WAREHOUSE, "-o", "json"))["state"]
    return state


def report(results: dict) -> None:
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(redact(json.dumps(results, indent=2, default=str)) + "\n")
    free = results["runs"].get("febrl4_databricks_free.yaml", {})
    lines = ["# Photon on serverless — lakematch FEBRL4 (ZR-6)", "",
             f"Measured {results['generated']} on fourth-pat (Free Edition, serverless, Spark "
             f"{free.get('spark', '?')}) by `python bench/serverless.py all`; the run with every paid feature off.",
             "Share = Photon time / task time, summed over the stage's statements in query history (the numbers the "
             "query profile shows). Fell back = the stage's physical-plan operators that are not Photon operators "
             "(formatted plan of the same stage on the same compute; the profile's operator tree has no public API).",
             "", "| Stage | Where | Statements | Task time (s) | Photon time (s) | Photon share | Operators that fell back |",
             "|---|---|---:|---:|---:|---:|---|"]
    metrics, plans = free.get("photon", {}), free.get("plans", {})
    for stage in [*PIPELINE_STAGES, *(f"task:{t}" for t in JOB_STAGES)]:
        m = metrics.get(stage, {})
        name = stage.replace("task:", "")
        where = "job task" if stage.startswith("task:") else "pipeline"
        pl = plans.get(name, {})
        fb, why = pl.get("fell_back"), pl.get("unsupported_expressions") or []
        fb_txt = ", ".join(f"`{x}`" for x in fb) if fb else ("none" if fb is not None else "— (MLlib / driver work)")
        if why:
            fb_txt += " — unsupported: " + ", ".join(f"`{w}`" for w in why)
        share = "—" if m.get("photon_share") is None else f"{m['photon_share']:.0%}"
        lines.append(f"| {name} | {where} | {m.get('statements', 0)} | {m.get('task_ms', 0) / 1000:.1f} | "
                     f"{m.get('photon_ms', 0) / 1000:.1f} | {share} | {fb_txt} |")
    lines += ["", "Notes", ""]
    lines += ["- Training (MLlib `fit`) runs in the train task; Photon accelerates DataFrame work only, never MLlib.",
              "- Scoring inside the pipeline is a compiled Spark SQL expression (src/lakematch/scoring_sql.py), not "
              "MLlib: a serverless pipeline crashes when `pyspark.ml` or MLflow is imported in it.", ""]
    PHOTON.write_text("\n".join(lines))


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "all"
    if cmd == "prepare":
        print(prepare()); return 0
    if cmd == "laptop":
        print(json.dumps(laptop()["evaluation"], indent=2)); return 0
    if cmd == "upload":
        upload(); return 0
    if cmd != "all":
        raise SystemExit(__doc__)
    results = {"generated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "runs": {}}
    results["seeded"] = prepare()
    lap = laptop()
    results["laptop"] = {"f1": lap["evaluation"]["all"]["f1"], "evaluation": lap["evaluation"],
                         "quarantined": lap["quarantined"], "wall_s": lap["wall_s"]}
    upload()
    for config_file in CONFIGS:
        rec = deploy(config_file)
        rec["job"] = run_job(rec["job_id"])
        rec["tasks"] = fetch(config_file.removesuffix(".yaml"))
        rec["ok"] = rec["job"]["result"] == "SUCCESS"
        cl = rec["tasks"].get("cluster", {})
        rec["f1"] = (cl.get("evaluation") or {}).get("all", {}).get("f1")
        rec["spark"] = (cl.get("runtime") or {}).get("spark")
        rec["photon"] = query_metrics(rec["job"]["start_ms"], rec["job"]["end_ms"] + 120_000,
                                      {t: v["run_id"] for t, v in rec["job"]["tasks"].items()})
        rec["plans"] = {p.stem: plan_operators(p.read_text())
                        for p in sorted((OUT / config_file.removesuffix(".yaml") / "explain").glob("*.txt"))}
        results["runs"][config_file] = rec
    default, free = (results["runs"][c] for c in CONFIGS)
    q = free["tasks"].get("quality", {})
    results.update({
        "febrl4_f1_laptop": results["laptop"]["f1"], "febrl4_f1_serverless": free["f1"],
        "febrl4_f1_delta_vs_laptop": round(free["f1"] - results["laptop"]["f1"], 4) if free["f1"] is not None else None,
        "dqx_quarantine_ok": bool(q.get("dqx_quarantine_ok")), "native_same_split": bool(q.get("native_same_split")),
        "all_paid_off_ran": free["ok"] and not free["paid_features_enabled"],
        "default_profile_deployed": bool(default.get("job_id")) and sorted(default["paid_features_enabled"]) == ["app", "genie"],
        "default_profile_ran": default["ok"],
        "predictive_optimization": (free["tasks"].get("plan") or {}).get("schema"),
    })
    results["warehouse_after"] = stop_warehouse()
    report(results)
    print(json.dumps({k: v for k, v in results.items() if k not in ("runs", "laptop")}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
