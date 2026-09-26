#!/usr/bin/env python3
"""ZR-3a: every method choice compared on VALIDATION data; the winners become the defaults in config.py.

Splits. Left records are bucketed by a hash of their id: train (60 %), valid (20 %), test (20 %, untouched here —
it belongs to ZR-3's final table). Pair corpora (BPID, Abt-Buy) keep their fixed pair splits; Leipzig pairs are split
by pair hash, as in bench/ablation.py.

1. candidates.method — candidate recall at an equal pair budget: every method's proposals are ranked by the same IDF
   gram cosine and cut to k per left record (k = 5; 10 for the Leipzig dedupe, self pairs removed). Recall = true
   pairs of VALID left records that survive. learned_blocker learns from the matches of TRAIN left records only.
   Tie-break: fewer proposed pairs.
2. features.string_similarity, matcher.estimator, decision.cardinality — end-to-end F1 on VALID with everything else at
   its default and the candidate winner. The model is fitted on 80 % of TRAIN, the threshold picked on the other 20 %
   (by left id for linkage, by pair hash otherwise), and F1 measured on VALID. Cardinality applies to the two
   linkage-shaped corpora (FEBRL4, Abt-Buy); BPID pairs are independent and Leipzig is dedupe (clusters are ZR-4).

Winner of each choice: the highest mean over the corpora it applies to; a tie keeps the current default.

    python bench/methods.py run [--only candidates|downstream]     # writes bench/results/methods.json
    python bench/methods.py render                                   # bench/METHODS.md
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpora  # noqa: E402
from ablation import boot_idx, f1_counts, summarise, strip  # noqa: E402

from pyspark.sql import functions as F  # noqa: E402

from lakematch import candidates, config, decision, matcher  # noqa: E402
from lakematch.config import DEFAULTS  # noqa: E402
from lakematch.features import active_families, family_of, spark_at_least  # noqa: E402
from lakematch.pipeline import entity_sides, pair_features  # noqa: E402
from lakematch.runtime import Runtime  # noqa: E402

RESULTS = HERE / "results" / "methods.json"
CORPORA = ("febrl4_half_unmatched", "bpid", "abt_buy", "leipzig_affiliations")
CAND = ["gram_topk", "learned_blocker", "minhash_lsh", "field_blocks", "union"]
UNION_OF = ["gram_topk", "field_blocks"]
SIMS = ["levenshtein", "jaro_winkler", "both"]
ESTS = ["gbt", "logistic_regression", "random_forest"]
CARDS = ["one_to_one", "many_to_one", "unrestricted"]


def log(msg):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {msg}", flush=True)


def bucket(col):
    b = F.pmod(F.xxhash64(col), F.lit(10))
    return F.when(b < 6, "train").when(b < 8, "valid").otherwise("test")


def cfg_for(corpus, **over):
    user = {"entity": {"name": corpus.name, "fields": corpus.fields},
            "storage": {"root": str(corpora.DATA / "runs" / "methods")}, "runtime": {"cores": 8}}
    for k, v in over.items():
        user.setdefault(k, {}).update(v)
    return config.build(user)


def linkage_view(c):
    """(left, right, truth, dedupe) for every corpus: pair corpora become two-table linkage over their records."""
    if c.kind == "pairs":
        truth = c.pairs[c.pairs.label == 1.0][["l_id", "r_id"]]
        return c.left, c.right, truth, False
    if c.kind == "dedupe":
        t = c.truth.merge(c.truth, on="cluster")
        t = t[t.id_x < t.id_y].rename(columns={"id_x": "l_id", "id_y": "r_id"})[["l_id", "r_id"]]
        return c.left, c.right, t, True
    return c.left, c.right, c.truth, False


# --- 1. candidates -----------------------------------------------------------------------------------------------------
def compare_candidates(rt, c) -> dict:
    spark = rt.spark
    left_pd, right_pd, truth_pd, dedupe = linkage_view(c)
    k = 10 if dedupe else 5
    base = cfg_for(c, candidates={"k": k + (1 if dedupe else 0), "union_of": UNION_OF},
                   features={"embeddings": {"provider": "none"}})
    L, R = entity_sides(rt, base, spark.createDataFrame(left_pd), spark.createDataFrame(right_pd))
    truth = spark.createDataFrame(truth_pd).withColumn("split", bucket("l_id"))
    if dedupe:   # a pair belongs to the split of its smaller id; count both orientations as the same pair
        truth = truth.withColumn("split", bucket(F.least("l_id", "r_id")))
    train_pos = truth.filter("split = 'train'").orderBy(F.xxhash64("l_id", "r_id")).limit(300).withColumn("label", F.lit(1.0))
    valid_truth = rt.materialize(truth.filter("split = 'valid'").select("l_id", "r_id"), "valid_truth")
    n_valid = valid_truth.count()
    out = {}
    for m in CAND:
        cfg = cfg_for(c, candidates={"method": m, "k": k + (1 if dedupe else 0), "union_of": UNION_OF},
                      features={"embeddings": {"provider": "none"}})
        t0 = time.time()
        uses_labels = m == "learned_blocker" or (m == "union" and "learned_blocker" in UNION_OF)
        props = rt.materialize(candidates.propose(m, L, R, cfg, train_pos if uses_labels else None), f"props_{m}")
        n_props = props.count()
        kept = candidates.top_k(candidates.rescore(props, L, R, cfg), cfg.get("candidates.k"))
        if dedupe:
            kept = kept.filter("l_id != r_id").select(F.least("l_id", "r_id").alias("l_id"),
                                                      F.greatest("l_id", "r_id").alias("r_id")).distinct()
        kept = rt.materialize(kept.select("l_id", "r_id"), f"kept_{m}")
        hit = kept.join(valid_truth, ["l_id", "r_id"]).count()
        out[m] = {"recall_at_budget": round(hit / max(n_valid, 1), 4), "proposals": n_props,
                  "kept": kept.count(), "wall_s": round(time.time() - t0, 1)}
        log(f"  {c.name:<22} {m:<16} recall {out[m]['recall_at_budget']:.4f}  proposals {n_props:>9}  {out[m]['wall_s']} s")
    return {"choices": out, "budget_per_left": k, "valid_true_pairs": n_valid}


# --- 2. downstream -----------------------------------------------------------------------------------------------------
def build_table(rt, c, cand_method):
    """A feature table over the corpus with every column any choice needs (lev + jw + defaults + embeddings):
    l_id, r_id, label, part (fit | thr | valid | test)."""
    spark = rt.spark
    cfg = cfg_for(c, features={"string_similarity": "both", "udf_features": True},
                  candidates={"method": cand_method, "union_of": UNION_OF})
    left_pd, right_pd, truth_pd, dedupe = linkage_view(c)
    L, R = entity_sides(rt, cfg, spark.createDataFrame(left_pd), spark.createDataFrame(right_pd))
    if c.kind == "pairs":
        pairs = spark.createDataFrame(c.pairs)
        pairs = pairs.withColumn("part", F.when(F.col("split") == "train",
                                                F.when(F.pmod(F.xxhash64("l_id", "r_id"), F.lit(5)) < 4, "fit").otherwise("thr"))
                                           .otherwise(F.col("split"))).drop("split")
        table, cols = pair_features(rt, cfg, L, R, pairs, keep=("label", "part"))
        return table, cols, cfg, "pair"
    truth = spark.createDataFrame(truth_pd).withColumn("label", F.lit(1.0))
    k = 10 if dedupe else 5
    ccfg = cfg_for(c, candidates={"method": cand_method, "k": k + (1 if dedupe else 0), "union_of": UNION_OF},
                   features={"embeddings": {"provider": "none"}})
    train_pos = truth.withColumn("s", bucket("l_id")).filter("s = 'train'").orderBy(F.xxhash64("l_id", "r_id")).limit(300)
    cand = candidates.generate(L, R, ccfg, train_pos)
    if dedupe:
        cand = cand.filter("l_id != r_id").withColumn("_a", F.least("l_id", "r_id")).withColumn("_b", F.greatest("l_id", "r_id")) \
                   .drop("l_id", "r_id").withColumnRenamed("_a", "l_id").withColumnRenamed("_b", "r_id") \
                   .dropDuplicates(["l_id", "r_id"])
    cand = rt.materialize(cand, "cand_" + c.name)
    split = bucket(F.least("l_id", "r_id") if dedupe else F.col("l_id"))
    sub = F.pmod(F.xxhash64("l_id"), F.lit(5))
    cand = cand.join(truth, ["l_id", "r_id"], "left").fillna(0.0, ["label"]).withColumn(
        "part", F.when(split == "train", F.when(sub < 4, "fit").otherwise("thr")).otherwise(split))
    table, cols = pair_features(rt, cfg, L, R, cand, keep=("cand_score", "cand_rank", "cand_gap", "label", "part"))
    return table, cols, cfg, "linkage" if not dedupe else "pair"


def columns_for(cols, sim: str) -> list[str]:
    fams = active_families(config.build({"features": {"string_similarity": sim, "udf_features": True}}))
    return [c for c in cols if family_of(c) in fams]


def evaluate(table, cols, cfg, shape, estimator="gbt", cardinality=None, truth_valid=None):
    ecfg = config.build({**{k: v for k, v in cfg.data.items() if k in ("entity", "features", "candidates", "storage")},
                         "matcher": {"estimator": estimator},
                         "decision": {"cardinality": cardinality or "one_to_one"}})
    fit, thr, valid = (table.filter(f"part = '{p}'") for p in ("fit", "thr", "valid"))
    model = matcher.train(fit, cols, ecfg)
    t = decision.pick_threshold(matcher.score(model, thr), ecfg)
    scored = matcher.score(model, valid)
    if shape == "pair" and cardinality is None:
        rows = scored.select("l_id", "r_id", "p", "label").orderBy("l_id", "r_id").collect()
        pred = np.array([r.p >= t for r in rows]); y = np.array([r.label == 1.0 for r in rows])
        tp, fp, fn = pred & y, pred & ~y, ~pred & y
    else:     # linkage-shaped: apply the cardinality policy; units = valid left records (or valid pairs)
        links = {(r.l_id, r.r_id) for r in decision.links(scored, t, ecfg).select("l_id", "r_id").collect()}
        units = sorted({(r.l_id, r.r_id) for r in scored.select("l_id", "r_id").collect()} | truth_valid)
        tp = np.array([(u in links) and (u in truth_valid) for u in units])
        fp = np.array([(u in links) and (u not in truth_valid) for u in units])
        fn = np.array([(u not in links) and (u in truth_valid) for u in units])
    res = summarise(tp, fp, fn, boot_idx(len(tp)))
    return {"valid_f1": res["f1"], "ci95": res["ci95"], "precision": res["precision"], "recall": res["recall"],
            "threshold": t}


def downstream(rt, c, cand_method) -> dict:
    t0 = time.time()
    table, cols, cfg, shape = build_table(rt, c, cand_method)
    log(f"  {c.name}: feature table {table.count()} rows, {len(cols)} columns, {time.time() - t0:.0f} s")
    default_cols = columns_for(cols, DEFAULTS["features"]["string_similarity"])
    left_pd, right_pd, truth_pd, dedupe = linkage_view(c)
    valid_truth = None
    if shape == "linkage" or c.name == "abt_buy":
        vt = table.filter("part = 'valid' and label = 1").select("l_id", "r_id").collect()
        if shape == "linkage":   # true links of valid left records, candidates or not (a missed candidate is a miss)
            valid_left = {r.l_id for r in table.filter("part = 'valid'").select("l_id").distinct().collect()}
            valid_truth = {(a, b) for a, b in truth_pd[["l_id", "r_id"]].itertuples(index=False) if a in valid_left}
        else:
            valid_truth = {(r.l_id, r.r_id) for r in vt}
    out = {"string_similarity": {}, "estimator": {}, "cardinality": {}}
    lk = dict(truth_valid=valid_truth, cardinality="one_to_one") if shape == "linkage" else {}
    for sim in SIMS:
        out["string_similarity"][sim] = evaluate(table, columns_for(cols, sim), cfg, shape, **lk)
        log(f"  {c.name:<22} similarity {sim:<20} F1 {out['string_similarity'][sim]['valid_f1']:.4f}")
    for est in ESTS:
        out["estimator"][est] = evaluate(table, default_cols, cfg, shape, estimator=est, **lk)
        log(f"  {c.name:<22} estimator  {est:<20} F1 {out['estimator'][est]['valid_f1']:.4f}")
    if valid_truth is not None:
        for card in CARDS:
            out["cardinality"][card] = evaluate(table, default_cols, cfg, shape, cardinality=card, truth_valid=valid_truth)
            log(f"  {c.name:<22} cardinality {card:<19} F1 {out['cardinality'][card]['valid_f1']:.4f}")
    out["wall_s"] = round(time.time() - t0, 1)
    return out


# --- driver ------------------------------------------------------------------------------------------------------------
def eligible(key: str, spark_version: str) -> list[str] | None:
    """Choices that may be a DEFAULT. D07 (Laurent, 2026-09-19): no default path may depend on Jaro-Winkler, a UDF
    before Spark 4.3 — so on 4.1 / 4.2 the string-similarity default is chosen among the built-in choices only. The
    unconstrained best is still reported; the Spark 4.3 watcher (tools/spark43_watch.py) triggers the re-decision."""
    if key == "features.string_similarity" and not spark_at_least(spark_version, 4, 3):
        return ["levenshtein"]
    return None


def winner(per_corpus: dict, metric: str, current: str, tie_key=None, allowed=None) -> tuple[str, dict]:
    choices = list(next(iter(per_corpus.values()))["choices"].keys())
    mean = {ch: float(np.mean([pc["choices"][ch][metric] for pc in per_corpus.values()])) for ch in choices}
    pool = [ch for ch in choices if allowed is None or ch in allowed]
    best = max(mean[ch] for ch in pool)
    tied = [ch for ch in pool if abs(mean[ch] - best) < 1e-9]
    if current in tied:
        w = current
    elif tie_key:
        w = min(tied, key=tie_key)
    else:
        w = tied[0]
    return w, {ch: round(v, 4) for ch, v in mean.items()}


def run(only: str | None) -> None:
    rt = Runtime(config.build({"storage": {"root": str(corpora.DATA / "runs" / "methods")},
                               "runtime": {"cores": 8, "shuffle_partitions": 16}}))
    res = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    res.setdefault("comparisons", {})
    res["selected_on"] = "validation"
    loaded = {n: (corpora.LOADERS[n]() if n != "febrl4_half_unmatched" else corpora.febrl4_half_unmatched()) for n in CORPORA}
    if only in (None, "candidates"):
        per = {}
        for n in CORPORA:
            per[n] = compare_candidates(rt, loaded[n])
            rt.close()
        props = lambda m: np.mean([per[n]["choices"][m]["proposals"] for n in per])
        w, mean = winner(per, "recall_at_budget", DEFAULTS["candidates"]["method"], tie_key=props)
        res["comparisons"]["candidates.method"] = {
            "metric": "recall_at_budget", "per_corpus": per, "mean": mean, "winner": w,
            "budget": {n: f"{per[n]['budget_per_left']} pairs per left record" for n in per}, "union_of": UNION_OF}
        res.setdefault("winners", {})["candidates.method"] = w
        save(res, rt)
    if only in (None, "downstream"):
        cand = res["winners"]["candidates.method"]
        per = {n: downstream(rt, loaded[n], cand) for n in CORPORA}
        for key, part, choices, cur in (("features.string_similarity", "string_similarity", SIMS, DEFAULTS["features"]["string_similarity"]),
                                        ("matcher.estimator", "estimator", ESTS, DEFAULTS["matcher"]["estimator"]),
                                        ("decision.cardinality", "cardinality", CARDS, DEFAULTS["decision"]["cardinality"])):
            pc = {n: {"choices": per[n][part]} for n in per if per[n][part]}
            res["comparisons"][key] = {"metric": "valid_f1", "per_corpus": pc}
        res["candidate_method_used_downstream"] = cand
        decide(res, rt.caps.spark_version)
        save(res, rt)
    rt.close(stop=True)


def decide(res: dict, spark_version: str) -> None:
    """Winners from the recorded comparisons (no Spark needed): highest mean among the choices eligible as a default,
    ties keep the current default."""
    current = {"features.string_similarity": DEFAULTS["features"]["string_similarity"],
               "matcher.estimator": DEFAULTS["matcher"]["estimator"],
               "decision.cardinality": DEFAULTS["decision"]["cardinality"]}
    for key, cur in current.items():
        block = res["comparisons"].get(key)
        if not block:
            continue
        allowed = eligible(key, spark_version)
        w, mean = winner(block["per_corpus"], "valid_f1", cur, allowed=allowed)
        best, _ = winner(block["per_corpus"], "valid_f1", cur)
        block.update({"mean": mean, "winner": w, "best_unconstrained": best,
                      "eligible_as_default": allowed or list(mean)})
        res.setdefault("winners", {})[key] = w


def save(res, rt, spark_version=None):
    res["meta"] = {"generated": datetime.datetime.now().isoformat(timespec="seconds"),
                   "spark": spark_version or rt.caps.spark_version, "bootstrap": 1000}
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(strip(res), indent=1) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--only", choices=["candidates", "downstream"])
    sub.add_parser("render")
    sub.add_parser("decide", help="recompute the winners from the recorded results (no Spark)")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.only)
    if a.cmd == "decide":
        res = json.loads(RESULTS.read_text())
        decide(res, res["meta"]["spark"])
        RESULTS.write_text(json.dumps(res, indent=1) + "\n")
    from render_methods import render
    render(RESULTS, HERE / "METHODS.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
