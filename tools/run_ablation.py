#!/usr/bin/env python3
"""Finite ZR-2 validation sweep. Confirmation/test records are never scored.

Run one corpus per bounded experiment. Shared retrieval/statistics preparation
is timed separately from feature execution, fitting and validation inference.
"""
import argparse
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import time

from pyspark.sql import functions as F

from lakematch import candidates, embeddings, entity, feature_stats, features, matcher
from lakematch.benchmark.corpora import LOADERS, eligible_supervised_pair
from lakematch.benchmark.metrics import bootstrap, evaluate, select, tune
from lakematch.config import FIELD_TYPES, from_dict
from lakematch.runtime import Materializer, create_session, probe
from offline_run import assert_offline

VARIANTS = {
    "native_all": {},
    "without_field_families": {"field_families": False},
    "without_idf": {"multi_token": ["gram_overlap", "monge_elkan_token"]},
    "without_grams": {"multi_token": ["idf_token_cosine", "monge_elkan_token"]},
    "without_monge": {"multi_token": ["idf_token_cosine", "gram_overlap"]},
    "plus_jaro_winkler": {"string_similarity": "both", "udf_features": True},
    "plus_affine": {"multi_token": ["idf_token_cosine", "gram_overlap", "monge_elkan_token", "affine_gap_udf"], "udf_features": True},
    "embedding_on": {"embeddings": {"fields_of_type": ["organisation", "title"], "provider": "local", "model": "data/models/all-MiniLM-L6-v2"}},
}
VARIANTS.update({f"without_{kind}_fields": {"exclude_field_types": [kind]} for kind in sorted(FIELD_TYPES)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", choices=LOADERS)
    parser.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    args = parser.parse_args()
    if args.variants[0] != "native_all":
        parser.error("native_all must be the first variant, the fixed paired-bootstrap reference")
    assert_offline()
    started = time.perf_counter()
    corpus = LOADERS[args.corpus]()
    manifest_path = corpus.freeze()
    out = Path("data/ablation") / corpus.name
    out.mkdir(parents=True, exist_ok=True)
    raw = {"entity": {"name": corpus.name, "fields": corpus.fields},
           "candidates": {"method": "gram_topk", "k": 5, "max_join_rows": 50_000_000, "max_pairs": 100_000},
           "features": {"multi_token": ["idf_token_cosine", "gram_overlap", "monge_elkan_token"],
                        "embeddings": {"fields_of_type": ["organisation", "title"], "provider": "none"}},
           "matcher": {"max_iter": 20, "max_depth": 3, "seed": 0},
           "decision": {"cardinality": "one_to_one" if corpus.retrieval else "unrestricted", "threshold": .5}}
    config = from_dict(raw)
    report = {"corpus": corpus.name, "protocol": "bench/PROTOCOL.md and bench/ABLATION_PLAN.md",
              "split_manifest": str(manifest_path), "manifest": json.loads(manifest_path.read_text()),
              "config": config.data, "variants_declared": args.variants,
              "confirmation_scored": False, "cost": {"remote_spend": 0, "llm_spend": 0, "mode": "offline local"},
              "rows": [], "status": "running"}
    output = out / "report.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    spark = create_session(config)
    try:
        capabilities = probe(spark)
        with Materializer(spark, config, capabilities) as m:
            t0 = time.perf_counter()
            schema = "rec_id string, " + ", ".join(f"{n} " + ("array<string>" if s.get("multiple") else "string") for n, s in corpus.fields.items())
            left, right = [m.materialize(entity.prepare(spark.createDataFrame(rows, schema), config), side)
                           for rows, side in ((corpus.left, "left"), (corpus.right, "right"))]
            truth = {(p["a_id"], p["b_id"]): p["label"] for p in corpus.pairs}
            if corpus.retrieval:
                candidate_plan = candidates.build(left, right, config)
                report["candidate_budget"] = candidate_plan.validate_budget()
                candidate_frame = m.materialize(candidate_plan.pairs, "candidates")
                # Record IDs and unsupervised retrieval scores only: no confirmation predictions.
                retrieval = candidate_frame.collect()
                split_of = {r["rec_id"]: r["split"] for r in corpus.left}
                right_split_of = {r["rec_id"]: r["split"] for r in corpus.right}
                candidate_rows = [{"a_id": p.a_id, "b_id": p.b_id, "label": truth.get((p.a_id, p.b_id), 0.),
                                   "split": split_of[p.a_id], "group": p.a_id} for p in retrieval
                                  if eligible_supervised_pair(p.a_id, p.b_id, split_of, right_split_of)]
                assert all(split_of[p["a_id"]] == right_split_of[p["b_id"]] == "train"
                           for p in candidate_rows if p["split"] == "train")
                report["training_record_partition_assertion"] = "both endpoints train; validation uses full-universe retrieval"
                validation_truth = {(p["a_id"], p["b_id"]): 1. for p in corpus.pairs if p["split"] == "valid"}
                validation_truth.update({(p["a_id"], p["b_id"]): p["label"] for p in candidate_rows if p["split"] == "valid"})
                groups = {pair: pair[0] for pair in validation_truth}
                candidate_set = {(p.a_id, p.b_id) for p in retrieval}
                positives = {p for p, y in validation_truth.items() if y}
                report["candidate_recall_validation"] = len(positives & candidate_set) / len(positives)
                report["candidate_recall_scope"] = "validation true links; no confirmation quality calculated"
            else:
                candidate_rows = [p for p in corpus.pairs if p["split"] in {"train", "valid"}]
                if len(candidate_rows) > config["candidates"]["max_pairs"]:
                    raise ValueError("Supplied-pair budget exceeded")
                candidate_frame = spark.createDataFrame([(p["a_id"], p["b_id"], 0., 1, 0.) for p in candidate_rows],
                                                       "a_id string, b_id string, cos double, rank int, gap double")
                validation_truth = {(p["a_id"], p["b_id"]): p["label"] for p in candidate_rows if p["split"] == "valid"}
                groups = {(p["a_id"], p["b_id"]): p["group"] for p in candidate_rows if p["split"] == "valid"}
                report["candidate_recall_validation"] = None
                report["candidate_recall_scope"] = "supplied labeled pairs; no retrieval claim"
            labels = spark.createDataFrame(candidate_rows, "a_id string, b_id string, label double, split string, group string")
            train_labels, valid_labels = labels.filter("split = 'train'"), labels.filter("split = 'valid'")
            eligible = labels.select("a_id", "b_id")
            candidate_frame = m.materialize(candidate_frame.join(eligible, ["a_id", "b_id"], "semi"), "eligible")
            train_records = [frame.join(train_labels.select(F.col(key).alias("rec_id")).distinct(), "rec_id", "semi")
                             for frame, key in ((left, "a_id"), (right, "b_id"))]
            idf_start = time.perf_counter()
            vocabulary = m.materialize(feature_stats.fit_idf(train_records, config), "idf")
            vocabulary.write.mode("overwrite").parquet(str(out / "idf"))
            left, right = [m.materialize(feature_stats.attach_idf(frame, vocabulary, config), side)
                           for frame, side in ((left, "weighted_left"), (right, "weighted_right"))]
            report["idf_fit_and_apply_seconds"] = time.perf_counter() - idf_start
            report["shared_preparation_seconds"] = time.perf_counter() - t0
            baseline_groups = None
            if corpus.retrieval:
                scores = [(p.a_id, p.b_id, p.cos) for p in retrieval if split_of[p.a_id] == "valid"]
                for name, threshold, cardinality in (("nearest_neighbour", 0., "many_to_one"),
                    ("cosine_threshold", tune(scores, validation_truth, groups, "one_to_one"), "one_to_one")):
                    result, grouped = evaluate(select(scores, threshold, cardinality), validation_truth, groups)
                    report.setdefault("baselines", []).append({"variant": name, "threshold": threshold, **result, **bootstrap(grouped)})
            for variant in args.variants:
                if variant.startswith("without_") and variant.endswith("_fields") and VARIANTS[variant]["exclude_field_types"][0] not in {f["type"] for f in corpus.fields.values()}:
                    continue
                if variant == "embedding_on" and not any(f["type"] in {"organisation", "title"} for f in corpus.fields.values()):
                    continue
                cfg_raw = deepcopy(raw)
                cfg_raw["features"].update(VARIANTS[variant])
                cfg = from_dict(cfg_raw)
                print(json.dumps({"corpus": corpus.name, "variant": variant, "status": "started"}), flush=True)
                with Materializer(spark, cfg, capabilities) as vm:
                    a, b = left, right
                    embedding_cost = {}
                    if variant == "embedding_on":
                        for side, frame in (("left", a), ("right", b)):
                            enriched, embedding_cost[side] = embeddings.prepare(frame, cfg, out / "embeddings" / f"{side}.jsonl")
                            if side == "left":
                                a = vm.materialize(enriched, "embedding_left")
                            else:
                                b = vm.materialize(enriched, "embedding_right")
                    t0 = time.perf_counter()
                    plan = features.build(candidate_frame, a, b, cfg)
                    plan_text = StringIO()
                    with redirect_stdout(plan_text):
                        plan.explain(mode="extended")
                    native = not any(n in plan_text.getvalue() for n in ("PythonUDF", "BatchEvalPython", "ArrowEvalPython"))
                    if not cfg["features"]["udf_features"] and not native:
                        raise AssertionError("Default feature plan contains Python UDF evaluation")
                    (out / f"{variant}.plan.txt").write_text(plan_text.getvalue())
                    frame = vm.materialize(plan, "features")
                    feature_seconds = time.perf_counter() - t0
                    if variant == "native_all" and not corpus.retrieval:
                        cols = [F.col(f"lev_{n}") for n in corpus.fields]
                        numerator = sum((F.when(c >= 0, c).otherwise(0.) for c in cols), F.lit(0.))
                        denominator = sum((F.when(c >= 0, 1.).otherwise(0.) for c in cols), F.lit(0.))
                        simple = frame.join(valid_labels.select("a_id", "b_id"), ["a_id", "b_id"], "semi").select(
                            "a_id", "b_id", (numerator / F.greatest(denominator, F.lit(1.))).alias("p"))
                        simple_scores = [(r.a_id, r.b_id, r.p) for r in simple.collect()]
                        cutoff = tune(simple_scores, validation_truth, groups, "unrestricted")
                        simple_result, simple_groups = evaluate(select(simple_scores, cutoff, "unrestricted"), validation_truth, groups)
                        report["baselines"] = [{"variant": "mean_levenshtein_threshold", "threshold": cutoff,
                                                **simple_result, **bootstrap(simple_groups)}]
                    t0 = time.perf_counter()
                    model = matcher.train(frame, train_labels, cfg)
                    train_seconds = time.perf_counter() - t0
                    t0 = time.perf_counter()
                    valid_features = frame.join(valid_labels.select("a_id", "b_id"), ["a_id", "b_id"], "semi")
                    scores = [(r.a_id, r.b_id, r.p) for r in matcher.score(valid_features, model).select("a_id", "b_id", "p").collect()]
                    score_seconds = time.perf_counter() - t0
                    threshold = tune(scores, validation_truth, groups, cfg["decision"]["cardinality"])
                    predictions = select(scores, threshold, cfg["decision"]["cardinality"])
                    result, grouped = evaluate(predictions, validation_truth, groups)
                    if baseline_groups is None:
                        baseline_groups = grouped
                    row = {"variant": variant, "features_config": cfg["features"], **result, **bootstrap(grouped, baseline_groups), "threshold": threshold,
                           "feature_seconds": feature_seconds, "train_seconds": train_seconds, "score_seconds": score_seconds,
                           "embedding_preparation": embedding_cost, "native_plan": native, "feature_count": len(features.feature_order(cfg))}
                    report["rows"].append(row)
                    (out / f"{variant}.predictions.json").write_text(json.dumps({"scores": scores, "labels": [[*p, y, groups[p]] for p, y in validation_truth.items()]}) + "\n")
                    output.write_text(json.dumps(report, indent=2) + "\n")
                    print(json.dumps(row), flush=True)
            report["cleanup"] = "succeeded"
    finally:
        spark.stop()
    report.update(status="completed", total_seconds_including_start_stop=time.perf_counter() - started)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(str(output), flush=True)


if __name__ == "__main__":
    main()
