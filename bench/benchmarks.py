#!/usr/bin/env python3
"""ZR-3: every corpus end to end on the laptop -> bench/results/benchmarks.json -> bench/BENCHMARKS.md.

Each corpus runs in its own process (`one <corpus>`), so its wall time includes Python start, the Spark session and
every stage from raw records to scored links. `all` runs them one after the other and merges the results with the
references (bench/references.py, the recorded Splink runs in bench/results/splink.json) and the method winners of
bench/results/methods.json (ZR-3a, chosen on VALIDATION).

Protocol (the same for every corpus, TEST is read once per labeller):

  linkage / dedupe   records -> entity view -> candidates (gram_topk, k = 5; k = 10 for dedupe, self pairs dropped,
                     pairs canonicalised) -> comparison vectors. Left records (the smaller id for dedupe) are split
                     by xxhash64 of their id: train 60 % / valid 20 % / test 20 % — the split of bench/methods.py, so
                     the method choices never saw TEST. Gold labeller: every TRAIN candidate labelled from the truth,
                     model fitted on TRAIN, threshold on VALID, links on TEST under the cardinality policy
                     (linkage: decision.cardinality; dedupe: unrestricted — clustering is ZR-4). Units = TEST left
                     records; a true pair the candidates missed is a false negative.
  pairs              the corpus's fixed pair splits (Ditto's for the Magellan sets, a line hash for BPID): model on
                     TRAIN, threshold on VALID, F1 on TEST pairs. Candidate recall@k = TEST matches that gram_topk
                     (k = 5) proposes when run over all records.
  Jev labeller       the same run with no gold label: Jev labels 400 TRAIN candidate pairs (xxhash order), only its
                     confident answers (tau 0.90) are kept, split 75 / 25 by left id into fit / threshold. Tokens and
                     dollars are the requests actually sent (answers are cached under data/runs/bench/jev/).
  trivial baseline   always link each left record's nearest neighbour (rank-1 candidate), scored on the same units.

F1 intervals: 95 % percentile bootstrap over TEST units (1 000 resamples, seed 0). Peak shuffle: the largest bytes
written by one stage, read from the Spark event log. De-duplication across splits is asserted per corpus.

    python bench/benchmarks.py all [--only a,b] [--skip-jev]     # also: lakematch bench --all
    python bench/benchmarks.py one <corpus> [--skip-jev]
    python bench/benchmarks.py render
"""
from __future__ import annotations

import time

T0 = time.time()

import argparse  # noqa: E402
import datetime  # noqa: E402
import gzip  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import corpora  # noqa: E402

RESULTS = HERE / "results" / "benchmarks.json"
WORK = corpora.DATA / "runs" / "bench"
ORDER = ["febrl4_half_unmatched", "febrl4_original", "febrl3", "bpid", "abt_buy", "amazon_google", "walmart_amazon",
         "dblp_acm", "splink_historical_50k", "leipzig_affiliations", "synthetic_1e6"]
VARIANTS = {"febrl4_half_unmatched_no_soc_sec_id": ("febrl4_half_unmatched", ("soc_sec_id",))}
N_JEV, TAU = 400, 0.90
B, SEED = 1000, 0
MEMORY = {"synthetic_1e6": "24g", "splink_historical_50k": "8g"}


def log(msg: str) -> None:
    print(f"[{datetime.datetime.now():%H:%M:%S}] {msg}", flush=True)


def load(name: str) -> corpora.Corpus:
    if name in VARIANTS:
        base, drop = VARIANTS[name]
        return corpora.febrl4_half_unmatched(drop=drop)
    return corpora.LOADERS[name]()


# --- statistics ----------------------------------------------------------------------------------------------------
def f1_of(tp, fp, fn):
    d = 2 * tp + fp + fn
    return np.where(d > 0, 2 * tp / np.where(d > 0, d, 1), 0.0)


