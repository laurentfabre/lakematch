"""`lakematch run`: quality gate -> entity view -> candidates -> features -> labels -> train -> score -> links ->
clusters -> identity (mdm_id, crosswalk, merge/split log).

On the laptop this is one process. On Databricks the lazy half (gate, entity, candidates, features, scoring, links)
becomes Spark Declarative Pipelines flows and the rest job tasks (ZR-6); the functions called here are the same.
Outputs under storage.root: links/ (Parquet), identity/crosswalk.json (record key -> mdm_id, read back by the next
run to keep ids), identity/log.jsonl (appended merge/split events), quarantine/<side>/ when rows were quarantined,
run_summary.json.
"""
from __future__ import annotations

import json
import logging
import time
from collections import Counter
from pathlib import Path

from pyspark.sql import DataFrame, functions as F

from . import candidates, cluster, decision, entity, evaluate, features, identity, labels, matcher, quality
from .config import Config, log_paid_features
from .io import read_table
from .runtime import Runtime

log = logging.getLogger("lakematch")


def _prefixed(df: DataFrame, prefix: str, id_alias: str) -> DataFrame:
    return df.select([F.col(c).alias(id_alias if c == "id" else f"{prefix}{c}") for c in df.columns])


def entity_sides(rt: Runtime, cfg: Config, left_raw: DataFrame, right_raw: DataFrame, id_column: str = "id"):
    """Entity view + record-level features for both sides, pinned (the embedding UDF, if any, runs here once)."""
    left, right = entity.prepare(left_raw, cfg, id_column), entity.prepare(right_raw, cfg, id_column)
    left, right = features.prepare_sides(left, right, cfg)
    return rt.materialize(left, "left"), rt.materialize(right, "right")


def pair_features(rt: Runtime, cfg: Config, left: DataFrame, right: DataFrame, pairs: DataFrame,
                  keep: tuple[str, ...] = ()) -> tuple[DataFrame, list[str]]:
    """Comparison vectors for given pairs (l_id, r_id, ...) over entity sides from `entity_sides`: the pair-corpus
    entry point (labelled pair benchmarks, a review queue). Columns of `pairs` named in `keep` are carried along."""
    joined = pairs.join(_prefixed(left, "l_", "l_id"), "l_id").join(_prefixed(right, "r_", "r_id"), "r_id")
    has_cand = "cand_score" in keep
    out, cols = features.compare(joined, cfg, candidates=has_cand)
    carry = [c for c in keep if c not in cols]
    return rt.materialize(out.select("l_id", "r_id", *carry, *cols), "pair_features"), cols


def pair_scorer(rt: Runtime, cfg: Config, left: DataFrame, right: DataFrame, model, cand: DataFrame):
    """p for arbitrary (l_id, r_id) pairs, one Spark job per call: verified merge's representative pairs. A candidate
    pair keeps its candidate columns; any other pair gets the shared ranking score, cand_rank = k + 1 (just outside
    the budget) and cand_gap = its left record's best candidate score minus its own."""
    spark = rt.spark
    k = cfg.get("candidates.k")
    cand_cols = cand.select("l_id", "r_id", "cand_score", F.col("cand_rank").cast("int").alias("cand_rank"), "cand_gap")
    best = cand.groupBy("l_id").agg(F.max("cand_score").alias("_best"))

    def score(pairs: list[tuple[str, str]]) -> dict[tuple[str, str], float]:
        if not pairs:
            return {}
        asked = spark.createDataFrame(pairs, "l_id string, r_id string").distinct()
        known = asked.join(cand_cols, ["l_id", "r_id"])
        new = asked.join(cand_cols.select("l_id", "r_id"), ["l_id", "r_id"], "left_anti")
        new = (candidates.rescore(new, left, right, cfg).join(best, "l_id", "left")
               .select("l_id", "r_id", "cand_score", F.lit(k + 1).cast("int").alias("cand_rank"),
                       F.greatest(F.coalesce(F.col("_best"), F.col("cand_score")) - F.col("cand_score"),
                                  F.lit(0.0)).alias("cand_gap")))
        table, _ = pair_features(rt, cfg, left, right, known.unionByName(new), keep=("cand_score", "cand_rank", "cand_gap"))
        return {(r.l_id, r.r_id): float(r.p) for r in matcher.score(model, table).select("l_id", "r_id", "p").collect()}
    return score


