#!/usr/bin/env python3
"""ZR-4: clustering methods compared on the dedupe corpora with clusters larger than two, then identity proofs.
-> bench/results/clusters.json, bench/CLUSTERS.md.

Per corpus (FEBRL3: clusters up to 6; Splink historical_50k: 5 156 clusters), one scoring pass exactly like ZR-3's
benchmark (bench/benchmarks.py): default candidates (k = 10 + self, canonical pairs), comparison vectors, the model
fitted on TRAIN pairs (the pair's smaller id), the threshold on VALID, every candidate pair scored. Then the four
methods cluster the links at or above the threshold:

    metrics     on the clustering INDUCED on one split's records (both the prediction and the gold clusters restricted
                to the records whose own id falls in that split): pairwise precision / recall / F1 over the
                within-cluster pairs, and B-cubed precision / recall / F1 (per record: shared members / predicted
                cluster size, / gold cluster size; averaged). A pair of two TEST records is a TEST pair: the model
                never saw it.
    winner      highest mean VALID B-cubed F1 over the two corpora; a tie keeps the current default. TEST is reported.
    convergence verified merge's loop must reach its fixed point (a round with nothing left to propose) before
                cluster.max_rounds on both corpora.
    rerun       a second, independent pass (candidates, model, scores, clusters) with the winner, its identity carried
                from the first pass's crosswalk: the number of records whose mdm_id changed must be 0 (and the ids
                must equal the first pass's even without history: they are a pure function of the clusters).
    incremental 1 % of the records (by id hash) is held out of a base pass; the next pass adds them back, deletes another
                1 % and changes another 1 % (two adjacent characters of the surname swapped). Its identity is assigned
                from the base crosswalk; identity.reconcile() must explain every id change from the log.

    python bench/clusters.py            # ~10 min on the laptop
"""
from __future__ import annotations

import datetime
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpora  # noqa: E402
from benchmarks import canonical, cfg_for, fit_and_threshold, split_col, truth_view  # noqa: E402

from lakematch import candidates, identity, matcher  # noqa: E402
from lakematch.cluster import METHODS  # noqa: E402
from lakematch.config import DEFAULTS  # noqa: E402
from lakematch.pipeline import entity_sides, pair_features, pair_scorer, resolve  # noqa: E402
from lakematch.runtime import Runtime  # noqa: E402

RESULTS = HERE / "results" / "clusters.json"
CORPORA = ("febrl3", "splink_historical_50k")
SURNAME = {"febrl3": "surname", "splink_historical_50k": "surname"}


def log(msg):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {msg}", flush=True)


# --- metrics -----------------------------------------------------------------------------------------------------------
def cluster_metrics(pred: dict, gold: dict, ids) -> dict:
    ids = [i for i in ids if i in pred and i in gold]
    cell = Counter((pred[i], gold[i]) for i in ids)
    ps, gs = Counter(pred[i] for i in ids), Counter(gold[i] for i in ids)
    c2 = lambda n: n * (n - 1) // 2
    tp, pp, tt = sum(c2(n) for n in cell.values()), sum(c2(n) for n in ps.values()), sum(c2(n) for n in gs.values())
    f = lambda p, r: 2 * p * r / (p + r) if p + r else 0.0
    pw_p, pw_r = (tp / pp if pp else 0.0), (tp / tt if tt else 0.0)
    b_p = float(np.mean([cell[(pred[i], gold[i])] / ps[pred[i]] for i in ids])) if ids else 0.0
    b_r = float(np.mean([cell[(pred[i], gold[i])] / gs[gold[i]] for i in ids])) if ids else 0.0
    r4 = lambda x: round(x, 4)
    return {"pairwise_precision": r4(pw_p), "pairwise_recall": r4(pw_r), "pairwise_f1": r4(f(pw_p, pw_r)),
            "b_cubed_precision": r4(b_p), "b_cubed_recall": r4(b_r), "b_cubed_f1": r4(f(b_p, b_r)),
            "records": len(ids), "predicted_clusters": len(ps), "gold_clusters": len(gs),
            "largest_predicted": max(ps.values()) if ps else 0}