def summarise(tp, fp, fn) -> dict:
    """tp / fp / fn: per-unit counts (a TEST pair, or a TEST left record). Percentile bootstrap over units."""
    tp, fp, fn = (np.asarray(x, dtype=float) for x in (tp, fp, fn))
    idx = np.random.default_rng(SEED).integers(0, len(tp), size=(B, len(tp)))
    boots = f1_of(tp[idx].sum(1), fp[idx].sum(1), fn[idx].sum(1))
    T, P, N = tp.sum(), fp.sum(), fn.sum()
    return {"precision": round(float(T / max(T + P, 1)), 4), "recall": round(float(T / max(T + N, 1)), 4),
            "f1": round(float(f1_of(T, P, N)), 4),
            "f1_ci95": [round(float(np.percentile(boots, 2.5)), 4), round(float(np.percentile(boots, 97.5)), 4)],
            "units": int(len(tp)), "tp": int(T), "fp": int(P), "fn": int(N)}


def unit_counts(units: list[str], links: pd.DataFrame, truth: pd.DataFrame) -> tuple:
    """Per-unit tp / fp / fn of predicted `links` against `truth` (both l_id, r_id; the unit is l_id)."""
    links = links[["l_id", "r_id"]].drop_duplicates()
    truth = truth[["l_id", "r_id"]].drop_duplicates()
    hit = links.merge(truth, on=["l_id", "r_id"])
    n = lambda df: df.groupby("l_id").size()
    frame = pd.DataFrame(index=pd.Index(units, name="l_id"))
    frame["tp"], frame["pred"], frame["true"] = n(hit), n(links), n(truth)
    frame = frame.fillna(0)
    return frame["tp"].to_numpy(), (frame["pred"] - frame["tp"]).to_numpy(), (frame["true"] - frame["tp"]).to_numpy()


# --- one corpus ----------------------------------------------------------------------------------------------------
def cfg_for(c, **over):
    from lakematch import config
    user = {"entity": {"name": c.name, "fields": c.fields},
            "storage": {"root": str(WORK / c.name)},
            "runtime": {"cores": 8, "shuffle_partitions": 32 if c.name == "synthetic_1e6" else 16,
                        "driver_memory": MEMORY.get(c.name, "6g")}}
    for k, v in over.items():
        user.setdefault(k, {}).update(v)
    return config.build(user)


def split_col(col):
    from pyspark.sql import functions as F
    b = F.pmod(F.xxhash64(col), F.lit(10))
    return F.when(b < 6, "train").when(b < 8, "valid").otherwise("test")


def canonical(df):
    from pyspark.sql import functions as F
    return (df.filter("l_id != r_id").withColumn("_a", F.least("l_id", "r_id")).withColumn("_b", F.greatest("l_id", "r_id"))
              .drop("l_id", "r_id").withColumnRenamed("_a", "l_id").withColumnRenamed("_b", "r_id")
              .dropDuplicates(["l_id", "r_id"]))


def truth_view(c) -> tuple[pd.DataFrame, bool]:
    if c.kind == "dedupe":
        t = c.truth.merge(c.truth, on="cluster")
        t = t[t.id_x < t.id_y].rename(columns={"id_x": "l_id", "id_y": "r_id"})
        return t[["l_id", "r_id"]].reset_index(drop=True), True
    return c.truth[["l_id", "r_id"]].copy(), False


def jev_key_loader() -> None:
    """The harness reads the key the way the rest of this machine does; the package reads TYPESAFE_API_KEY only."""
    if os.environ.get("TYPESAFE_API_KEY"):
        return
    env = Path.home() / ".secrets" / "typesafe.env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("TYPESAFE_API_KEY="):
                os.environ["TYPESAFE_API_KEY"] = line.split("=", 1)[1].strip().strip("\"'")


def fit_and_threshold(rt, cfg, fit, thr, cols):
    from lakematch import decision, matcher
    model = matcher.train(fit, cols, cfg)
    return model, decision.pick_threshold(matcher.score(model, thr), cfg)


