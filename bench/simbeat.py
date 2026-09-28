#!/usr/bin/env python3
"""SIM-3: offline, resumable VALID selection followed by one locked TEST confirmation.

Source scripts/env.sh first. `python bench/simbeat.py run` resumes an identical
manifest; `audit` recomputes the selection, intervals and verdict without Spark.
Record preprocessing is transductive; TEST outcomes never enter selection.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import corpora
import simbeat_inputs as inputs
from methods import CORPORA, cfg_for, bucket

from pyspark.ml import PipelineModel
from pyspark.sql import functions as F, Window
from lakematch import candidates, config, decision, embeddings, features, matcher
from lakematch.features import sota, udf
from lakematch.pipeline import entity_sides, _prefixed
from lakematch.runtime import Runtime

RESULT = HERE / "results/simbeat.json"
DEFAULT_WORK = corpora.DATA / "runs/simbeat"
PROTOCOL = "simbeat-v2"
B = 1000
SEED = 0
PARTITIONS = 8
UDF_MARKERS = ("pythonudf", "batchevalpython", "arrowevalpython", "scalaudf")
DATA_FILES = (
    "febrl4/left.csv", "febrl4/right.csv", "febrl4/truth.csv",
    "bpid/matching_dataset.jsonl", "abt_buy/train.txt", "abt_buy/valid.txt", "abt_buy/test.txt",
    "leipzig/affiliationstrings_ids.csv", "leipzig/affiliationstrings_mapping.csv",
)


def log(s):
    print(f"[{dt.datetime.now():%H:%M:%S}] {s}", flush=True)


def read(p):
    return json.loads(Path(p).read_text())


def write(p, value):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    tmp.replace(p)


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_hash(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_hash(p):
    return digest({str(f.relative_to(p)): file_hash(f) for f in sorted(Path(p).rglob("*")) if f.is_file()
                   and not f.name.startswith(".")})


def shortlist():
    return [m["family"] for m in sorted(
        (m for m in read(ROOT / "spec/research/sota_candidates.json")["measures"] if m.get("shortlisted")),
        key=lambda m: m["rank"])]


def variant(fs):
    return "levenshtein" + "".join(" + " + f for f in shortlist() if f in fs)


def families(name):
    return name.split(" + ")[1:]


def key(name):
    return hashlib.sha256(name.encode()).hexdigest()[:16]


def offline():
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    def cached(url, dest):
        if not dest.exists():
            raise FileNotFoundError(f"Offline benchmark: missing {dest}; fetch corpora separately")
        return dest
    corpora._fetch = cached


def manifest():
    offline()
    bundle = inputs.public_manifest()
    provider = embeddings.resolve(config.build({}))
    if provider is None:
        raise RuntimeError("The default local embedding model must already be cached")
    import pyspark, pandas, pyarrow
    sources = [*sorted((ROOT / "src/lakematch").rglob("*.py")), HERE / "simbeat.py",
               HERE / "corpora.py", HERE / "methods.py", HERE / "simbeat_audit.py",
               HERE / "simbeat_inputs.py", HERE / "simbeat_holdout.py",
               ROOT / "spec/research/sota_candidates.json"]
    return {"protocol": PROTOCOL, "shortlist": shortlist(), "seed": SEED, "bootstrap_replicates": B,
            "partitions": PARTITIONS, "new_max_chars": 512, "new_token_cap": 128, "monge_elkan_token_cap": 30,
            "candidate_method": "gram_topk", "matcher": {"estimator": "gbt", "maxIter": 60, "maxDepth": 3},
            "versions": {"python": sys.version.split()[0], "spark": pyspark.__version__,
                         "numpy": np.__version__, "pandas": pandas.__version__, "pyarrow": pyarrow.__version__},
            "data_sha256": bundle["source_sha256"], "input_bundle": bundle,
            "source_sha256": {str(f.relative_to(ROOT)): file_hash(f) for f in sources},
            "embedding": {"model": provider.model, "revision": Path(provider.path).name,
                          "sha256": tree_hash(Path(provider.path))},
            "defaults": config.build({}).data}


def cfg(c, work, *, extras=False):
    return cfg_for(c, storage={"root": str(work / c.name / "scratch")},
                   runtime={"cores": 8, "shuffle_partitions": PARTITIONS, "driver_memory": "8g"},
                   features={"string_similarity": "both", "udf_features": True,
                             "extra_families": shortlist() if extras else [],
                             "token_cap": 128 if extras else 30, "sota_max_chars": 512},
                   matcher={"estimator": "gbt", "seed": SEED})


def stable(df):
    return df.repartition(PARTITIONS, "l_id", "r_id").sortWithinPartitions("l_id", "r_id")


def part_expr(split, *unit):
    sub = F.pmod(F.xxhash64(*unit, F.lit("simbeat_fit_v1")), F.lit(5))
    return F.when(split == "train", F.when(sub < 4, "fit").otherwise("thr")).otherwise(split)


def development_context(work, name):
    """Public metadata only; historical mixed-label caches cannot start new work."""
    m = read(Path(work) / "manifest.json")
    if m["protocol"] != PROTOCOL:
        raise RuntimeError("Legacy mixed-label cache is read-only; provision v2 inputs for new work")
    bundle = inputs.public_manifest()
    if bundle != m["input_bundle"]:
        raise RuntimeError("Staged input manifest changed")
    meta = bundle["corpora"][name]
    return corpora.Corpus(name, meta["kind"], meta["fields"], None, None)


def attach_labels(spark, c, pairs, labels):
    """Called only after candidate partitions have been separated."""
    if c.kind == "pairs":
        truth = spark.createDataFrame(labels["pairs"], "l_id string, r_id string, label double, split string")
        out = pairs.join(truth.select("l_id", "r_id", "label"), ["l_id", "r_id"], "left")
        if out.filter("label is null").limit(1).count():
            raise RuntimeError("Missing labels for partitioned pairs")
        return out
    truth = spark.createDataFrame(labels["truth"], "l_id string, r_id string").withColumn("label", F.lit(1.0))
    return pairs.join(truth, ["l_id", "r_id"], "left").fillna(0.0, ["label"])


def make_pairs(rt, c, L, R, work):
    spark = rt.spark
    labels = inputs.load_development(c.name)
    if c.kind == "pairs":
        props = spark.createDataFrame(c.pairs, "l_id string, r_id string, split string")
        sub = F.pmod(F.xxhash64("l_id", "r_id"), F.lit(5))
        props = props.withColumn("part", F.when(F.col("split") == "train",
                    F.when(sub < 4, "fit").otherwise("thr")).otherwise(F.col("split"))).drop("split")
    else:
        dedupe = c.kind == "dedupe"
        ccfg = cfg_for(c, candidates={"method": "gram_topk", "k": 11 if dedupe else 5})
        props = candidates.generate(L, R, ccfg)
        if dedupe:
            props = props.filter("l_id != r_id").withColumn("a", F.least("l_id", "r_id")).withColumn("b", F.greatest("l_id", "r_id"))
            w = Window.partitionBy("a", "b").orderBy("l_id", "r_id")
            props = props.withColumn("rn", F.row_number().over(w)).filter("rn = 1").select(
                F.col("a").alias("l_id"), F.col("b").alias("r_id"), "cand_score", "cand_rank", "cand_gap")
            part = part_expr(bucket(F.concat_ws("|", "l_id", "r_id")), "l_id", "r_id")
        else:
            part = part_expr(bucket("l_id"), "l_id")
            units = spark.createDataFrame([(u,) for u in labels["units"]], "l_id string")
            valid_units = [r.l_id for r in units.withColumn("split", bucket("l_id")).filter("split = 'valid'").orderBy("l_id").collect()]
            valid_set = set(valid_units)
            write(work / c.name / "development_truth.json", {"valid": {
                "units": valid_units, "truth": sorted(t for t in labels["truth"] if t[0] in valid_set)}})
        props = props.withColumn("part", part)
    # Held-out candidates have no outcome column; development cannot materialize TEST labels.
    heldout = props.filter("part = 'test'")
    development = attach_labels(spark, c, props.filter("part != 'test'"), labels)
    return development, heldout


def prepare_test_pairs(rt, c, work, payload):
    p = Path(work) / c.name
    candidates_test = rt.spark.read.parquet(str(p / "test_candidates"))
    if "label" in candidates_test.columns or candidates_test.filter("part != 'test'").limit(1).count():
        raise RuntimeError("Invalid unlabelled TEST candidates")
    pairs = attach_labels(rt.spark, c, candidates_test, payload)
    pairs.write.mode("overwrite").parquet(str(p / "test_pairs"))
    if c.kind == "linkage":
        write(p / "test_truth.json", {"test": {"units": payload["units"], "truth": payload["truth"]}})
    return rt.spark.read.parquet(str(p / "test_pairs"))


def pair_table(rt, c, work, pairs, L, R, requested=None, stage="valid"):
    base, extra = cfg(c, work), cfg(c, work, extras=True)
    joined = pairs.join(_prefixed(L, "l_", "l_id"), "l_id").join(_prefixed(R, "r_", "r_id"), "r_id")
    # Pin the joined inputs after balancing; expensive DP projections must not be
    # pushed below the repartition into a coalesced Parquet reader.
    joined = rt.materialize(stable(joined), "comparison_inputs_" + stage)
    out, cols = features.compare(joined, base, candidates="cand_score" in pairs.columns)
    add = {}
    wanted = set(shortlist() if requested is None else requested)
    for f, spec in c.fields.items():
        add.update(sota.comparisons(f, spec["type"], extra, wanted))
        if spec["type"] != "number" and f"jw_{f}" not in cols:
            a, b = F.col("l_" + f), F.col("r_" + f)
            add[f"jw_{f}"] = F.when((F.length(a) > 0) & (F.length(b) > 0),
                                    udf.jaro_winkler(a, b, rt.spark.version)).otherwise(-1.0)
    out = out.withColumns({n: e.cast("double") for n, e in add.items()})
    cols += list(add)
    builtin_cols = [n for n in cols if features.family_of(n) != "jaro_winkler"]
    proof = {}
    for name, selected in (("builtins", builtin_cols), ("jaro_winkler", [n for n in cols if n.startswith("jw_")])):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out.select(*selected).explain(mode="simple")
        plan = buf.getvalue()
        free = not any(m in plan.lower() for m in UDF_MARKERS)
        if free != (name == "builtins"):
            raise AssertionError(f"Unexpected pair comparison plan for {name}")
        path = work / c.name / f"{stage}_{name}.plan.txt"
        path.write_text(plan)
        proof[name] = {"udf_free": free, "sha256": file_hash(path), "columns": selected,
                       "scope": "physical comparison projection before pair materialization; record embeddings pinned"}
    return out.select("l_id", "r_id", "label", "part", *cols), cols, proof


def prepare(work, name):
    offline()
    p = work / name
    if (p / "prepared.json").exists():
        return
    p.mkdir(parents=True, exist_ok=True)
    development_context(work, name)
    c = inputs.load_records(name)
    rt = Runtime(cfg(c, work, extras=True))
    try:
        L, R = entity_sides(rt, cfg(c, work, extras=True), rt.spark.createDataFrame(c.left), rt.spark.createDataFrame(c.right))
        limits = {}
        for side, df in (("left", L), ("right", R)):
            exprs = []
            for f, spec in c.fields.items():
                if spec["type"] in {t for types in sota.FIELD_TYPES.values() for t in types}:
                    exprs.append(F.max(F.length(f)).alias("chars_" + f))
                    if "tok_" + f in df.columns:
                        exprs.append(F.max(F.size(F.array_distinct("tok_" + f))).alias("tokens_" + f))
            limits[side] = df.agg(*exprs).first().asDict()
            if any(v > (512 if k.startswith("chars_") else 128) for k, v in limits[side].items()):
                raise RuntimeError(f"Predeclared feature limits exceeded: {limits}")
            df.write.mode("overwrite").parquet(str(p / side))
        L, R = (rt.spark.read.parquet(str(p / side)) for side in ("left", "right"))
        pairs, heldout = make_pairs(rt, c, L, R, work)
        heldout.write.mode("overwrite").parquet(str(p / "test_candidates"))
        pairs.write.mode("overwrite").parquet(str(p / "pairs"))
        pairs = rt.spark.read.parquet(str(p / "pairs"))
        # Only development comparisons are evaluated here. Held-out vectors are deferred.
        table, cols, proof = pair_table(rt, c, work, pairs.filter("part != 'test'"), L, R)
        stable(table).write.mode("overwrite").parquet(str(p / "development"))
        counts = {r.part: {"pairs": r.n, "positives": int(r.positives)} for r in
                  pairs.filter("part != 'test'").groupBy("part").agg(F.count("*").alias("n"), F.sum("label").alias("positives")).collect()}
        write(p / "prepared.json", {"columns": cols, "plan": proof, "counts": counts,
                                     "limits": limits, "notes": c.notes, "fields": c.fields, "kind": c.kind})
        log(f"Prepared {name}: {counts}, {len(cols)} features")
    finally:
        rt.close(stop=True)


def select_cols(cols, name):
    fs = set(families(name))
    sim = name if name in ("jaro_winkler", "both") else "levenshtein"
    allowed = features.active_families(config.build({"features": {"string_similarity": sim, "udf_features": True}})) | fs
    return [c for c in cols if features.family_of(c) in allowed]


def selected_links(rows, threshold, prob="p"):
    # Mirrors decision.links(one_to_one): best right per left, then best left per right, no reassignment.
    left = {}
    for r in sorted(rows, key=lambda r: (-r[prob], r["r_id"], r["l_id"])):
        if r[prob] >= threshold:
            left.setdefault(r["l_id"], r)
    right = {}
    for r in sorted(left.values(), key=lambda r: (-r[prob], r["l_id"], r["r_id"])):
        right.setdefault(r["r_id"], r)
    return {(r["l_id"], r["r_id"]) for r in right.values()}


def counts_for(rows, threshold, linkage=None, prob="p"):
    if linkage is None:
        rows = sorted(rows, key=lambda r: (r["l_id"], r["r_id"]))
        units = [[r["l_id"], r["r_id"]] for r in rows]
        y = np.array([r["label"] == 1 for r in rows])
        pred = np.array([r[prob] >= threshold for r in rows])
        counts = np.stack((pred & y, pred & ~y, ~pred & y), axis=1).astype(int)
    else:
        units = linkage["units"]
        truth = {tuple(t) for t in linkage["truth"]}
        links = selected_links(rows, threshold, prob)
        by_left = {u: [0, 0, 0] for u in units}
        for pair in truth | links:
            by_left[pair[0]][0 if pair in truth & links else 1 if pair in links else 2] += 1
        counts = np.array([by_left[u] for u in units], dtype=int)
    return units, counts


def f1(counts):
    tp, fp, fn = np.asarray(counts).T
    den = 2 * tp + fp + fn
    return np.divide(2 * tp, den, out=np.zeros_like(den, dtype=float), where=den != 0)


def bootstrap(counts, seed=SEED):
    rng = np.random.default_rng(seed)
    # Bounded memory, same unit indices for both models when called with the same seed.
    return np.array([float(f1(counts[rng.integers(0, len(counts), len(counts))].sum(axis=0))) for _ in range(B)])


def metrics(units, counts):
    totals = counts.sum(axis=0)
    tp, fp, fn = (int(v) for v in totals)
    return {"f1": float(f1(totals)), "ci95": np.quantile(bootstrap(counts), [.025, .975]).tolist(),
            "tp": tp, "fp": fp, "fn": fn, "units": len(units), "unit_sha256": digest(units),
            "precision": tp / max(tp + fp, 1), "recall": tp / max(tp + fn, 1)}


def metric_path(work, corpus, name):
    return work / corpus / "valid" / (key(name) + ".json")


def evaluate(work, name, variants):
    offline()
    pending = [v for v in variants if not metric_path(work, name, v).exists()]
    if not pending:
        return
    c = development_context(work, name)
    p = work / name
    meta = read(p / "prepared.json")
    rt = Runtime(cfg(c, work))
    try:
        table = rt.spark.read.parquet(str(p / "development"))
        fit = stable(table.filter("part = 'fit'")).cache()
        thr = stable(table.filter("part = 'thr'")).cache()
        valid = stable(table.filter("part = 'valid'")).cache()
        for df in (fit, thr, valid):
            df.count()
        linkage = read(p / "development_truth.json")["valid"] if c.kind == "linkage" else None
        for v in pending:
            cols = select_cols(meta["columns"], v)
            log(f"Fit {name}: {v} ({len(cols)} columns)")
            model = matcher.train(fit, cols, cfg(c, work))
            threshold = decision.pick_threshold(matcher.score(model, thr), cfg(c, work))
            rows = [r.asDict() for r in matcher.score(model, valid).select("l_id", "r_id", "label", "p").orderBy("l_id", "r_id").collect()]
            units, counts = counts_for(rows, threshold, linkage)
            result = metrics(units, counts)
            model_path = p / "models" / key(v)
            model.write().overwrite().save(str(model_path))
            builtin = set(cols) <= set(meta["plan"]["builtins"]["columns"])
            result.update({"variant": v, "columns": cols, "threshold": threshold,
                           "plan_udf_free": builtin and meta["plan"]["builtins"]["udf_free"],
                           "plan_sha256": meta["plan"]["builtins" if builtin else "jaro_winkler"]["sha256"],
                           "model_sha256": tree_hash(model_path), "counts_by_unit": counts.tolist()})
            write(metric_path(work, name, v), result)
            log(f"VALID {name}: {v}: F1={result['f1']:.8f}, threshold={threshold}")
            del model
            rt.spark._jvm.java.lang.System.gc()
    finally:
        rt.close(stop=True)


def mean(rows):
    return sum(rows[c]["f1"] for c in CORPORA) / len(CORPORA)


def choose_round(current, options, rows):
    base = variant(current)
    means = {v: mean(rows[v]) for v in options}
    best = max(options, key=means.get)  # input order is the declared shortlist tie-break
    accepted = means[best] > mean(rows[base])
    return {"base": base, "base_mean_f1": mean(rows[base]), "options": means,
            "best": best, "gain": means[best] - mean(rows[base]), "accepted": accepted}


def recompute_verdict(result):
    rows, t = result["valid"], result["test"]
    checks = {"valid_mean_improves_jw": mean(rows["chosen"]) > mean(rows["jaro_winkler"]),
              "abt_buy_not_below_jw": rows["chosen"]["abt_buy"]["f1"] >= rows["jaro_winkler"]["abt_buy"]["f1"],
              "all_within_0_005_of_lev": all(rows["chosen"][c]["f1"] >= rows["levenshtein"][c]["f1"] - .005 for c in CORPORA),
              "test_mean_not_below_jw": t["chosen"]["mean_f1"] >= t["jaro_winkler"]["mean_f1"]}
    return ("beaten" if all(checks.values()) else "not_beaten"), checks


def confirm(work, name):
    # All cache validation precedes Runtime, corpus loaders and model inference.
    from simbeat_audit import (audit_confirmation, audit_selection, bound_models, canonical, columns_for,
                               load_predictions, model_check, plan_checks, prediction_counts,
                               prediction_provenance, require)
    work = Path(work)
    p = work / name
    lock, manifest_record = read(work / "selection.json"), read(work / "manifest.json")
    require(digest(manifest_record) == lock["manifest_sha256"], "Confirmation manifest mismatch")
    require(lock["chosen_variant"] == canonical(lock["chosen_families"], manifest_record["shortlist"]),
            "Chosen variant mismatch")
    prepared = read(p / "prepared.json")
    frozen = {label: read(metric_path(work, name, v)) for label, v in
              (("chosen", lock["chosen_variant"]), ("jaro_winkler", "jaro_winkler"))}
    bound_models(lock, frozen, name)
    for label, row in frozen.items():
        v = lock["chosen_variant"] if label == "chosen" else label
        require(row["variant"] == v and row["columns"] == columns_for(
            prepared["columns"], v, manifest_record["shortlist"]), "Frozen feature columns mismatch")
    confirmation_path = p / "confirmation.json"
    if confirmation_path.exists():
        audit_confirmation(name, read(confirmation_path), lock, frozen, prepared, work)
        return
    prediction_path = p / "test_predictions.json"
    if prediction_path.exists():
        expected = prediction_provenance(work, name, lock, frozen)
        # Orphan bare arrays are rejected; only bound envelopes may resume here.
        rows, proof = load_predictions(prediction_path, expected)
        plan_checks(proof, path=p, stage="test")
        prediction_counts(work, name, rows, frozen)
    else:
        valid = {v: {c: read(metric_path(work, c, v)) for c in CORPORA} for v in lock["variants"]}
        valid["chosen"] = valid[lock["chosen_variant"]]
        audit_selection(manifest_record, lock, valid)
        require(manifest() == manifest_record, "Live manifest differs; refusing fresh TEST inference")
        if manifest_record["protocol"] != PROTOCOL:
            raise RuntimeError("Fresh confirmation requires isolated v2 inputs")
        c = development_context(work, name)
        from simbeat_holdout import release_labels
        payload = release_labels(work, name, lock, manifest_record, valid)
        rt = Runtime(cfg(c, work))
        try:
            pair = prepare_test_pairs(rt, c, work, payload)
            expected = prediction_provenance(work, name, lock, frozen)
            L, R = (rt.spark.read.parquet(str(p / side)) for side in ("left", "right"))
            table, _, proof = pair_table(rt, c, work, pair, L, R, lock["chosen_families"], stage="test")
            table = stable(table).cache()
            preds = table
            for label, v in (("chosen", lock["chosen_variant"]), ("jaro_winkler", "jaro_winkler")):
                path = p / "models" / key(v)
                model_check(path, frozen[label])
                preds = matcher.score(PipelineModel.load(str(path)), preds).withColumnRenamed("p", "p_" + label)
            rows = [r.asDict() for r in preds.select("l_id", "r_id", "label", "p_chosen", "p_jaro_winkler")
                    .orderBy("l_id", "r_id").collect()]
            # One atomic write binds predictions to the lock, models and input files.
            write(prediction_path, {"schema_version": 1, "provenance": expected, "plan": proof, "rows": rows})
        finally:
            rt.close(stop=True)
    truth_file = "test_truth.json" if manifest_record["protocol"] == PROTOCOL else "linkage_truth.json"
    linkage = read(p / truth_file)["test"] if name == "febrl4_half_unmatched" else None
    result = {"selection_sha256": digest(lock), "predictions_sha256": file_hash(prediction_path), "plan": proof}
    for label in ("chosen", "jaro_winkler"):
        units, counts = counts_for(rows, frozen[label]["threshold"], linkage, "p_" + label)
        result[label] = {**metrics(units, counts), "counts_by_unit": counts.tolist(),
                         "threshold": frozen[label]["threshold"], "model_sha256": frozen[label]["model_sha256"]}
    audit_confirmation(name, result, lock, frozen, prepared, work)
    write(confirmation_path, result)
    log(f"TEST {name}: chosen={result['chosen']['f1']:.8f}, JW={result['jaro_winkler']['f1']:.8f}")


def child(work, action, corpus, variants=()):
    subprocess.run([sys.executable, str(Path(__file__).resolve()), action, "--work-dir", str(work),
                    "--corpus", corpus, "--variants", json.dumps(list(variants))], check=True)


def load_valid(work, names):
    return {v: {c: read(metric_path(work, c, v)) for c in CORPORA} for v in names}


def aggregate_test(per):
    out = {label: {"corpora": {c: per[c][label] for c in CORPORA},
                   "mean_f1": sum(per[c][label]["f1"] for c in CORPORA) / len(CORPORA)}
           for label in ("chosen", "jaro_winkler")}
    boot = {}
    for label in out:
        boot[label] = np.mean([bootstrap(np.array(per[c][label]["counts_by_unit"]), SEED + i)
                               for i, c in enumerate(CORPORA)], axis=0)
        out[label]["mean_ci95"] = np.quantile(boot[label], [.025, .975]).tolist()
    for c in CORPORA:
        assert per[c]["chosen"]["unit_sha256"] == per[c]["jaro_winkler"]["unit_sha256"]
    out["delta_mean_f1"] = out["chosen"]["mean_f1"] - out["jaro_winkler"]["mean_f1"]
    out["delta_ci95"] = np.quantile(boot["chosen"] - boot["jaro_winkler"], [.025, .975]).tolist()
    return out


def run(work):
    # A completed historical run is read-only, even after checker-source changes.
    # Any unfinished/new execution still requires exact live-manifest equality below.
    destination = Path(work) / "result.json"
    existing = destination if destination.exists() else RESULT
    if existing.exists():
        completed = read(existing)
        if Path(completed["meta"]["work_dir"]).resolve() == Path(work).resolve():
            audit(completed, work)
            log(f"Verified completed SIM-3: {completed['verdict']}; no benchmark execution")
            return
    work.mkdir(parents=True, exist_ok=True)
    m = manifest()
    if (work / "manifest.json").exists():
        if read(work / "manifest.json") != m:
            raise RuntimeError("Manifest changed: use a fresh --work-dir; never mix measurements")
    else:
        write(work / "manifest.json", m)
    if not (work / "selection.json").exists():
        for c in CORPORA:
            child(work, "prepare", c)
        names = ["levenshtein", "jaro_winkler", "both"] + [variant([f]) for f in shortlist()]
        for c in CORPORA:
            child(work, "evaluate", c, names)
        current, trace = [], []
        while len(current) < len(shortlist()):
            options = [variant(current + [f]) for f in shortlist() if f not in current]
            for v in options:
                if v not in names:
                    names.append(v)
            for c in CORPORA:
                child(work, "evaluate", c, options)
            rows = load_valid(work, names)
            step = choose_round(current, options, rows)
            trace.append(step)
            log(f"Greedy round {len(trace)}: {step}")
            if not step["accepted"]:
                break
            current = families(step["best"])
        chosen = variant(current)
        rows = load_valid(work, names)
        lock = {"manifest_sha256": digest(m), "selected_on": "validation", "chosen_variant": chosen,
                "chosen_families": current, "forward_selection": trace, "variants": names,
                "models": {c: {label: {k: rows[v][c][k] for k in ("model_sha256", "threshold")}
                                for label, v in (("chosen", chosen), ("jaro_winkler", "jaro_winkler"))} for c in CORPORA}}
        write(work / "selection.json", lock)
    lock = read(work / "selection.json")
    if lock["manifest_sha256"] != digest(m):
        raise AssertionError("Selection belongs to a different manifest")
    for c in CORPORA:
        child(work, "confirm", c)
    rows = load_valid(work, lock["variants"])
    rows["chosen"] = rows[lock["chosen_variant"]]
    per = {c: read(work / c / "confirmation.json") for c in CORPORA}
    result = {"meta": {"generated": dt.datetime.now(dt.timezone.utc).isoformat(), "manifest": m,
                        "selection_sha256": digest(lock), "work_dir": str(work)},
              "selected_on": "validation", "valid": rows, "forward_selection": lock["forward_selection"],
              "chosen_families": lock["chosen_families"], "chosen_variant": lock["chosen_variant"],
              "selection_lock": lock, "test": aggregate_test(per), "confirmation": per,
              "prepared": {c: read(work / c / "prepared.json") for c in CORPORA}}
    result["verdict"], result["verdict_checks"] = recompute_verdict(result)
    audit(result, work)
    write(destination, result)
    render(result, Path(work) / "report.md")
    log(f"SIM-3: {result['verdict']}; result {destination}")


def audit(d, work_dir=None):
    from simbeat_audit import audit as verify
    return verify(d, work_dir)


def render(d, destination=None):
    from render_simbeat import render_report
    Path(destination or (HERE / "SIMBEAT.md")).write_text(render_report(d))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("run", "audit", "render", "prepare", "evaluate", "confirm"))
    ap.add_argument("--work-dir", type=Path, default=DEFAULT_WORK)
    ap.add_argument("--result", type=Path, default=RESULT, help="saved result to audit or render")
    ap.add_argument("--json-only", action="store_true", help="audit internal JSON consistency only; excludes saved evidence")
    ap.add_argument("--corpus", choices=CORPORA)
    ap.add_argument("--variants", default="[]")
    args = ap.parse_args()
    if args.action not in ("audit", "render"):
        offline()
    if args.action == "run":
        run(args.work_dir.resolve())
    elif args.action == "audit":
        from simbeat_audit import AuditError
        try:
            audit(read(args.result), None if args.json_only else args.work_dir)
        except AuditError as e:
            ap.exit(1, f"Audit failed: {e}\n")
        log("Audit passed: " + ("JSON consistency only" if args.json_only else
            "selection, saved predictions, inputs, models, plans, intervals and verdict"))
    elif args.action == "render":
        d = read(args.result); audit(d)
        render(d, None if args.result == RESULT else args.result.parent / "report.md")
    elif args.action == "prepare":
        prepare(args.work_dir, args.corpus)
    elif args.action == "evaluate":
        evaluate(args.work_dir, args.corpus, json.loads(args.variants))
    else:
        confirm(args.work_dir, args.corpus)


if __name__ == "__main__":
    main()
