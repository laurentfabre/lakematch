#!/usr/bin/env python3
"""ZR-2 ablation: what each feature family adds, what the UDF features add, and whether embeddings pay (D12).

For every corpus the full comparison vector (all families, the UDF features, embeddings where relevant) is computed
once; each variant then trains the default estimator on a subset of its columns, picks the threshold on VALID and is
scored on TEST. Every F1 carries a 95 % bootstrap interval (1 000 resamples) and every variant a paired interval on
its difference from the reference row (same resamples).

    febrl4_half_unmatched[_no_soc_sec_id]  linkage: gram_topk k=5 candidates, 1 000 labelled candidate pairs drawn in
                                           xxhash order (75 % train / 25 % valid by left id), test = every candidate
                                           of the left records that carry no label, one-to-one links; bootstrap over
                                           those left records
    bpid, abt_buy                          labelled pairs, fixed splits (see corpora.py); bootstrap over test pairs
    leipzig_affiliations                   dedupe: gram_topk k=10 within the corpus, labels from the gold clusters,
                                           split 60/20/20 by pair hash; bootstrap over test pairs

Embeddings (organisation and title fields): two local model2vec models are tried on Leipzig (organisation) and
Abt-Buy (title); the model is chosen on VALID F1, and D12 keeps the feature on by default only if the chosen model's
TEST F1 difference is positive on both corpora. Cost is the model's encode time per 10^5 records on this laptop.

    python bench/ablation.py run [--corpus NAME ...]     # writes bench/results/ablation.json (merged per corpus)
    python bench/ablation.py render                      # bench/ABLATION.md from the JSON
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

from pyspark.sql import functions as F  # noqa: E402

from lakematch import candidates, config, decision, embeddings, labels, matcher  # noqa: E402
from lakematch.features import active_families, family_of  # noqa: E402
from lakematch.pipeline import entity_sides, pair_features  # noqa: E402
from lakematch.runtime import Runtime  # noqa: E402

RESULTS = HERE / "results" / "ablation.json"
MODELS = ["minishlab/potion-base-8M", "minishlab/potion-base-32M"]
UDF_FAMILIES = ("jaro_winkler", "affine_gap")
B, SEED = 1000, 0


def log(msg: str) -> None:
    print(f"[{datetime.datetime.now():%H:%M:%S}] {msg}", flush=True)


# --- statistics ------------------------------------------------------------------------------------------------------
def f1_counts(tp, fp, fn):
    d = 2 * tp + fp + fn
    return np.where(d > 0, 2 * tp / np.where(d > 0, d, 1), 0.0)


def boot_idx(n: int) -> np.ndarray:
    return np.random.default_rng(SEED).integers(0, n, size=(B, n))


def summarise(tp, fp, fn, idx, ref=None) -> dict:
    """tp/fp/fn: per-unit 0/1 arrays (a test pair, or a held-out left record); idx: shared bootstrap indices."""
    tp, fp, fn = map(np.asarray, (tp, fp, fn))
    point = float(f1_counts(tp.sum(), fp.sum(), fn.sum()))
    boots = f1_counts(tp[idx].sum(1), fp[idx].sum(1), fn[idx].sum(1))
    out = {"f1": round(point, 4), "ci95": [round(float(np.percentile(boots, 2.5)), 4),
                                           round(float(np.percentile(boots, 97.5)), 4)],
           "precision": round(float(tp.sum() / max(tp.sum() + fp.sum(), 1)), 4),
           "recall": round(float(tp.sum() / max(tp.sum() + fn.sum(), 1)), 4), "_boots": boots}
    if ref is not None:
        d = boots - ref["_boots"]
        out["delta"] = round(point - ref["f1"], 4)
        out["delta_ci95"] = [round(float(np.percentile(d, 2.5)), 4), round(float(np.percentile(d, 97.5)), 4)]
    return out


# --- variants --------------------------------------------------------------------------------------------------------
def variants(cols: list[str], default_fams: set[str], extra: dict[str, list[str]] | None = None):
    """(name, columns) — the reference first. `extra` adds named column groups on top of the reference."""
    fam = {c: family_of(c) for c in cols}
    ref = [c for c in cols if fam[c] in default_fams]
    out = [("reference", ref)]
    for f in sorted({fam[c] for c in ref}):
        out.append((f"- {f}", [c for c in ref if fam[c] != f]))
    udf = {f: [c for c in cols if fam[c] == f] for f in UDF_FAMILIES}
    for f, extra_cols in udf.items():
        if extra_cols:
            out.append((f"+ {f} (UDF)", ref + extra_cols))
    if all(udf.values()):
        out.append(("+ both UDF features", ref + udf["jaro_winkler"] + udf["affine_gap"]))
    for name, extra_cols in (extra or {}).items():
        out.append((name, ref + extra_cols))
    return out


def base_cfg(corpus, **features):
    feats = {"string_similarity": "both", "udf_features": True,
             "multi_token": ["idf_token_cosine", "gram_overlap", "monge_elkan_token", "affine_gap_udf"],
             "embeddings": {"provider": "none"}}
    feats.update(features)
    return config.build({"entity": {"name": corpus.name, "fields": corpus.fields}, "features": feats,
                         "candidates": {"k": 5}, "storage": {"root": str(corpora.DATA / "runs" / "ablation")},
                         "runtime": {"cores": 8, "shuffle_partitions": 16}})


def default_families() -> set[str]:
    return active_families(config.build({})) - {"embedding"}


# --- pair corpora ----------------------------------------------------------------------------------------------------
def fit_eval_pairs(table, cols, cfg, idx, ref=None, splits=None):
    train, valid = splits
    model = matcher.train(train, cols, cfg)
    vs = matcher.score(model, valid).select("p", "label")
    t = decision.pick_threshold(vs, cfg)
    vrows = vs.collect()
    vp = np.array([r.p >= t for r in vrows]); vy = np.array([r.label == 1.0 for r in vrows])
    valid_f1 = float(f1_counts((vp & vy).sum(), (vp & ~vy).sum(), (~vp & vy).sum()))
    rows = matcher.score(model, table.filter("split = 'test'")).select("l_id", "r_id", "p", "label") \
                  .orderBy("l_id", "r_id").collect()
    pred = np.array([r.p >= t for r in rows]); y = np.array([r.label == 1.0 for r in rows])
    res = summarise(pred & y, pred & ~y, ~pred & y, idx, ref)
    res["threshold"] = t
    res["valid_f1"] = round(valid_f1, 4)
    if ref is None:
        res["top_features"] = top_features(model, cols)
    return res


def top_features(model, cols, n=6) -> list[list]:
    """The fitted model's largest importances (tree ensembles) — what the reference actually leans on."""
    est = model.stages[-1]
    if not hasattr(est, "featureImportances"):
        return []
    imp = est.featureImportances.toArray()
    return [[c, round(float(v), 3)] for v, c in sorted(zip(imp, cols), reverse=True)[:n] if v > 0.001]