def run_linkage(rt, c, cfg, do_jev: bool) -> dict:
    from pyspark.sql import Window, functions as F
    from lakematch import candidates, decision, labels, matcher
    from lakematch.pipeline import entity_sides, pair_features
    spark = rt.spark
    truth_pd, dedupe = truth_view(c)
    k = 10 if dedupe else 5
    ccfg = cfg_for(c, candidates={"k": k + (1 if dedupe else 0)})
    L, R = entity_sides(rt, ccfg, spark.createDataFrame(c.left), spark.createDataFrame(c.right))
    raw = rt.materialize(candidates.generate(L, R, ccfg), "cand_raw")
    if dedupe:
        cand = rt.materialize(canonical(raw), "cand")
        nn = raw.filter("l_id != r_id").withColumn("_n", F.row_number().over(
            Window.partitionBy("l_id").orderBy("cand_rank", "r_id"))).filter("_n = 1")
        nn = canonical(nn.drop("_n"))
    else:
        cand = raw
        nn = raw.filter("cand_rank = 1")
    n_cand = cand.count()
    table, cols = pair_features(rt, ccfg, L, R, cand.withColumn("split", split_col("l_id")),
                                keep=("cand_score", "cand_rank", "cand_gap", "split"))
    truth = spark.createDataFrame(truth_pd).withColumn("label", F.lit(1.0))
    table = rt.materialize(table.join(truth, ["l_id", "r_id"], "left").fillna(0.0, ["label"]), "table")

    # units and TEST truth, on the driver (split computed by Spark so both sides agree)
    ids = spark.createDataFrame(c.left[["id"]]).withColumn("split", split_col("id")).toPandas()
    test_units = sorted(ids.loc[ids.split == "test", "id"])
    test_set = set(test_units)
    test_truth = truth_pd[truth_pd.l_id.isin(test_set)]
    split_of = dict(zip(ids.id, ids.split))
    assert_disjoint = {s: set(ids.loc[ids.split == s, "id"]) for s in ("train", "valid", "test")}
    dedup_ok = not (assert_disjoint["train"] & assert_disjoint["test"]) and not (assert_disjoint["valid"] & assert_disjoint["test"])
    pair_splits = truth_pd.l_id.map(split_of)
    dedup_ok = dedup_ok and pair_splits.notna().all()

    cand_test = cand.join(spark.createDataFrame(pd.DataFrame({"l_id": test_units})), "l_id").select("l_id", "r_id").toPandas()
    cand_recall = len(cand_test.merge(test_truth, on=["l_id", "r_id"])) / max(len(test_truth), 1)
    nn_test = nn.select("l_id", "r_id").toPandas()
    nn_test = nn_test[nn_test.l_id.isin(test_set)]
    baseline = summarise(*unit_counts(test_units, nn_test, test_truth))

    dcfg = cfg_for(c, decision={"cardinality": "unrestricted"}) if dedupe else ccfg
    fit, thr, test = (table.filter(f"split = '{s}'") for s in ("train", "valid", "test"))
    model, t = fit_and_threshold(rt, dcfg, fit, thr, cols)
    links = decision.links(matcher.score(model, test), t, dcfg).select("l_id", "r_id").toPandas()
    gold = summarise(*unit_counts(test_units, links, test_truth))
    gold.update({"threshold": t, "labels": {"train": fit.count(), "valid": thr.count()}})
    out = {"kind": c.kind, "records": {"left": len(c.left), "right": len(c.right)} if not dedupe else {"records": len(c.left)},
           "true_pairs": len(truth_pd), "test_true_pairs": len(test_truth), "candidates": n_cand,
           "k": k, "candidate_recall_at_k": round(cand_recall, 4), "trivial_baseline": baseline, "gold": gold,
           "cardinality": dcfg.get("decision.cardinality"),
           "split_dedup": {"ok": bool(dedup_ok), "check": "train/valid/test left ids disjoint; each true pair has "
                                                          "exactly one split (its left / smaller id)"}}
    out["wall_s_incl_start"] = round(time.time() - T0, 1)
    log(f"{c.name}: F1 {gold['f1']} {gold['f1_ci95']}  NN {baseline['f1']}  cand recall {cand_recall:.4f}  "
        f"{out['wall_s_incl_start']} s")
    if do_jev:
        t1 = time.time()
        sample = fit.orderBy(F.xxhash64("l_id", "r_id"), "l_id", "r_id").limit(N_JEV)
        jcfg = cfg_for(c, labels={"llm_cache": str(WORK / "jev" / f"{c.name.split('_no_')[0]}.jsonl"), "llm_tau": TAU})
        lab, usage = labels.llm_labelled(spark, fit.drop("label"), jcfg, L, R, pairs=sample)
        lab = rt.materialize(lab, "jev_labels")
        jfit, jthr = labels.split(lab, jcfg)
        out["jev"] = jev_result(rt, dcfg, jfit, jthr, test, cols, test_units, test_truth, usage, t1, pairs_mode=False)
    return out


