"""Job tasks of the Databricks deployment (ZR-6): the steps that need actions, around the one pipeline
(pipelines/flows.py). The bundle (bundle/databricks.yml) runs them in this order:

    plan      schema hygiene (predictive optimisation per its paid switch), then the data-dependent candidate choices
              (candidates.resolve_plan) -> <storage.root>/candidate_plan.json
    [pipeline refresh: valid, quarantine, entity, candidates, features]
    train     labels -> MLlib fit -> threshold -> tracking.log_run: composite model, UC registry, @alias moved, the
              compiled scoring expression handed to the pipeline (<storage.root>/champion.json); labels -> lm_labels
    [pipeline refresh: scores, links]
    cluster   checks the links carry the version @alias names, clusters (cluster.method, scoring new pairs with the
              same compiled expression), identity (mdm_id, crosswalk, merge/split log) -> lm_crosswalk, evaluation
              against the truth set -> <storage.root>/run_summary.json
    quality   the gate's two engines on the same inputs: DQX (what the pipeline ran) and native must give the same
              split, and the seeded bad rows must be exactly the quarantined ones -> <storage.root>/quality.json
    explain   the physical plan of every stage on this compute (Photon or not, per operator) -> <storage.root>/explain/

Every task: `python lakematch_task.py <task> --config <yaml>`; each writes its own JSON under storage.root.
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from collections import Counter
from pathlib import Path

from pyspark.sql import DataFrame, functions as F

from . import candidates, entity, evaluate, features, identity, labels, quality
from .config import Config, load
from .io import read_table
from .runtime import Runtime

log = logging.getLogger("lakematch")

STAGE_TABLES = ("lm_left_valid", "lm_right_valid", "lm_left_quarantine", "lm_right_quarantine", "lm_left_entity",
                "lm_right_entity", "lm_candidates", "lm_features", "lm_scores", "lm_links")


def _root(cfg: Config) -> Path:
    return Path(cfg.path(cfg.get("storage.root")))


def _table(cfg: Config, name: str) -> str:
    catalog = cfg.get("storage.catalog")
    return f"{catalog}.{name}" if catalog else name


def _write(cfg: Config, name: str, payload: dict) -> Path:
    path = _root(cfg) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return path


def _read(cfg: Config, name: str) -> dict | None:
    path = _root(cfg) / name
    return json.loads(path.read_text()) if path.exists() else None


def schema_hygiene(cfg: Config, rt: Runtime) -> dict:
    """Predictive optimisation bills as serverless jobs: off unless its paid switch is on (the brief's rule)."""
    if not cfg.get("storage.catalog"):
        return {"skipped": "no storage.catalog (a laptop run has no schema to configure)"}
    on = cfg.get("paid_features.predictive_optimization")
    stmt = f"ALTER SCHEMA {cfg.get('storage.catalog')} {'ENABLE' if on else 'DISABLE'} PREDICTIVE OPTIMIZATION"
    try:
        rt.spark.sql(stmt).collect()
        return {"statement": stmt, "ok": True}
    except Exception as e:                      # recorded, never silent: bench/serverless.py reads it
        return {"statement": stmt, "ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}


def _entity_sides(cfg: Config, rt: Runtime):
    sides = []
    for side in ("left", "right"):
        spec = cfg.get(f"inputs.{side}")
        valid, _ = quality.engine(cfg).split(read_table(rt.spark, cfg, spec), quality.input_specs(cfg, spec["id"], side))
        sides.append(entity.prepare(valid, cfg, spec["id"]))
    left, right = features.prepare_sides(sides[0], sides[1], cfg)
    return rt.materialize(left, "left"), rt.materialize(right, "right")


def task_plan(cfg: Config, rt: Runtime) -> dict:
    out = {"schema": schema_hygiene(cfg, rt)}
    left, right = _entity_sides(cfg, rt)
    seed = None
    if "learned_blocker" in candidates._methods(cfg):    # the blocker learns from labelled matches (as in run())
        seed_c = rt.materialize(candidates.gram_topk(left, right, cfg), "seed_candidates")
        seed = rt.materialize(labels.labelled(rt.spark, seed_c, cfg, left, right), "seed_labels")
    plan = candidates.resolve_plan(left, right, cfg, seed)
    if plan.get("unplannable"):
        raise ValueError(f"{plan['unplannable']} cannot run inside a pipeline flow (MLlib fit): pick another "
                         "candidates.method for the Databricks deployment")
    _write(cfg, "candidate_plan.json", plan)
    out["plan"] = plan
    return out


def task_train(cfg: Config, rt: Runtime) -> dict:
    from . import decision, matcher, tracking
    spark = rt.spark
    pairs = rt.materialize(spark.read.table(_table(cfg, "lm_features")), "features")
    left, right = spark.read.table(_table(cfg, "lm_left_entity")), spark.read.table(_table(cfg, "lm_right_entity"))
    feature_cols = [c for c in pairs.columns if c not in ("l_id", "r_id")]
    usage: dict = {}
    lab = rt.materialize(labels.labelled(spark, pairs, cfg, left, right, usage), "labels")
    lab.select("l_id", "r_id", "label").write.mode("overwrite").saveAsTable(_table(cfg, "lm_labels"))
    train, valid_lab = labels.split(lab, cfg)
    summary: dict = {"methods": {k: cfg.get(k) for k in ("candidates.method", "features.string_similarity",
                                                         "features.multi_token", "matcher.estimator",
                                                         "decision.cardinality", "quality.engine")},
                     "labels": {"train": train.count(), "train_matches": train.filter("label = 1").count(),
                                "validation": valid_lab.count()},
                     "candidates": {"pairs": pairs.count()}, "features": feature_cols}
    if usage:
        summary["llm_labeller"] = usage
    model = matcher.train(train, feature_cols, cfg)
    valid_scored = matcher.score(model, valid_lab)
    threshold = decision.pick_threshold(valid_scored, cfg)
    scored = matcher.score(model, pairs)
    linked = rt.materialize(decision.links(scored, threshold, cfg).select("l_id", "r_id", "p"), "links")
    summary["decision"] = {"threshold": threshold, "links": linked.count()}
    raws = {s: read_table(spark, cfg, cfg.get(f"inputs.{s}")) for s in ("left", "right")}
    summary["mlflow"] = tracking.log_run(
        rt, cfg, run_name=time.strftime("%Y%m%dT%H%M%S"), model=model, feature_cols=feature_cols,
        threshold=threshold, lab=lab, train=train, valid_scored=valid_scored, scored=scored, linked=linked,
        truth=labels.truth_pairs(spark, cfg), raw_inputs=raws, summary=summary, plan=_read(cfg, "candidate_plan.json"))
    if not summary["mlflow"].get("accepted"):
        raise RuntimeError(f"the run was not accepted: {summary['mlflow'].get('rejected_because')}")
    return summary


def _alias_version(cfg: Config) -> str:
    import mlflow
    from . import tracking
    tracking.configure(cfg)
    return str(mlflow.MlflowClient().get_model_version_by_alias(tracking.registered_name(cfg),
                                                                cfg.get("mlflow.alias")).version)


def task_cluster(cfg: Config, rt: Runtime) -> dict:
    from .pipeline import pair_scorer, resolve
    spark = rt.spark
    champion = _read(cfg, "champion.json")
    if champion is None:
        raise RuntimeError("champion.json is missing: the train task writes it")
    linked = rt.materialize(spark.read.table(_table(cfg, "lm_links")), "links")
    versions = sorted(r[0] for r in linked.select("model_version").distinct().collect())
    current = _alias_version(cfg)
    if versions != [current] or str(champion["version"]) != current:
        raise RuntimeError(f"links were scored by version(s) {versions}, champion.json names {champion['version']}, "
                           f"@{cfg.get('mlflow.alias')} names {current}: refresh scores and links first")
    left, right = spark.read.table(_table(cfg, "lm_left_entity")), spark.read.table(_table(cfg, "lm_right_entity"))
    cand = rt.materialize(spark.read.table(_table(cfg, "lm_candidates")), "candidates")
    threshold = champion["threshold"]
    left_ids = [r.id for r in left.select("id").collect()]
    right_ids = [r.id for r in right.select("id").collect()]
    link_rows = [(r.l_id, r.r_id, float(r.p)) for r in linked.collect()]
    scorer = pair_scorer(rt, cfg, left, right, champion["expr"], cand)
    clusters, cstats = resolve(cfg, left_ids, right_ids, link_rows, threshold, score=scorer)
    ident = _root(cfg) / "identity"
    prev_path = ident / "crosswalk.json"
    previous = json.loads(prev_path.read_text()) if prev_path.exists() else None
    crosswalk, events = identity.assign(clusters, previous, run=time.strftime("%Y%m%dT%H%M%S"))
    ok, problems = identity.reconcile(previous or {}, crosswalk, events)
    if not ok:
        raise RuntimeError("identity log does not reconcile: " + "; ".join(problems))
    ident.mkdir(parents=True, exist_ok=True)
    prev_path.write_text(json.dumps(crosswalk, sort_keys=True) + "\n")
    with (ident / "log.jsonl").open("a") as fh:
        for e in events:
            fh.write(json.dumps(e, sort_keys=True) + "\n")
    spark.createDataFrame(sorted(crosswalk.items()), "record_key string, mdm_id string") \
        .write.mode("overwrite").saveAsTable(_table(cfg, "lm_crosswalk"))
    out = {"model_version": current, "threshold": threshold, "links": len(link_rows),
           "identity": {"method": cfg.get("cluster.method"), "entities": len(set(crosswalk.values())),
                        "records": len(crosswalk), "events": dict(sorted(Counter(e["event"] for e in events).items())),
                        "cluster_stats": cstats, "reconciles": ok}}
    truth = labels.truth_pairs(spark, cfg)
    if truth is not None:
        anchors = spark.read.table(_table(cfg, "lm_labels")).select("l_id").distinct()
        out["evaluation"] = evaluate.pairwise(linked, truth, cand, anchors)
        out["evaluation"]["nearest_neighbour_baseline"] = evaluate.trivial_baseline(cand, truth)
    return out


def canonical(row: dict | str) -> str:
    """One row as canonical JSON: keys sorted, nulls dropped (Spark's to_json drops them too)."""
    d = json.loads(row) if isinstance(row, str) else row
    return json.dumps({k: v for k, v in d.items() if v is not None}, sort_keys=True, separators=(",", ":"))


def _rows(df: DataFrame, columns: list[str]) -> list[str]:
    return sorted(canonical(r[0]) for r in df.select(F.to_json(F.struct(*[F.col(c) for c in columns]))).collect())


def task_quality(cfg: Config, rt: Runtime, expect: str | None = None) -> dict:
    """Both engines on the raw inputs, plus what the pipeline's own (DQX) quarantine tables hold."""
    spark, out = rt.spark, {}
    seeded = json.loads(Path(expect).read_text()) if expect else {}
    for side in ("left", "right"):
        spec = cfg.get(f"inputs.{side}")
        raw, specs = read_table(spark, cfg, spec), quality.input_specs(cfg, spec["id"], side)
        res = {}
        for name in ("native", "dqx"):
            valid, bad = quality.engine(cfg, name).split(raw, specs)
            # a row is identified by its full content (seeded rows may share or lack an id)
            res[name] = {"valid": valid.count(), "quarantined": _rows(bad, raw.columns)}
        res["pipeline"] = _rows(spark.read.table(_table(cfg, f"lm_{side}_quarantine")), raw.columns)
        want = sorted(canonical(r) for r in seeded.get(side, []))
        out[side] = {"native_valid": res["native"]["valid"], "dqx_valid": res["dqx"]["valid"],
                     "native_quarantined": len(res["native"]["quarantined"]),
                     "dqx_quarantined": len(res["dqx"]["quarantined"]), "pipeline_quarantined": len(res["pipeline"]),
                     "same_split": res["native"] == res["dqx"],
                     "pipeline_is_dqx_split": res["pipeline"] == res["dqx"]["quarantined"],
                     "seeded": len(want),
                     "seeded_rows_quarantined": want == res["dqx"]["quarantined"] if want else None}
    out["native_same_split"] = all(out[s]["same_split"] for s in ("left", "right"))
    out["dqx_quarantine_ok"] = all(out[s]["pipeline_is_dqx_split"] and out[s]["seeded_rows_quarantined"] is not False
                                   and out[s]["dqx_quarantined"] == out[s]["seeded"] for s in ("left", "right"))
    return out


def task_explain(cfg: Config, rt: Runtime) -> dict:
    """The formatted physical plan of each pipeline stage, rebuilt from its upstream table on this compute; a plan
    node that is not a Photon operator is a fallback. Plans go to <storage.root>/explain/<stage>.txt."""
    spark, out = rt.spark, {}
    champion = _read(cfg, "champion.json") or {}
    feats = spark.read.table(_table(cfg, "lm_features"))
    stages = {
        "gate": lambda: quality.engine(cfg).split(read_table(spark, cfg, cfg.get("inputs.left")),
                                                  quality.input_specs(cfg, cfg.get("inputs.left.id"), "left"))[0],
        "entity": lambda: features.prepare_sides(
            entity.prepare(spark.read.table(_table(cfg, "lm_left_valid")), cfg, cfg.get("inputs.left.id")),
            entity.prepare(spark.read.table(_table(cfg, "lm_right_valid")), cfg, cfg.get("inputs.right.id")), cfg)[0],
        "candidates": lambda: candidates.generate(spark.read.table(_table(cfg, "lm_left_entity")),
                                                  spark.read.table(_table(cfg, "lm_right_entity")), cfg,
                                                  plan=_read(cfg, "candidate_plan.json")),
        "features": lambda: _features_plan(cfg, spark),
        "scores": lambda: feats.select("l_id", "r_id", F.expr(champion["expr"]).alias("p")),
    }
    from . import decision
    stages["links"] = lambda: decision.links(spark.read.table(_table(cfg, "lm_scores")), champion["threshold"], cfg)
    d = _root(cfg) / "explain"
    d.mkdir(parents=True, exist_ok=True)
    for name, build in stages.items():
        try:
            text = build()._explain_string(mode="formatted")
        except Exception as e:
            out[name] = {"error": f"{type(e).__name__}: {str(e)[:300]}"}
            continue
        (d / f"{name}.txt").write_text(text)
        out[name] = {"chars": len(text), "path": str(d / f"{name}.txt")}
    return out


def _features_plan(cfg: Config, spark):
    left = spark.read.table(_table(cfg, "lm_left_entity"))
    right = spark.read.table(_table(cfg, "lm_right_entity"))
    pre = lambda df, p, idc: df.select([F.col(c).alias(idc if c == "id" else f"{p}{c}") for c in df.columns])
    joined = (spark.read.table(_table(cfg, "lm_candidates")).join(pre(left, "l_", "l_id"), "l_id")
              .join(pre(right, "r_", "r_id"), "r_id"))
    df, cols = features.compare(joined, cfg)
    return df.select("l_id", "r_id", *cols)


TASKS = {"plan": task_plan, "train": task_train, "cluster": task_cluster, "quality": task_quality,
         "explain": task_explain}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lakematch_task")
    ap.add_argument("task", choices=sorted(TASKS))
    ap.add_argument("--config", required=True)
    ap.add_argument("--expect", help="quality: JSON of the seeded bad rows per side")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load(args.config)
    t0 = time.time()
    rt = Runtime(cfg)
    try:
        result = TASKS[args.task](cfg, rt, args.expect) if args.task == "quality" else TASKS[args.task](cfg, rt)
    finally:
        rt.close()
    result = {"task": args.task, "seconds": round(time.time() - t0, 1), "runtime": {
        "spark": rt.caps.spark_version, "remote": rt.remote, "materialize": rt.strategy()}, **result}
    path = _write(cfg, f"tasks/{args.task}.json", result)
    print(f"LAKEMATCH_TASK {args.task} -> {path}")
    print(json.dumps(result, indent=2, default=str)[:20000])
    return 0