def run_pair_table(name, table, cols, cfg, extra=None, default_fams=None):
    train, valid = table.filter("split = 'train'"), table.filter("split = 'valid'")
    n_test = table.filter("split = 'test'").count()
    idx = boot_idx(n_test)
    rows, ref = [], None
    for vname, vcols in variants(cols, default_fams or default_families(), extra):
        t0 = time.time()
        res = fit_eval_pairs(table, vcols, cfg, idx, ref, (train, valid))
        if ref is None:
            ref = res
        rows.append({"variant": vname, "n_features": len(vcols), **res, "fit_s": round(time.time() - t0, 1)})
        log(f"  {name:<24} {vname:<34} F1 {res['f1']:.4f} {res['ci95']}  Δ {res.get('delta', 0):+.4f}")
    return rows, n_test


def pair_corpus(rt, corpus, embed_models=()):
    cfg = base_cfg(corpus)
    spark = rt.spark
    left, right = spark.createDataFrame(corpus.left), spark.createDataFrame(corpus.right)
    t0 = time.time()
    L, R = entity_sides(rt, cfg, left, right)
    pairs = spark.createDataFrame(corpus.pairs)
    table, cols = pair_features(rt, cfg, L, R, pairs, keep=("label", "split"))
    log(f"{corpus.name}: {table.count()} pairs, {len(cols)} feature columns in {time.time() - t0:.0f} s")
    extra, emb_info = embedding_columns(rt, corpus, cfg, left, right, pairs) if embed_models else ({}, None)
    if extra:
        for name, (etable, ecols) in extra.items():
            table = table.join(etable, ["l_id", "r_id"])
        extra = {name: ecols for name, (etable, ecols) in extra.items()}
        table = rt.materialize(table, "with_embeddings")
    rows, n_test = run_pair_table(corpus.name, table, cols, cfg, extra)
    return {"kind": corpus.kind, "test_units": n_test, "unit": "pair", "rows": rows, "notes": corpus.notes,
            "embedding_models": emb_info}