def jev_result(rt, cfg, jfit, jthr, test, cols, test_units, test_truth, usage, t1, pairs_mode):
    from lakematch import decision, matcher
    n_fit, n_pos = jfit.count(), jfit.filter("label = 1").count()
    res = {"usage": usage, "labels_fit": n_fit, "labels_fit_matches": n_pos, "labels_threshold": jthr.count()}
    if n_pos == 0 or n_pos == n_fit:
        res["note"] = "Jev's confident labels hold one class only: no model can be fitted"
        return res
    model, t = fit_and_threshold(rt, cfg, jfit, jthr, cols)
    scored = matcher.score(model, test)
    if pairs_mode:
        pdf = scored.select("p", "label").toPandas()
        pred, y = (pdf.p >= t).to_numpy(), (pdf.label == 1.0).to_numpy()
        res.update(summarise(pred & y, pred & ~y, ~pred & y))
    else:
        links = decision.links(scored, t, cfg).select("l_id", "r_id").toPandas()
        res.update(summarise(*unit_counts(test_units, links, test_truth)))
    res.update({"threshold": t, "wall_s": round(time.time() - t1, 1)})
    log(f"  jev: F1 {res['f1']} {res['f1_ci95']}  asked {usage['asked']} kept {usage['kept']}  "
        f"sent {usage['requests']} ({usage['input_tokens']} tokens, ${usage['usd']})")
    return res


def run_pairs(rt, c, cfg, do_jev: bool) -> dict:
    from pyspark.sql import functions as F
    from lakematch import candidates, labels, matcher
    from lakematch.pipeline import entity_sides, pair_features
    spark = rt.spark
    pairs = c.pairs
    # a pair in two splits would leak (the loaders keep its first split); assert it here, on content ids
    counts = pairs.groupby(["l_id", "r_id"])["split"].nunique()
    dedup_ok = bool((counts == 1).all())
    L, R = entity_sides(rt, cfg, spark.createDataFrame(c.left), spark.createDataFrame(c.right))
    table, cols = pair_features(rt, cfg, L, R, spark.createDataFrame(pairs), keep=("label", "split"))
    fit, thr, test = (table.filter(f"split = '{s}'") for s in ("train", "valid", "test"))
    model, t = fit_and_threshold(rt, cfg, fit, thr, cols)
    pdf = matcher.score(model, test).select("l_id", "r_id", "p", "label").orderBy("l_id", "r_id").toPandas()
    pred, y = (pdf.p >= t).to_numpy(), (pdf.label == 1.0).to_numpy()
    gold = summarise(pred & y, pred & ~y, ~pred & y)
    gold.update({"threshold": t, "labels": {"train": fit.count(), "valid": thr.count()}})
    # candidate recall@k and the nearest-neighbour baseline over all records
    ccfg = cfg_for(c, candidates={"k": 5})
    cand = rt.materialize(candidates.generate(L, R, ccfg).select("l_id", "r_id", "cand_rank"), "cand")
    cset = cand.toPandas()
    pos = pdf[pdf.label == 1.0][["l_id", "r_id"]]
    cand_recall = len(pos.merge(cset, on=["l_id", "r_id"])) / max(len(pos), 1)
    nn = set(map(tuple, cset[cset.cand_rank == 1][["l_id", "r_id"]].to_numpy()))
    bpred = np.array([(a, b) in nn for a, b in zip(pdf.l_id, pdf.r_id)])
    baseline = summarise(bpred & y, bpred & ~y, ~bpred & y)
    out = {"kind": c.kind, "records": {"left": len(c.left), "right": len(c.right)},
           "pairs": {s: int((pairs.split == s).sum()) for s in ("train", "valid", "test")},
           "test_matches": int(y.sum()), "candidates": len(cset), "k": 5,
           "candidate_recall_at_k": round(cand_recall, 4), "trivial_baseline": baseline, "gold": gold,
           "split_dedup": {"ok": dedup_ok, "check": "no (left, right) pair — records identified by content — in two "
                                                    "splits"}}
    out["wall_s_incl_start"] = round(time.time() - T0, 1)
    log(f"{c.name}: F1 {gold['f1']} {gold['f1_ci95']}  NN {baseline['f1']}  cand recall {cand_recall:.4f}  "
        f"{out['wall_s_incl_start']} s")
    if do_jev:
        t1 = time.time()
        sample = fit.orderBy(F.xxhash64("l_id", "r_id"), "l_id", "r_id").limit(N_JEV)
        jcfg = cfg_for(c, labels={"llm_cache": str(WORK / "jev" / f"{c.name}.jsonl"), "llm_tau": TAU})
        lab, usage = labels.llm_labelled(spark, fit.drop("label"), jcfg, L, R, pairs=sample)
        lab = rt.materialize(lab, "jev_labels")
        jfit, jthr = labels.split(lab, jcfg)
        out["jev"] = jev_result(rt, cfg, jfit, jthr, test, cols, None, None, usage, t1, pairs_mode=True)
    return out


