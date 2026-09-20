#!/usr/bin/env python3
"""Validation-only estimator/string/cardinality factorial, with composite tracking."""
import argparse
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
import os
from pathlib import Path
import shlex
import tarfile
import time
from uuid import uuid4

import mlflow
import pandas as pd
from pyspark.sql import functions as F

from lakematch import candidates, entity, feature_stats, features, matcher, tracking
from lakematch.benchmark.corpora import LOADERS, eligible_supervised_pair, febrl4
from lakematch.benchmark.metrics import bootstrap, evaluate, select, tune
from lakematch.config import from_dict
from lakematch.runtime import Materializer, create_session, probe
from evidence import sha256
from offline_run import assert_offline
from spark_event_metrics import summarize as summarize_events

STRINGS = ["levenshtein", "jaro_winkler", "both"]
ESTIMATORS = ["gbt", "logistic_regression", "random_forest"]


def policies(pairs, retrieval):
    if retrieval:
        return ["one_to_one", "many_to_one", "unrestricted"]
    positive = [p for p in pairs if p["label"] == 1. and p["split"] in {"train", "valid"}]
    a, b = {}, {}
    for p in positive:
        a.setdefault(p["a_id"], set()).add(p["b_id"])
        b.setdefault(p["b_id"], set()).add(p["a_id"])
    result = ["unrestricted"]
    if all(len(v) <= 1 for v in a.values()):
        result.append("many_to_one")
        if all(len(v) <= 1 for v in b.values()):
            result.append("one_to_one")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", choices=LOADERS)
    parser.add_argument("--febrl-variant", choices=["all", "no_ssn", "no_ssn_dob"], default="all")
    args = parser.parse_args()
    assert_offline()
    started = time.perf_counter()
    corpus = febrl4(args.febrl_variant) if args.corpus == "febrl4" else LOADERS[args.corpus]()
    manifest = corpus.freeze()
    out = (Path("data/methods") / corpus.name).resolve()
    out.mkdir(parents=True, exist_ok=True)
    archive = out / "methods-evidence.tar.gz"
    archive.unlink(missing_ok=True)
    event_root = out / "spark-events" / uuid4().hex
    event_root.mkdir(parents=True)
    os.environ["PYSPARK_SUBMIT_ARGS"] = shlex.join(["--conf", "spark.eventLog.enabled=true",
        "--conf", "spark.eventLog.compress=false", "--conf", "spark.eventLog.dir=" + event_root.as_uri(), "pyspark-shell"])
    raw = {"entity": {"name": corpus.name, "fields": corpus.fields},
        "candidates": {"k": 5, "max_pairs": 100000, "max_join_rows": 50000000},
        "features": {"multi_token": ["idf_token_cosine", "gram_overlap", "monge_elkan_token"],
                     "embeddings": {"provider": "none"}},
        "decision": {"threshold": .5, "cardinality": "one_to_one" if corpus.retrieval else "unrestricted"},
        "mlflow": {"tracking_uri": f"sqlite:///{out}/mlflow.db", "experiment": "zr3-methods"}}
    config = from_dict(raw)
    report = {"status": "running", "iteration": 2, "corpus": corpus.name,
              "manifest": json.loads(manifest.read_text()), "plan": "bench/CLASSIFIER_PLAN.md",
              "config": config.data, "confirmation_scored": False, "rows": [], "baselines": [],
              "evaluation_scope": "closed-world transductive linkage" if corpus.retrieval else "supplied labelled pairs only",
              "cardinalities": policies(corpus.pairs, corpus.retrieval),
              "spark_event_root": str(event_root), "spark_submit_args": os.environ["PYSPARK_SUBMIT_ARGS"],
              "cost": {"remote_spend": 0, "live_label_spend": 0}}
    evidence_files = set()
    output = out / "report.json"
    def save():
        report["evidence_files"] = {str(p.relative_to(out)): sha256(p) for p in sorted(evidence_files)}
        output.write_text(json.dumps(report, indent=2) + "\n")
    save()
    spark = create_session(config)
    try:
        capabilities = probe(spark)
        with Materializer(spark, config, capabilities) as m:
            preparation = time.perf_counter()
            schema = "rec_id string, " + ", ".join(f"{n} " + ("array<string>" if s.get("multiple") else "string") for n, s in corpus.fields.items())
            raw_left, raw_right = [spark.createDataFrame(rows, schema) for rows in (corpus.left, corpus.right)]
            left, right = [m.materialize(entity.prepare(frame, config), side) for frame, side in ((raw_left, "left"), (raw_right, "right"))]
            truth = {(p["a_id"], p["b_id"]): p["label"] for p in corpus.pairs if p["split"] in {"train", "valid"}}
            if corpus.retrieval:
                plan = candidates.build(left, right, config)
                report["candidate_budget"] = plan.validate_budget()
                candidate_frame = m.materialize(plan.pairs, "candidates")
                retrieval = candidate_frame.collect()
                splits_a = {r["rec_id"]: r["split"] for r in corpus.left}
                splits_b = {r["rec_id"]: r["split"] for r in corpus.right}
                pairs = [{"a_id": p.a_id, "b_id": p.b_id, "label": truth.get((p.a_id, p.b_id), 0.),
                    "split": splits_a[p.a_id], "group": p.a_id} for p in retrieval
                    if eligible_supervised_pair(p.a_id, p.b_id, splits_a, splits_b)]
                assert all(splits_a[p["a_id"]] == splits_b[p["b_id"]] == "train" for p in pairs if p["split"] == "train")
                valid_truth = {(p["a_id"], p["b_id"]): 1. for p in corpus.pairs if p["split"] == "valid"}
                valid_truth.update({(p["a_id"], p["b_id"]): p["label"] for p in pairs if p["split"] == "valid"})
                groups = {pair: pair[0] for pair in valid_truth}
                positives = {p for p, y in valid_truth.items() if y}
                report["candidate_recall"] = len(positives & {(p.a_id, p.b_id) for p in retrieval}) / len(positives)
                simple_scores = [(p.a_id, p.b_id, p.cos) for p in retrieval if splits_a[p.a_id] == "valid"]
            else:
                pairs = [p for p in corpus.pairs if p["split"] in {"train", "valid"}]
                if len(pairs) > config["candidates"]["max_pairs"]:
                    raise ValueError("Supplied pair budget exceeded")
                candidate_frame = spark.createDataFrame([(p["a_id"], p["b_id"], 0., 1, 0.) for p in pairs],
                    "a_id string, b_id string, cos double, rank int, gap double")
                valid_truth = {(p["a_id"], p["b_id"]): p["label"] for p in pairs if p["split"] == "valid"}
                groups = {(p["a_id"], p["b_id"]): p["group"] for p in pairs if p["split"] == "valid"}
                report["candidate_recall"] = None
            labels = spark.createDataFrame(pairs, "a_id string, b_id string, label double, split string, group string")
            train, valid = labels.filter("split = 'train'"), labels.filter("split = 'valid'")
            candidate_frame = m.materialize(candidate_frame.join(labels.select("a_id", "b_id"), ["a_id", "b_id"], "semi"), "eligible")
            training_records = [frame.join(train.select(F.col(key).alias("rec_id")).distinct(), "rec_id", "semi")
                                for frame, key in ((left, "a_id"), (right, "b_id"))]
            vocab = m.materialize(feature_stats.fit_idf(training_records, config), "idf")
            idf_path = out / "idf"
            vocab.write.mode("overwrite").parquet(str(idf_path))
            left, right = [m.materialize(feature_stats.attach_idf(frame, vocab, config), side)
                           for frame, side in ((left, "weighted_left"), (right, "weighted_right"))]
            consumed = train.select("a_id", "b_id", "label").collect()
            example = tracking.pair_snapshot(candidate_frame.orderBy("a_id", "b_id").limit(5), raw_left, raw_right, config)
            report["shared_preparation_seconds"] = time.perf_counter() - preparation
            reference = None
            for similarity in STRINGS:
                cfg_raw = deepcopy(raw)
                cfg_raw["features"].update(string_similarity=similarity, udf_features=similarity != "levenshtein")
                cfg = from_dict(cfg_raw)
                with Materializer(spark, cfg, capabilities) as fm:
                    t0 = time.perf_counter()
                    plan = features.build(candidate_frame, left, right, cfg)
                    explanation = StringIO()
                    with redirect_stdout(explanation):
                        plan.explain(mode="extended")
                    plan_path = out / f"{similarity}.plan.txt"
                    plan_path.write_text(explanation.getvalue())
                    evidence_files.add(plan_path)
                    frame = fm.materialize(plan, "features")
                    feature_seconds = time.perf_counter() - t0
                    native = not any(n in explanation.getvalue() for n in ("PythonUDF", "BatchEvalPython", "ArrowEvalPython"))
                    assert similarity != "levenshtein" or native
                    if similarity == "levenshtein":
                        if not corpus.retrieval:
                            cols = [F.col(f"lev_{n}") for n in corpus.fields]
                            numerator = sum((F.when(c >= 0, c).otherwise(0.) for c in cols), F.lit(0.))
                            denominator = sum((F.when(c >= 0, 1.).otherwise(0.) for c in cols), F.lit(0.))
                            simple = frame.join(valid.select("a_id", "b_id"), ["a_id", "b_id"], "semi").select(
                                "a_id", "b_id", (numerator / F.greatest(denominator, F.lit(1.))).alias("p"))
                            simple_scores = [(r.a_id, r.b_id, r.p) for r in simple.collect()]
                        primary = report["cardinalities"][0]
                        for name, threshold, policy in (("nearest_neighbour", 0., "many_to_one"),
                            ("scalar_threshold", tune(simple_scores, valid_truth, groups, primary), primary)):
                            metrics, grouped = evaluate(select(simple_scores, threshold, policy), valid_truth, groups)
                            report["baselines"].append({"name": name, "threshold": threshold, "cardinality": policy,
                                "score": "IDF gram cosine" if corpus.retrieval else "mean present-field Levenshtein",
                                **metrics, **bootstrap(grouped)})
                    for estimator in ESTIMATORS:
                        variant = similarity + "__" + estimator
                        print(json.dumps({"corpus": corpus.name, "variant": variant, "status": "started"}), flush=True)
                        model_raw = deepcopy(cfg_raw)
                        model_raw["matcher"] = {"estimator": estimator, "max_iter": 20, "max_depth": 3, "seed": 0}
                        model_config = from_dict(model_raw)
                        t0 = time.perf_counter()
                        model = matcher.train(frame, train, model_config)
                        train_seconds = time.perf_counter() - t0
                        t0 = time.perf_counter()
                        valid_frame = frame.join(valid.select("a_id", "b_id"), ["a_id", "b_id"], "semi")
                        scores = [(r.a_id, r.b_id, r.p) for r in matcher.score(valid_frame, model).select("a_id", "b_id", "p").collect()]
                        score_seconds = time.perf_counter() - t0
                        rows = []
                        for policy in report["cardinalities"]:
                            threshold = tune(scores, valid_truth, groups, policy)
                            result, grouped = evaluate(select(scores, threshold, policy), valid_truth, groups)
                            reference = reference if reference is not None else grouped
                            rows.append({"variant": variant, "similarity": similarity, "estimator": estimator,
                                "cardinality": policy, "threshold": threshold, **result, **bootstrap(grouped, reference)})
                        best = max(enumerate(rows), key=lambda row: (row[1]["f1"], -row[0]))[1]
                        model_raw["decision"] = {"threshold": best["threshold"], "cardinality": best["cardinality"]}
                        frozen = from_dict(model_raw)
                        t0 = time.perf_counter()
                        model_record = tracking.log_composite(model, frozen, labels=consumed, input_example=example,
                            experiment="zr3-methods", staging_root=out / "staging", idf_path=str(idf_path),
                            metrics={"validation_f1": best["f1"], "train_seconds": train_seconds})
                        selected = select(scores, best["threshold"], best["cardinality"])
                        predictions = pd.DataFrame([(a, b, (a, b) in selected) for a, b, _ in scores], columns=["a_id", "b_id", "is_link"])
                        with mlflow.start_run(run_id=model_record["run_id"]):
                            evaluation = tracking.evaluate_pairs(predictions,
                                [{"a_id": a, "b_id": b, "label": y} for (a, b), y in valid_truth.items()])
                        assert abs(evaluation["pairwise_f1"] - best["f1"]) < 1e-12
                        logging_seconds = time.perf_counter() - t0
                        for row in rows:
                            row.update(feature_seconds=feature_seconds, train_seconds=train_seconds,
                                score_seconds=score_seconds, logging_seconds=logging_seconds, native_plan=native,
                                feature_count=len(features.feature_order(frozen)), model=model_record,
                                logged_policy=best["cardinality"], logged_threshold=best["threshold"])
                        report["rows"].extend(rows)
                        prediction_path = out / f"{variant}.predictions.json"
                        prediction_path.write_text(json.dumps({"scores": scores, "labels": [[a, b, y, groups[a, b]] for (a, b), y in valid_truth.items()]}) + "\n")
                        evidence_files.add(prediction_path)
                        save()
                        print(json.dumps({"variant": variant, "f1": best["f1"], "cardinality": best["cardinality"],
                            "train_seconds": train_seconds, "model_run_id": model_record["run_id"]}), flush=True)
        report.update(status="completed", cleanup="succeeded")
    except Exception as exc:
        report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        try:
            spark.stop()
        finally:
            report["wall_seconds_including_spark"] = time.perf_counter() - started
            try:
                events = summarize_events(event_root)
                event_summary = out / "spark-metrics.json"
                event_summary.write_text(json.dumps(events, indent=2) + "\n")
                evidence_files.add(event_summary)
                evidence_files.update(p for p in event_root.rglob("*") if p.is_file())
                report["spark_metrics"] = {k: v for k, v in events.items() if k != "stage_metrics"}
            except Exception as exc:
                report.update(status="failed", event_log_error=f"{type(exc).__name__}: {exc}")
            save()
            with tarfile.open(archive, "w:gz") as bundle:
                for path in sorted(evidence_files | {output}):
                    bundle.add(path, arcname=str(path.relative_to(out)))
    if report["status"] != "completed":
        raise RuntimeError("Method experiment or event-log capture did not complete")


if __name__ == "__main__":
    main()