# --- one scoring pass ----------------------------------------------------------------------------------------------------
def scoring_pass(rt, c):
    """(ids, links (a, b, p) over canonical pairs, threshold, scorer, split_of) for corpus `c` (dedupe)."""
    from pyspark.sql import functions as F
    spark = rt.spark
    truth_pd, dedupe = truth_view(c)
    assert dedupe, f"{c.name} is not a dedupe corpus"
    ccfg = cfg_for(c, candidates={"k": 11}, decision={"cardinality": "unrestricted"})
    L, R = entity_sides(rt, ccfg, spark.createDataFrame(c.left), spark.createDataFrame(c.right))
    cand = rt.materialize(canonical(candidates.generate(L, R, ccfg)), "cand")
    table, cols = pair_features(rt, ccfg, L, R, cand.withColumn("split", split_col("l_id")),
                                keep=("cand_score", "cand_rank", "cand_gap", "split"))
    truth = spark.createDataFrame(truth_pd).withColumn("label", F.lit(1.0))
    table = rt.materialize(table.join(truth, ["l_id", "r_id"], "left").fillna(0.0, ["label"]), "table")
    fit, thr = table.filter("split = 'train'"), table.filter("split = 'valid'")
    model, t = fit_and_threshold(rt, ccfg, fit, thr, cols)
    links = [(r.l_id, r.r_id, float(r.p)) for r in matcher.score(model, table).filter(F.col("p") >= t)
             .select("l_id", "r_id", "p").collect()]
    ids_pd = spark.createDataFrame(c.left[["id"]]).withColumn("split", split_col("id")).toPandas()
    split_of = dict(zip(ids_pd.id, ids_pd.split))
    return list(c.left.id), links, t, pair_scorer(rt, ccfg, L, R, model, cand), split_of, ccfg


def gold_of(c) -> dict:
    return dict(zip(c.truth.id, c.truth.cluster))


def compare(rt, c) -> dict:
    t0 = time.time()
    ids, links, t, scorer, split_of, ccfg = scoring_pass(rt, c)
    log(f"{c.name}: {len(ids)} records, {len(links)} links at p >= {t}, scoring pass {time.time() - t0:.0f} s")
    gold = gold_of(c)
    by_split = {s: [i for i in ids if split_of[i] == s] for s in ("valid", "test")}
    out = {"records": len(ids), "links": len(links), "threshold": t, "gold_clusters": len(set(gold.values())),
           "largest_gold_cluster": max(Counter(gold.values()).values())}
    assign = {}
    for m in METHODS:
        t1 = time.time()
        got, stats = resolve(ccfg, ids, None, links, t, score=scorer, method=m)
        assign[m] = got
        test = cluster_metrics(got, gold, by_split["test"])
        valid = cluster_metrics(got, gold, by_split["valid"])
        out[m] = {**test, "valid_pairwise_f1": valid["pairwise_f1"], "valid_b_cubed_f1": valid["b_cubed_f1"],
                  "wall_s": round(time.time() - t1, 1), **({"stats": stats} if stats else {})}
        log(f"  {c.name:<22} {m:<21} TEST pairwise F1 {test['pairwise_f1']:.4f}  B-cubed F1 {test['b_cubed_f1']:.4f}"
            f"  VALID B3 {valid['b_cubed_f1']:.4f}  {out[m]['wall_s']} s {stats or ''}")
    return out


def winner(res: dict) -> tuple[str, dict]:
    mean = {m: round(float(np.mean([res[c][m]["valid_b_cubed_f1"] for c in CORPORA])), 4) for m in METHODS}
    best = max(mean.values())
    tied = [m for m in METHODS if abs(mean[m] - best) < 1e-9]
    cur = DEFAULTS["cluster"]["method"]
    return (cur if cur in tied else sorted(tied)[0]), mean


# --- identity proofs -------------------------------------------------------------------------------------------------------
def rerun(rt, c, method) -> dict:
    """Two independent passes on unchanged input: ids carried over must not change; ids without history must match."""
    passes = []
    for _ in range(2):
        ids, links, t, scorer, _, ccfg = scoring_pass(rt, c)
        clusters, _ = resolve(ccfg, ids, None, links, t, score=scorer, method=method)
        passes.append(clusters)
        rt.close()
    first, _ = identity.assign(passes[0])
    carried, events = identity.assign(passes[1], previous=first, run="rerun")
    fresh, _ = identity.assign(passes[1])
    changed = sum(1 for r in first if carried.get(r) != first[r])
    return {"changed_ids": changed, "events": len(events), "ids_equal_without_history": fresh == first,
            "entities": len(set(first.values()))}


def bucket(i: str) -> int:
    return int(hashlib.sha1(i.encode()).hexdigest(), 16) % 100