def shuffle_from_event_log(log_dir: Path) -> dict:
    """Largest bytes one stage wrote to shuffle, and the total, from the Spark event log of this process."""
    per_stage: dict[int, int] = {}
    files = sorted(f for f in log_dir.rglob("*") if f.is_file()) if log_dir.exists() else []
    for f in files:
        opener = gzip.open if f.suffix == ".gz" else open
        with opener(f, "rt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"SparkListenerTaskEnd"' not in line:
                    continue
                j = json.loads(line)
                w = (j.get("Task Metrics") or {}).get("Shuffle Write Metrics") or {}
                per_stage[j["Stage ID"]] = per_stage.get(j["Stage ID"], 0) + int(w.get("Shuffle Bytes Written", 0))
    if not per_stage:
        return {}
    return {"peak_stage_mb": round(max(per_stage.values()) / 2**20, 1), "total_mb": round(sum(per_stage.values()) / 2**20, 1)}


def one(name: str, do_jev: bool) -> dict:
    from lakematch.runtime import Runtime
    c = load(name)
    if name in VARIANTS:
        c.name = name
    cfg = cfg_for(c)
    if do_jev:
        jev_key_loader()
    rt = Runtime(cfg)
    try:
        res = run_pairs(rt, c, cfg, do_jev) if c.kind == "pairs" else run_linkage(rt, c, cfg, do_jev)
        res["spark"] = rt.caps.spark_version
    finally:
        rt.close(stop=True)
    res["shuffle"] = shuffle_from_event_log(Path(os.environ.get("LAKEMATCH_EVENT_LOG", "/nonexistent")))
    n = sum(res["records"].values())
    res["records_per_s"] = round(n / res["wall_s_incl_start"], 1)
    res["notes"] = c.notes
    out = WORK / "results" / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1) + "\n")
    return res


def spawn(name: str, do_jev: bool) -> dict:
    """Run one corpus in a fresh process with a Spark event log; returns its result file."""
    ev = WORK / "eventlog" / name
    shutil.rmtree(ev, ignore_errors=True)
    ev.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, LAKEMATCH_EVENT_LOG=str(ev),
               PYSPARK_SUBMIT_ARGS=f"--conf spark.ui.showConsoleProgress=false --conf spark.eventLog.enabled=true --conf spark.eventLog.compress=false --conf spark.eventLog.dir=file://{ev} pyspark-shell")
    cmd = [sys.executable, str(HERE / "benchmarks.py"), "one", name] + ([] if do_jev else ["--skip-jev"])
    log(f"== {name}")
    r = subprocess.run(cmd, env=env)
    if r.returncode:
        raise SystemExit(f"{name}: exit {r.returncode}")
    return json.loads((WORK / "results" / f"{name}.json").read_text())