def embedding_columns(rt, corpus, cfg, left, right, pairs):
    """Per model: the ebc_ columns (renamed per model) and the model's encode cost."""
    out, info = {}, []
    texts = []
    for f in cfg.fields_of_type("organisation", "title"):
        texts += [t for t in list(corpus.left[f]) + list(corpus.right[f]) if t]
    for model in MODELS:
        ecfg = base_cfg(corpus, exclude=[f for f in config.FAMILIES if f != "embedding"],
                        string_similarity="levenshtein", multi_token=[], udf_features=False,
                        embeddings={"provider": "local", "model": model, "fields_of_type": ["organisation", "title"]})
        provider = embeddings.resolve(ecfg)
        provider.encode(texts[:50])                                          # load before timing
        t0 = time.time(); provider.encode(texts); enc = time.time() - t0
        L, R = entity_sides(rt, ecfg, left, right)
        etable, ecols = pair_features(rt, ecfg, L, R, pairs)
        tag = model.split("/")[-1]
        renamed = {c: f"ebc_{tag.replace('-', '')}__{c[4:]}" for c in ecols}
        etable = etable.select("l_id", "r_id", *[F.col(c).alias(renamed[c]) for c in ecols])
        out[f"+ embedding {tag}"] = (etable, list(renamed.values()))
        dims = int(provider.encode(["x"]).shape[1])
        info.append({"model": model, "dims": dims, "texts": len(texts),
                     "encode_s_per_1e5_records": round(enc / max(len(texts), 1) * 1e5, 2)})
        log(f"  {corpus.name}: {model} dims {dims}, {info[-1]['encode_s_per_1e5_records']} s per 10^5 records")
    return out, info


# --- linkage (FEBRL4) ------------------------------------------------------------------------------------------------
def linkage_corpus(rt, corpus, n_labels=1000):
    cfg = base_cfg(corpus)
    spark = rt.spark
    t0 = time.time()
    L, R = entity_sides(rt, cfg, spark.createDataFrame(corpus.left), spark.createDataFrame(corpus.right))
    cand = rt.materialize(candidates.generate(L, R, cfg), "cand")
    truth = spark.createDataFrame(corpus.truth).select("l_id", "r_id")
    table, cols = pair_features(rt, cfg, L, R, cand, keep=("cand_score", "cand_rank", "cand_gap"))
    table = table.join(truth.withColumn("label", F.lit(1.0)), ["l_id", "r_id"], "left").fillna(0.0, ["label"])
    table = rt.materialize(table, "linkage_table")
    n_true = corpus.truth.shape[0]
    cand_recall = table.filter("label = 1").count() / n_true
    lab = table.orderBy(F.xxhash64("l_id", "r_id"), "l_id", "r_id").limit(n_labels)
    lab = rt.materialize(lab, "labels")
    train, valid = labels.split(lab, cfg)
    anchors = lab.select("l_id").distinct()
    held = table.join(anchors, "l_id", "left_anti")
    held_left = sorted(r.id for r in L.join(anchors.withColumnRenamed("l_id", "id"), "id", "left_anti").select("id").collect())
    true_of = dict(corpus.truth[["l_id", "r_id"]].itertuples(index=False))
    idx = boot_idx(len(held_left))
    log(f"{corpus.name}: {table.count()} candidate pairs (recall {cand_recall:.4f}), {len(cols)} features, "
        f"{len(held_left)} held-out left records, {time.time() - t0:.0f} s")
    rows, ref = [], None
    for vname, vcols in variants(cols, default_families()):
        t1 = time.time()
        model = matcher.train(train, vcols, cfg)
        t = decision.pick_threshold(matcher.score(model, valid), cfg)
        links = decision.links(matcher.score(model, held), t, cfg).select("l_id", "r_id").collect()
        pred = {r.l_id: r.r_id for r in links}
        tp = np.array([pred.get(a) is not None and pred.get(a) == true_of.get(a) for a in held_left])
        fp = np.array([pred.get(a) is not None and pred.get(a) != true_of.get(a) for a in held_left])
        fn = np.array([true_of.get(a) is not None and pred.get(a) != true_of.get(a) for a in held_left])
        res = summarise(tp, fp, fn, idx, ref)
        res["threshold"] = t
        if ref is None:
            res["top_features"] = top_features(model, vcols)
            ref = res
        rows.append({"variant": vname, "n_features": len(vcols), **res, "fit_s": round(time.time() - t1, 1)})
        log(f"  {corpus.name:<24} {vname:<34} F1 {res['f1']:.4f} {res['ci95']}  Δ {res.get('delta', 0):+.4f}")
    return {"kind": corpus.kind, "test_units": len(held_left), "unit": "held-out left record", "rows": rows,
            "candidate_recall": round(cand_recall, 4), "labels": n_labels, "notes": corpus.notes}