def resolve(cfg: Config, left_ids: list[str], right_ids: list[str] | None, links: list[tuple[str, str, float]],
            threshold: float, score=None, method: str | None = None) -> tuple[dict[str, str], dict]:
    """Links -> clusters (`cluster.method`). Dedupe (`right_ids` None): record keys are the ids. Linkage: record keys are
    "left:<id>" / "right:<id>", and verified merge only scores left-right representative pairs (what the model knows)."""
    method = method or cfg.require("cluster.method")
    kw = {"representatives": cfg.get("cluster.representatives"), "max_rounds": cfg.get("cluster.max_rounds")}
    if right_ids is None:
        return cluster.run(method, left_ids, links, threshold, score=score, **kw)
    nodes = [f"left:{i}" for i in left_ids] + [f"right:{i}" for i in right_ids]
    edges = [(f"left:{a}", f"right:{b}", p) for a, b, p in links]

    def keyed_score(pairs):
        got = score([(a[5:], b[6:]) for a, b in pairs])
        return {(f"left:{a}", f"right:{b}"): p for (a, b), p in got.items()}
    allowed = lambda x, y: x[:5] != y[:5]
    return cluster.run(method, nodes, edges, threshold, score=keyed_score if score else None, allowed=allowed, **kw)


def run(cfg: Config, root: Path | None = None, t_process: float | None = None, rt: Runtime | None = None) -> dict:
    t_start = t_process or time.time()
    problems = cfg.runnable_problems()
    if problems:
        raise SystemExit("config names choices that have not landed yet:\n  " + "\n  ".join(problems))
    if root is not None:
        # --root redirects every output, the model store included: a scratch run never becomes the accepted model
        cfg.data["storage"]["root"] = str(root)
        if not cfg.get("mlflow.registry") and cfg.get("mlflow.tracking_uri").startswith("sqlite:///"):
            cfg.data["mlflow"]["tracking_uri"] = f"sqlite:///{Path(root) / 'mlflow.db'}"
            cfg.data["mlflow"]["pointer"] = str(Path(root) / "models" / "current.json")
    out_dir = cfg.path(cfg.get("storage.root"))
    log_paid_features(cfg)
    features.check(cfg)

    rt = rt or Runtime(cfg)
    spark = rt.spark
    t_session = time.time()
    summary: dict = {"runtime": {"remote": rt.remote, "spark": rt.caps.spark_version,
                                 "materialize": rt.strategy()},
                     "paid_features_enabled": cfg.enabled_paid_features(),
                     "methods": {k: cfg.get(k) for k in ("candidates.method", "features.string_similarity",
                                                         "features.multi_token", "matcher.estimator",
                                                         "decision.cardinality", "quality.engine")}}
    try:
        gate = quality.engine(cfg)
        sides, raws = {}, {}
        for side in ("left", "right"):
            spec = cfg.get(f"inputs.{side}")
            raw = raws[side] = read_table(spark, cfg, spec)
            valid, quarantined = gate.split(raw, quality.input_specs(cfg, spec["id"], side))
            n_bad = quarantined.count()
            summary.setdefault("quarantined", {})[side] = n_bad
            if n_bad:
                quarantined.write.mode("overwrite").parquet(str(out_dir / "quarantine" / side))
            sides[side] = entity.prepare(valid, cfg, spec["id"])
        left, right = features.prepare_sides(sides["left"], sides["right"], cfg)
        left, right = rt.materialize(left, "left"), rt.materialize(right, "right")

        seed_labels = None
        uses = {cfg.get("candidates.method"), *cfg.get("candidates.union_of")}
        if "learned_blocker" in uses:
            # the blocker learns from labelled matches: label a gram_topk seed set first (same label source)
            seed = rt.materialize(candidates.gram_topk(left, right, cfg), "seed_candidates")
            seed_labels = rt.materialize(labels.labelled(spark, seed, cfg, left, right), "seed_labels")
        cand = rt.materialize(candidates.generate(left, right, cfg, seed_labels), "candidates")
        pairs = (cand.join(_prefixed(left, "l_", "l_id"), "l_id").join(_prefixed(right, "r_", "r_id"), "r_id"))
        pairs, feature_cols = features.compare(pairs, cfg)
        pairs = rt.materialize(pairs.select("l_id", "r_id", *feature_cols), "features")
        summary["candidates"] = {"pairs": pairs.count(), "k": cfg.get("candidates.k"),
                                 "budget": candidates.budget_note(cfg)}
        summary["features"] = feature_cols

        llm_usage: dict = {}
        lab = rt.materialize(labels.labelled(spark, pairs, cfg, left, right, llm_usage), "labels")
        if llm_usage:
            summary["llm_labeller"] = llm_usage
        train, valid_lab = labels.split(lab, cfg)
        summary["labels"] = {"train": train.count(), "train_matches": train.filter("label = 1").count(),
                             "validation": valid_lab.count()}
        model = matcher.train(train, feature_cols, cfg)
        valid_scored = matcher.score(model, valid_lab)
        threshold = decision.pick_threshold(valid_scored, cfg)
        scored = matcher.score(model, pairs)
        linked = rt.materialize(decision.links(scored, threshold, cfg).select("l_id", "r_id", "p"), "links")
        linked.write.mode("overwrite").parquet(str(out_dir / "links"))
        summary["decision"] = {"threshold": threshold, "links": linked.count()}

        # clusters and identity: the previous crosswalk (if any) carries the ids over; the log explains every change
        ident_dir = out_dir / "identity"
        left_ids = [r.id for r in left.select("id").collect()]
        right_ids = [r.id for r in right.select("id").collect()]
        link_rows = [(r.l_id, r.r_id, float(r.p)) for r in linked.collect()]
        scorer = pair_scorer(rt, cfg, left, right, model, cand)
        clusters, cstats = resolve(cfg, left_ids, right_ids, link_rows, threshold, score=scorer)
        prev_path = ident_dir / "crosswalk.json"
        previous = json.loads(prev_path.read_text()) if prev_path.exists() else None
        run_id = time.strftime("%Y%m%dT%H%M%S")
        crosswalk, events = identity.assign(clusters, previous, run=run_id)
        ok, problems = identity.reconcile(previous or {}, crosswalk, events)
        if not ok:
            raise RuntimeError("identity log does not reconcile: " + "; ".join(problems))
        ident_dir.mkdir(parents=True, exist_ok=True)
        prev_path.write_text(json.dumps(crosswalk, sort_keys=True) + "\n")
        with (ident_dir / "log.jsonl").open("a") as fh:
            for e in events:
                fh.write(json.dumps(e, sort_keys=True) + "\n")
        summary["identity"] = {"method": cfg.get("cluster.method"), "entities": len(set(crosswalk.values())),
                               "records": len(crosswalk), "events": dict(sorted(
                                   Counter(e["event"] for e in events).items())),
                               "cluster_stats": cstats, "reconciles": ok}

        truth = labels.truth_pairs(spark, cfg)
        if truth is not None:
            summary["evaluation"] = evaluate.pairwise(linked, truth, cand, lab.select("l_id").distinct())
            summary["evaluation"]["nearest_neighbour_baseline"] = evaluate.trivial_baseline(cand, truth)

        if cfg.get("mlflow.enabled"):
            from . import tracking                       # MLflow is imported only when a run logs
            t_ml = time.time()
            summary["mlflow"] = tracking.log_run(
                rt, cfg, run_name=run_id, model=model, feature_cols=feature_cols, threshold=threshold, lab=lab,
                train=train, valid_scored=valid_scored, scored=scored, linked=linked, truth=truth, raw_inputs=raws,
                summary=summary)
            summary["mlflow"]["seconds"] = round(time.time() - t_ml, 1)
    finally:
        rt.close()
    now = time.time()
    summary["timing_s"] = {"session_start": round(t_session - t_start, 1), "compute": round(now - t_session, 1),
                           "wall_including_session_start": round(now - t_start, 1)}
    summary["outputs"] = {"links": str(out_dir / "links"), "crosswalk": str(out_dir / "identity" / "crosswalk.json"),
                          "identity_log": str(out_dir / "identity" / "log.jsonl")}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