def merge(per: dict) -> dict:
    import references
    methods = json.loads((HERE / "results" / "methods.json").read_text())
    splink = json.loads((HERE / "results" / "splink.json").read_text()) if (HERE / "results" / "splink.json").exists() else {}
    corp = {}
    for name in ORDER:
        r = per.get(name)
        if r is None:
            continue
        row = {**r, "precision": r["gold"]["precision"], "recall": r["gold"]["recall"], "f1": r["gold"]["f1"],
               "f1_ci95": r["gold"]["f1_ci95"], "references": references.for_corpus(name, splink.get(name))}
        if name == "febrl4_half_unmatched" and "febrl4_half_unmatched_no_soc_sec_id" in splink:
            row["references"]["splink"]["ssn_hidden"] = splink["febrl4_half_unmatched_no_soc_sec_id"]
        if name == "febrl4_half_unmatched":
            row["f1_all_fields"] = r["gold"]["f1"]
            h = per.get("febrl4_half_unmatched_no_soc_sec_id")
            if h:
                row["f1_ssn_hidden"] = h["gold"]["f1"]
                row["ssn_hidden"] = h
                row["wall_s_incl_start"] = max(r["wall_s_incl_start"], h["wall_s_incl_start"])
        corp[name] = row
    from lakematch.config import DEFAULTS
    winners = methods.get("winners", {})
    return {"corpora": corp, "method_winners": winners,
            "method_winners_source": "bench/results/methods.json (ZR-3a, chosen on validation)",
            "split_dedup_asserted": bool(corp) and all(v["split_dedup"]["ok"] for v in corp.values()),
            "defaults": {k: _get(DEFAULTS, k) for k in winners},
            "protocol": __doc__.split("Protocol", 1)[1].split("    python bench")[0].strip()}


def _get(d, key):
    for p in key.split("."):
        d = d[p]
    return d


def save(res: dict, generated: str | None = None) -> None:
    import platform
    res["meta"] = {"generated": generated or datetime.datetime.now().isoformat(timespec="seconds"), "bootstrap": B,
                   "machine": f"{platform.machine()} · {os.cpu_count()} cores · local[8]",
                   "jev_price_per_m_input_usd": 0.042}
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(res, indent=1) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("all")
    a.add_argument("--only", help="comma-separated corpora (the others keep their last result)")
    a.add_argument("--skip-jev", action="store_true")
    o = sub.add_parser("one")
    o.add_argument("corpus", choices=[*ORDER, *VARIANTS])
    o.add_argument("--skip-jev", action="store_true")
    sub.add_parser("render")
    args = ap.parse_args(argv)
    if args.cmd == "one":
        one(args.corpus, not args.skip_jev)
        return 0
    names = [*ORDER[:1], *VARIANTS, *ORDER[1:]]
    if args.cmd == "all":
        for n in (args.only.split(",") if args.only else names):
            spawn(n, not args.skip_jev and n not in VARIANTS)
    # merge the per-corpus results of the last runs (data/runs/bench/results, local) with the references;
    # `render` on a fresh clone has none and re-renders the committed JSON as it is
    per = {n: json.loads((WORK / "results" / f"{n}.json").read_text()) for n in names
           if (WORK / "results" / f"{n}.json").exists()}
    if per:
        if args.cmd == "render":      # keep the generation time of the runs; only references / rendering changed
            generated = json.loads(RESULTS.read_text())["meta"]["generated"] if RESULTS.exists() else None
            save(merge(per), generated)
        else:
            save(merge(per))
    from render_benchmarks import render
    render(RESULTS, HERE / "BENCHMARKS.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