def swap(s: str) -> str:
    s = str(s)
    if len(s) < 3:
        return s + "x"
    j = len(s) // 2
    return s[:j - 1] + s[j] + s[j - 1] + s[j + 1:]


def incremental(rt, c, method) -> dict:
    """Base = all but 1 % held out; next = base − 1 % deleted + the held-out 1 % + 1 % changed."""
    recs, gold = c.left.copy(), c.truth.copy()
    b = recs.id.map(bucket)
    held, deleted, changed = recs[b == 0].id, recs[b == 1].id, recs[b == 2].id
    base_recs = recs[b != 0]

    def corpus(df):
        keep = set(df.id)
        return corpora.Corpus(c.name, "dedupe", c.fields, df.reset_index(drop=True), df.reset_index(drop=True),
                              truth=gold[gold.id.isin(keep)].reset_index(drop=True))

    ids, links, t, scorer, _, ccfg = scoring_pass(rt, corpus(base_recs))
    base_clusters, _ = resolve(ccfg, ids, None, links, t, score=scorer, method=method)
    rt.close()
    base_xw, base_ev = identity.assign(base_clusters, run="base")
    nxt = recs[(b != 1)].copy()
    col = SURNAME[c.name]
    nxt.loc[nxt.id.isin(set(changed)), col] = nxt.loc[nxt.id.isin(set(changed)), col].map(swap)
    ids, links, t, scorer, _, ccfg = scoring_pass(rt, corpus(nxt))
    next_clusters, _ = resolve(ccfg, ids, None, links, t, score=scorer, method=method)
    rt.close()
    next_xw, events = identity.assign(next_clusters, previous=base_xw, run="incremental")
    ok, problems = identity.reconcile(base_xw, next_xw, events)
    moved = sum(1 for r in base_xw if r in next_xw and next_xw[r] != base_xw[r])
    return {"added": int(len(held)), "deleted": int(len(deleted)), "changed": int(len(changed)),
            "base_records": len(base_xw), "next_records": len(next_xw), "events": dict(Counter(e["event"] for e in events)),
            "records_whose_id_changed": moved, "reconciles": ok, "problems": problems,
            "deleted_absent": not (set(deleted) & set(next_xw)), "added_present": set(held) <= set(next_xw)}


def main() -> int:
    from lakematch import config
    rt = Runtime(config.build({"storage": {"root": str(corpora.DATA / "runs" / "clusters")},
                               "runtime": {"cores": 8, "shuffle_partitions": 16, "driver_memory": "8g"}}))
    loaded = {n: corpora.LOADERS[n]() for n in CORPORA}
    res: dict = {}
    for n in CORPORA:
        res[n] = compare(rt, loaded[n])
        rt.close()
    w, mean = winner(res)
    res["winner"], res["mean_valid_b_cubed_f1"] = w, mean
    log(f"winner {w}  (mean VALID B-cubed F1 {mean})")
    vm = {n: res[n]["verified_merge"]["stats"] for n in CORPORA}
    res["convergence_test"] = {"passed": all(s["converged"] and s["rounds"] < DEFAULTS["cluster"]["max_rounds"]
                                             for s in vm.values()),
                               "rule": "verified_merge reaches a round with nothing left to propose before "
                                       "cluster.max_rounds", "per_corpus": vm}
    res["rerun"] = {n: rerun(rt, loaded[n], w) for n in CORPORA}
    res["rerun_changed_ids"] = sum(r["changed_ids"] for r in res["rerun"].values())
    log(f"rerun: {res['rerun']}")
    res["incremental"] = {n: incremental(rt, loaded[n], w) for n in CORPORA}
    res["incremental_log_reconciles"] = all(r["reconciles"] and r["deleted_absent"] and r["added_present"]
                                            for r in res["incremental"].values())
    log(f"incremental: {res['incremental']}")
    if not res["convergence_test"]["passed"]:                   # a failed test must read as false, not as a dict
        res["convergence_detail"], res["convergence_test"] = res["convergence_test"], False
    res["meta"] = {"generated": datetime.datetime.now().isoformat(timespec="seconds"),
                   "spark": rt.caps.spark_version, "default_cluster_method": DEFAULTS["cluster"]["method"]}
    rt.close(stop=True)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(res, indent=1, default=str) + "\n")
    from render_clusters import render
    render(RESULTS, HERE / "CLUSTERS.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
