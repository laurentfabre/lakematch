#!/usr/bin/env python3
"""Fixed-budget retrieval comparison; only validation positive recall is scored."""
import argparse
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import random
import tarfile
import time

from pyspark.sql import functions as F

from lakematch import blocking, candidates, entity
from lakematch.benchmark.corpora import LOADERS, febrl4
from lakematch.benchmark.metrics import BOOTSTRAP_SEED
from lakematch.benchmark.retrieval import training_ids, validation_scope
from lakematch.config import from_dict
from lakematch.runtime import Materializer, create_session, probe
from evidence import sha256
from offline_run import assert_offline

METHODS = ["gram_topk", "learned_blocker", "minhash_lsh", "field_blocks", "union"]


def recall_interval(grouped, reference):
    keys = sorted(grouped)
    if not keys or (reference is not None and set(keys) != set(reference)):
        raise ValueError("Candidate bootstrap needs paired groups with labelled positives")
    rng = random.Random(BOOTSTRAP_SEED)
    values, changes = [], []
    for _ in range(2000):
        draw = rng.choices(keys, k=len(keys))
        numerator = sum(grouped[k][0] for k in draw)
        denominator = sum(grouped[k][1] for k in draw)
        values.append(numerator / denominator)
        if reference is not None:
            baseline = sum(reference[k][0] for k in draw) / denominator
            changes.append(values[-1] - baseline)
    def interval(rows):
        rows = sorted(rows)
        return [rows[int(1999 * .025)], rows[int(1999 * .975)]]
    return {"recall_95ci": interval(values), "paired_recall_delta_95ci": interval(changes) if reference is not None else None,
            "bootstrap_seed": BOOTSTRAP_SEED, "bootstrap_resamples": 2000,
            "bootstrap_units": "declared groups with labelled validation positives", "groups": len(keys)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", choices=LOADERS)
    parser.add_argument("--febrl-variant", choices=["all", "no_ssn", "no_ssn_dob"], default="all")
    args = parser.parse_args()
    assert_offline()
    started = time.perf_counter()
    corpus = febrl4(args.febrl_variant) if args.corpus == "febrl4" else LOADERS[args.corpus]()
    manifest = corpus.freeze()
    out = Path("data/retrieval") / corpus.name
    out.mkdir(parents=True, exist_ok=True)
    archive = out / "retrieval-evidence.tar.gz"
    archive.unlink(missing_ok=True)
    config = from_dict({"entity": {"name": corpus.name, "fields": corpus.fields},
                       "candidates": {"k": 5, "max_pairs": 100000, "max_join_rows": 50000000},
                       "decision": {"threshold": .5}})
    raw = deepcopy(config.data)
    raw["candidates"].update(field_blocks=blocking.proposed_rules(config), union_of=["gram_topk", "field_blocks"])
    config = from_dict(raw)
    train = [p for p in corpus.pairs if p["split"] == "train"]
    if corpus.retrieval:
        partitions = [{r["rec_id"]: r["split"] for r in records} for records in (corpus.left, corpus.right)]
        assert all(partitions[0][p["a_id"]] == partitions[1][p["b_id"]] == "train" for p in train)
    scopes = {name: validation_scope(corpus, name) for name in ("transductive", "disjoint")}
    report = {"corpus": corpus.name, "manifest": json.loads(manifest.read_text()), "config": config.data,
              "plan": "bench/METHOD_PLAN.md", "scope": "validation labelled-positive recall only",
              "scopes": {name: row[2] for name, row in scopes.items()}, "iteration": 1,
              "confirmation_scored": False, "unlabelled_pairs_are_negatives": False,
              "methods": [], "status": "running", "cost": {"remote_spend": 0, "live_label_spend": 0}}
    output = out / "report.json"
    evidence_files = set()
    def save():
        report["evidence_files"] = {str(p.relative_to(out)): sha256(p) for p in sorted(evidence_files)}
        output.write_text(json.dumps(report, indent=2) + "\n")
    def subset(frame, ids):
        selected = spark.createDataFrame([(i,) for i in sorted(ids)], "rec_id string")
        return frame.join(selected, "rec_id", "semi")
    save()
    spark = create_session(config)
    try:
        capabilities = probe(spark)
        with Materializer(spark, config, capabilities) as materializer:
            schema = "rec_id string, " + ", ".join(f"{n} " + ("array<string>" if s.get("multiple") else "string")
                                                    for n, s in corpus.fields.items())
            left, right = [materializer.materialize(entity.prepare(spark.createDataFrame(rows, schema), config), side)
                           for rows, side in ((corpus.left, "left"), (corpus.right, "right"))]
            labels = spark.createDataFrame(train, "a_id string, b_id string, label double")
            training = [materializer.materialize(subset(frame, ids), side)
                        for frame, ids, side in zip((left, right), training_ids(corpus), ("training_left", "training_right"))]
            universes = {"transductive": (left, right), "disjoint": tuple(
                materializer.materialize(subset(frame, ids), side) for frame, ids, side in
                zip((left, right), scopes["disjoint"][0], ("disjoint_left", "disjoint_right")))}
            references = {}
            for method in METHODS:
                print(json.dumps({"corpus": corpus.name, "method": method, "status": "started"}), flush=True)
                cfg = blocking.child_config(config, method)
                fit_started = time.perf_counter()
                state = blocking.prepare_state(*training, labels, cfg)
                state_path = out / (method + "_state")
                blocking.save_state(state, state_path)
                evidence_files.update(p for p in state_path.rglob("*") if p.is_file())
                fit_seconds = time.perf_counter() - fit_started
                for scope, universe in universes.items():
                    positives = scopes[scope][1]
                    if not positives:
                        report["methods"].append({"method": method, "scope": scope, "status": "unavailable",
                                                  "reason": "no labelled validation positives after exclusions"})
                        save()
                        continue
                    validation_anchors = spark.createDataFrame([(a,) for a in sorted({p[0] for p in positives})], "a_id string")
                    plan = candidates.build(*universe, cfg, state=state)
                    text = StringIO()
                    with redirect_stdout(text):
                        plan.pairs.explain(mode="extended")
                    plan_path = out / f"{method}.{scope}.plan.txt"
                    plan_path.write_text(text.getvalue())
                    evidence_files.add(plan_path)
                    retrieval_started = time.perf_counter()
                    try:
                        budget = plan.validate_budget()
                    except candidates.CandidateBudgetExceeded as exc:
                        record = {"method": method, "scope": scope, "status": "budget_rejected",
                            "reason": str(exc), "diagnostics": plan.diagnostics.first().asDict(),
                            "candidate_recall": None, "fit_and_save_seconds": fit_seconds,
                            "guard_seconds": time.perf_counter() - retrieval_started,
                            "fitted_state": str(state_path)}
                        report["methods"].append(record)
                        print(json.dumps(record), flush=True)
                        save()
                        continue
                    rows = plan.pairs.join(validation_anchors, "a_id", "semi").select("a_id", "b_id", "cos", "rank").collect()
                    retrieval_seconds = time.perf_counter() - retrieval_started
                    found = {(r.a_id, r.b_id) for r in rows}
                    grouped = {}
                    for pair, group in positives.items():
                        row = grouped.setdefault(group, [0, 0])
                        row[0] += int(pair in found)
                        row[1] += 1
                    if method == "gram_topk":
                        references[scope] = grouped
                    reference = references.get(scope)
                    hit = len(positives.keys() & found)
                    record = {"method": method, "scope": scope, "status": "completed", "candidate_recall": hit / len(positives),
                              "covered_positives": hit, "validation_positives": len(positives), "budget": budget,
                              "fit_and_save_seconds": fit_seconds, "retrieval_seconds": retrieval_seconds,
                              "fitted_state": str(state_path),
                              "has_python_udf": any(marker in text.getvalue() for marker in ("PythonUDF", "BatchEvalPython", "ArrowEvalPython")),
                              **recall_interval(grouped, reference)}
                    report["methods"].append(record)
                    predictions_path = out / f"{method}.{scope}.predictions.json"
                    predictions_path.write_text(json.dumps({"validation_candidates": [r.asDict() for r in rows],
                        "validation_positives": [[a, b, group] for (a, b), group in positives.items()]}) + "\n")
                    evidence_files.add(predictions_path)
                    print(json.dumps(record), flush=True)
                    save()
        report["cleanup"] = "succeeded"
        report["status"] = "completed"
    except Exception as exc:
        report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        try:
            spark.stop()
        finally:
            report["wall_seconds_including_spark"] = time.perf_counter() - started
            save()
            with tarfile.open(archive, "w:gz") as bundle:
                for path in sorted(evidence_files | {output}):
                    bundle.add(path, arcname=str(path.relative_to(out)))


if __name__ == "__main__":
    main()