# --- dedupe (Leipzig) ------------------------------------------------------------------------------------------------
def dedupe_pairs(rt, corpus):
    """Candidate pairs within the corpus (k=10, self pairs and mirror duplicates removed), labelled from clusters."""
    cfg = config.build({"entity": {"fields": corpus.fields}, "candidates": {"k": 10},
                        "features": {"embeddings": {"provider": "none"}}})
    spark = rt.spark
    recs = spark.createDataFrame(corpus.left)
    L, R = entity_sides(rt, cfg, recs, recs)
    cand = candidates.generate(L, R, cfg).filter("l_id != r_id")
    a = F.least("l_id", "r_id"); b = F.greatest("l_id", "r_id")
    pairs = cand.select(a.alias("l_id"), b.alias("r_id")).distinct()
    cl = spark.createDataFrame(corpus.truth)
    pairs = (pairs.join(cl.withColumnRenamed("id", "l_id").withColumnRenamed("cluster", "cl"), "l_id")
                  .join(cl.withColumnRenamed("id", "r_id").withColumnRenamed("cluster", "cr"), "r_id")
                  .select("l_id", "r_id", (F.col("cl") == F.col("cr")).cast("double").alias("label")))
    bucket = F.pmod(F.xxhash64(F.concat_ws("|", "l_id", "r_id")), F.lit(10))
    pairs = pairs.withColumn("split", F.when(bucket < 6, "train").when(bucket < 8, "valid").otherwise("test"))
    pdf = pairs.orderBy("l_id", "r_id").toPandas()
    corpus.pairs = pdf
    corpus.notes = corpus.notes + [f"{len(pdf)} candidate pairs, {int(pdf.label.sum())} true"]
    return corpus


# --- main ------------------------------------------------------------------------------------------------------------
def run(names: list[str]) -> None:
    rt = Runtime(config.build({"storage": {"root": str(corpora.DATA / "runs" / "ablation")},
                               "runtime": {"cores": 8, "shuffle_partitions": 16}}))
    results = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    for name in names:
        t0 = time.time()
        if name == "febrl4_half_unmatched":
            res = {"all_fields": linkage_corpus(rt, corpora.febrl4_half_unmatched()),
                   "ssn_hidden": linkage_corpus(rt, corpora.febrl4_half_unmatched(("soc_sec_id",)))}
        elif name == "bpid":
            res = pair_corpus(rt, corpora.bpid())
        elif name == "abt_buy":
            res = pair_corpus(rt, corpora.abt_buy(), embed_models=MODELS)
        elif name == "leipzig_affiliations":
            res = pair_corpus(rt, dedupe_pairs(rt, corpora.leipzig_affiliations()), embed_models=MODELS)
        else:
            raise SystemExit(f"unknown corpus {name}")
        res["wall_s"] = round(time.time() - t0, 1)
        results[name] = strip(res)
        results["meta"] = {"generated": datetime.datetime.now().isoformat(timespec="seconds"),
                           "spark": rt.caps.spark_version, "estimator": "gbt (defaults)", "bootstrap": B,
                           "reference_families": sorted(default_families())}
        results["embedding_decision"] = decide_embeddings(results)
        RESULTS.parent.mkdir(parents=True, exist_ok=True)
        RESULTS.write_text(json.dumps(results, indent=1) + "\n")
        rt.close()
    rt.close(stop=True)


def strip(obj):
    if isinstance(obj, dict):
        return {k: strip(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [strip(v) for v in obj]
    return obj


def decide_embeddings(results: dict) -> dict:
    corp = [c for c in ("leipzig_affiliations", "abt_buy") if c in results]
    if len(corp) < 2:
        return {"kept_on_by_default": None, "reason": "waiting for both corpora"}
    score = {}
    for m in MODELS:
        tag = f"+ embedding {m.split('/')[-1]}"
        rows = [next(r for r in results[c]["rows"] if r["variant"] == tag) for c in corp]
        score[m] = {"test_delta": {c: r["delta"] for c, r in zip(corp, rows)},
                    "test_delta_ci95": {c: r["delta_ci95"] for c, r in zip(corp, rows)}}
    for m in MODELS:                                    # the model is chosen on VALID F1, never on TEST

        tag = f"+ embedding {m.split('/')[-1]}"
        score[m]["valid_f1_mean"] = round(float(np.mean([next(r for r in results[c]["rows"] if r["variant"] == tag)
                                                          ["valid_f1"] for c in corp])), 4)
    winner = max(MODELS, key=lambda m: (score[m]["valid_f1_mean"], -MODELS.index(m)))
    kept = all(d > 0 for d in score[winner]["test_delta"].values())
    return {"winner_model": winner, "chosen_on": "mean VALID F1 over leipzig_affiliations and abt_buy",
            "models": score, "kept_on_by_default": kept,
            "rule": "D12: on by default for organisation and title fields only if the chosen model's TEST F1 "
                    "difference is positive on both corpora"}


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--corpus", nargs="*", default=["leipzig_affiliations", "abt_buy", "bpid", "febrl4_half_unmatched"])
    sub.add_parser("render")
    args = ap.parse_args()
    if args.cmd == "run":
        run(args.corpus)
    from render_ablation import render
    render(RESULTS, HERE / "ABLATION.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
