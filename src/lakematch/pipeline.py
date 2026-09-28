"""`lakematch run`: quality gate -> entity view -> candidates -> features -> labels -> train -> score -> links.

On the laptop this is one process. On Databricks the lazy half (gate, entity, candidates, features, scoring, links)
becomes Spark Declarative Pipelines flows and the rest job tasks (ZR-6); the functions called here are the same.
Outputs under storage.root: links/ (Parquet), quarantine/<side>/ when rows were quarantined, run_summary.json.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from pyspark.sql import DataFrame, functions as F

from . import candidates, decision, entity, evaluate, features, labels, matcher, quality
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


def run(cfg: Config, root: Path | None = None, t_process: float | None = None, rt: Runtime | None = None) -> dict:
    t_start = t_process or time.time()
    problems = cfg.runnable_problems()
    if problems:
        raise SystemExit("config names choices that have not landed yet:\n  " + "\n  ".join(problems))
    if root is not None:
        cfg.data["storage"]["root"] = str(root)
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
        sides = {}
        for side in ("left", "right"):
            spec = cfg.get(f"inputs.{side}")
            raw = read_table(spark, cfg, spec)
            valid, quarantined = gate.apply_and_split(raw, quality.input_checks(cfg, spec["id"], side))
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
        threshold = decision.pick_threshold(matcher.score(model, valid_lab), cfg)
        scored = matcher.score(model, pairs)
        linked = rt.materialize(decision.links(scored, threshold, cfg).select("l_id", "r_id", "p"), "links")
        linked.write.mode("overwrite").parquet(str(out_dir / "links"))
        summary["decision"] = {"threshold": threshold, "links": linked.count()}

        truth = labels.truth_pairs(spark, cfg)
        if truth is not None:
            summary["evaluation"] = evaluate.pairwise(linked, truth, cand, lab.select("l_id").distinct())
            summary["evaluation"]["nearest_neighbour_baseline"] = evaluate.trivial_baseline(cand, truth)
    finally:
        rt.close()
    now = time.time()
    summary["timing_s"] = {"session_start": round(t_session - t_start, 1), "compute": round(now - t_session, 1),
                           "wall_including_session_start": round(now - t_start, 1)}
    summary["outputs"] = {"links": str(out_dir / "links")}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
