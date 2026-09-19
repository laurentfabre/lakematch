#!/usr/bin/env python3
"""bench_febrl.py — the COMPLETE system (Zingg on Spark 4.1 + Jev) on FEBRL4, scored against ground truth.

FEBRL4 (recordlinkage toolkit): 5 000 person records, 5 000 corrupted duplicates, one true link each. Zingg does
everything it does in production — findTrainingData (active learning), train (blocking tree + classifier), link —
and only the LABELLER changes:

    jev     mdm_jev.py prelabel: Jev labels the obvious pairs, the rest stay unlabelled (no human in the loop)
    truth   every proposed pair labelled from the ground truth: a tireless, perfect human
    jev+h   Jev first, then the ground truth on exactly the pairs Jev deferred: Jev + a human on the hard ones

    source ../zingg_env.sh
    $ZINGG_VENV/bin/python bench_febrl.py prepare
    $ZINGG_VENV/bin/python bench_febrl.py run --labeller jev --rounds 6
    $ZINGG_VENV/bin/python bench_febrl.py score            # every run found under work/

Run with the venv's Python (recordlinkage, duckdb); Zingg itself runs through scripts/zingg.sh.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE / "work" / "febrl4"
FIELDS = ["given_name", "surname", "street_number", "address_1", "address_2", "suburb", "postcode", "state",
          "date_of_birth", "soc_sec_id"]
EXACT = {"postcode", "state"}
SYSTEM_PY = "/opt/homebrew/bin/python3"          # mdm_jev.py runs where typesafe_sdk lives


def prepare(_args) -> int:
    from recordlinkage.datasets import load_febrl4

    WORK.mkdir(parents=True, exist_ok=True)
    a, b = load_febrl4()
    if UNMATCHED:                                     # same removal as bench_pipeline.py --unmatched (seed 23)
        import numpy as np
        _, _, links = load_febrl4(return_links=True)
        partners = sorted(y for _, y in links)
        gone = set(np.random.default_rng(23).choice(partners, size=int(len(partners) * UNMATCHED), replace=False))
        b = b.drop(index=list(gone))
        (WORK / "true_links.txt").write_text(str(len(partners) - len(gone)))
    for name, frame in (("a", a), ("b", b)):
        frame = frame.reset_index().fillna("")
        frame[["rec_id"] + FIELDS].to_csv(WORK / f"{name}.csv", index=False, header=True)
    print(f"wrote {len(a)} + {len(b)} records under {WORK}")
    return 0


DROP: set[str] = set()
UNMATCHED = 0.0


def config(tag: str) -> Path:
    schema = ", ".join(f"{c} string" for c in ["rec_id"] + FIELDS)
    pipe = lambda n: {"name": n, "format": "csv", "schema": schema,  # noqa: E731
                      "props": {"path": str(WORK / f"{n}.csv"), "delimiter": ",", "header": True}}
    conf = {
        "fieldDefinition": [{"fieldName": "rec_id", "fields": "rec_id", "dataType": "string", "matchType": "dont_use"}] + [
            {"fieldName": f, "fields": f, "dataType": "string", "matchType": "dont_use" if f in DROP else "exact" if f in EXACT else "fuzzy"} for f in FIELDS],
        "data": [pipe("a"), pipe("b")],
        "output": [{"name": "out", "format": "parquet", "props": {"path": str(WORK / tag / "out")}}],
        "labelDataSampleSize": 0.1, "numPartitions": 8, "modelId": 1, "zinggDir": str(WORK / tag / "models"),
    }
    path = WORK / tag / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(conf, indent=1))
    return path


def zingg(phase: str, conf: Path, log: Path) -> float:
    home, t0 = os.environ["ZINGG_HOME"], time.time()
    with log.open("w") as fh:
        rc = subprocess.run(["bash", "scripts/zingg.sh", "--phase", phase, "--conf", str(conf)], cwd=home,
                            stdout=fh, stderr=subprocess.STDOUT).returncode
    if rc:
        raise SystemExit(f"zingg {phase} failed, see {log}")
    return time.time() - t0


def entity_of(rec_id: str) -> str:
    return rec_id.split("-")[1]


def label_truth(model: Path, only_deferred: bool) -> tuple[int, int]:
    """Write ground-truth labels for the unlabelled pairs (all of them, or only those Jev has judged and deferred)."""
    import duckdb

    con = duckdb.connect()
    un = f"read_parquet('{model}/trainingData/unmarked/*.parquet', union_by_name = true)"
    marked = list((model / "trainingData" / "marked").glob("*.parquet"))
    done = f"SELECT z_cluster FROM read_parquet({[str(m) for m in marked]}, union_by_name = true)" if marked else "SELECT NULL WHERE false"
    rows = con.execute(f"SELECT z_cluster, z_zid, rec_id FROM {un} WHERE z_cluster NOT IN ({done}) ORDER BY 1, 2").fetchall()
    pairs: dict[str, list[str]] = {}
    for cluster, _, rec in rows:
        pairs.setdefault(cluster, []).append(rec)
    labels = {c: int(entity_of(r[0]) == entity_of(r[1])) for c, r in pairs.items() if len(r) == 2}
    if only_deferred:
        judged = set()
        for path in (model / "jev").glob("prelabel_*.json"):
            judged |= {p["z_cluster"] for p in json.loads(path.read_text())["pairs"] if "error" not in p}
        labels = {c: y for c, y in labels.items() if c in judged}
    if not labels:
        return 0, 0
    con.execute("CREATE TABLE l (z_cluster VARCHAR, y INTEGER)")
    con.executemany("INSERT INTO l VALUES (?, ?)", list(labels.items()))
    out = model / "trainingData" / "marked" / f"part-truth-{int(time.time() * 1000)}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY (SELECT u.* REPLACE (l.y AS z_isMatch) FROM {un} u JOIN l USING (z_cluster) "
                f"QUALIFY row_number() OVER (PARTITION BY u.z_cluster, u.z_zid ORDER BY 1) = 1) "
                f"TO '{out}' (FORMAT parquet, COMPRESSION snappy)")
    return sum(labels.values()), len(labels) - sum(labels.values())


def label_jev(model: Path, tau: float) -> str:
    out = subprocess.run([SYSTEM_PY, str(HERE.parent / "mdm_jev.py"), "prelabel", "--entity", "febrl4_nossn" if DROP else "febrl4",
                          "--model-dir", str(model), "--tau", str(tau)], capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(out.stdout + out.stderr)
    return next((l.strip() for l in out.stdout.splitlines() if "Jev labelled" in l), "")


def run(args) -> int:
    tag = args.tag or f"{args.labeller.replace('+', '')}_r{args.rounds}" + ("_nossn" if DROP else "")
    conf, model, logs = config(tag), WORK / tag / "models" / "1", WORK / tag / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    for rnd in range(1, args.rounds + 1):
        secs = zingg("findTrainingData", conf, logs / f"ftd{rnd}.log")
        note = ""
        if args.labeller in ("jev", "jev+h"):
            note = label_jev(model, args.tau)
        if args.labeller in ("truth", "jev+h"):
            pos, neg = label_truth(model, only_deferred=args.labeller == "jev+h")
            note += f"  truth labelled {pos} match + {neg} no-match"
        print(f"  round {rnd}: findTrainingData {secs:.0f} s | {note}", flush=True)
    t_train = zingg("train", conf, logs / "train.log")
    t_link = zingg("link", conf, logs / "link.log")
    print(f"  train {t_train:.0f} s, link {t_link:.0f} s")
    return score(argparse.Namespace(tag=tag))


def score(args) -> int:
    import duckdb

    tags = [args.tag] if getattr(args, "tag", None) else sorted(p.name for p in WORK.iterdir() if (p / "out").exists())
    print(f"{'run':<22}{'labels +':>9}{'labels -':>9}{'pred links':>11}{'TP':>6}{'FP':>6}{'FN':>6}{'P':>8}{'R':>8}{'F1':>8}")
    for tag in tags:
        con = duckdb.connect()
        out = f"read_parquet('{WORK / tag / 'out'}/*.parquet')"
        # a predicted link = two records of different sources in one output cluster
        rows = con.execute(f"""
            WITH r AS (SELECT z_cluster, rec_id, split_part(rec_id, '-', 2) AS ent, rec_id LIKE '%-org' AS is_a FROM {out})
            SELECT count(*) AS pred, count(*) FILTER (WHERE x.ent = y.ent) AS tp
            FROM r x JOIN r y ON x.z_cluster = y.z_cluster AND x.is_a AND NOT y.is_a""").fetchone()
        pred, tp = rows
        total = int((WORK / "true_links.txt").read_text()) if (WORK / "true_links.txt").exists() else 5000
        fp, fn = pred - tp, total - tp
        p, r = (tp / pred if pred else 0), tp / total
        marked = [str(m) for m in (WORK / tag / "models" / "1" / "trainingData" / "marked").glob("*.parquet")]
        lab = dict(con.execute(f"SELECT z_isMatch, count(DISTINCT z_cluster) FROM read_parquet({marked}, union_by_name = true) GROUP BY 1").fetchall()) if marked else {}
        print(f"{tag:<22}{lab.get(1, 0):>9}{lab.get(0, 0):>9}{pred:>11}{tp:>6}{fp:>6}{fn:>6}{p:>8.4f}{r:>8.4f}{(2 * p * r / (p + r) if p + r else 0):>8.4f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare").set_defaults(fn=prepare)
    r = sub.add_parser("run"); r.set_defaults(fn=run)
    r.add_argument("--labeller", choices=["jev", "truth", "jev+h"], required=True)
    r.add_argument("--rounds", type=int, default=6); r.add_argument("--tau", type=float, default=0.90)
    r.add_argument("--tag", default=""); r.add_argument("--drop", default="", help="comma-separated fields hidden from Zingg and Jev")
    s = sub.add_parser("score"); s.set_defaults(fn=score); s.add_argument("--tag", default="")
    ap.add_argument("--unmatched", type=float, default=0.0, help="share of A records whose partner is removed from B")
    args = ap.parse_args()
    DROP.update(f for f in getattr(args, "drop", "").split(",") if f)
    global UNMATCHED, WORK
    UNMATCHED = args.unmatched
    if UNMATCHED:
        WORK = HERE / "work" / f"febrl4_u{int(UNMATCHED * 100)}"
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
