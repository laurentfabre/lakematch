"""Labelled pairs for training and threshold selection.

    labels.source: file          a CSV or Parquet of (l_id, r_id, is_match) written by a person or a tool
    labels.source: truth_sample  benchmarks only: `labels.n` candidate pairs drawn in a fixed pseudo-random order
                                 (xxhash64 of the pair) and labelled from evaluation.truth
    labels.source: app           the arbitration app's label store (ZR-7, labels/store.py): the reviewers' current
                                 match / no-match decisions, over the labels of `labels.app_base` (none by default)
    labels.llm                   the LLM labeller plug-in: none, jev (labels/jev.py), ai_query (Databricks Model
                                 Serving through the built-in SQL function, labels.llm_endpoint). The same `labels.n`
                                 sample is labelled by the LLM instead of a truth file; with jev only the confident
                                 answers (labels.llm_tau) become labels, with ai_query only "same" / "different"
                                 (the model answers "cannot tell" when the fields do not settle it)

`split()` separates training and validation labels *by left record*, so no left record contributes to both sides.
"""
from __future__ import annotations

import json

from pyspark.sql import DataFrame, SparkSession, functions as F

from ..config import Config
from ..io import read_table


def truth_pairs(spark: SparkSession, cfg: Config) -> DataFrame | None:
    spec = cfg.get("evaluation.truth")
    if not spec:
        return None
    df = read_table(spark, cfg, spec)
    return df.select(F.col(spec.get("left_id", "l_id")).cast("string").alias("l_id"),
                     F.col(spec.get("right_id", "r_id")).cast("string").alias("r_id")).distinct()


def sample(features: DataFrame, cfg: Config) -> DataFrame:
    """`labels.n` candidate pairs in a fixed pseudo-random order (xxhash64 of the pair)."""
    return features.orderBy(F.xxhash64("l_id", "r_id"), "l_id", "r_id").limit(cfg.get("labels.n"))


def jev_answers(cfg: Config, todo: DataFrame, left: DataFrame, right: DataFrame) -> tuple[list[dict], dict]:
    """Jev's answer on each (l_id, r_id) of `todo` over the entity sides: one row per pair {l_id, r_id, probs,
    label (1.0 / 0.0 / None = cannot tell or below labels.llm_tau)}, and usage. Cached, budgeted (labels/jev.py)."""
    from . import jev
    fields = list(cfg.fields)
    rec = lambda side, p: side.select(F.col("id").alias(f"{p}_id"), F.struct(*fields).alias(f"{p}_rec"))
    rows = todo.join(rec(left, "l"), "l_id").join(rec(right, "r"), "r_id").orderBy("l_id", "r_id").collect()
    asked = [{"l_id": r.l_id, "r_id": r.r_id, "record_a": r.l_rec.asDict(), "record_b": r.r_rec.asDict()} for r in rows]
    name = cfg.get("entity.name")
    what = (f"two {name} records from two sources; a duplicate may carry typos, abbreviations, missing, reordered "
            "or swapped fields")
    cache = cfg.path(cfg.get("labels.llm_cache")) or cfg.path(cfg.get("storage.root")) / "jev_cache.jsonl"
    return jev.ask(asked, what, name, cache, tau=cfg.get("labels.llm_tau"), max_usd=cfg.get("labels.llm_max_usd"))


def llm_labelled(spark: SparkSession, features: DataFrame, cfg: Config, left: DataFrame, right: DataFrame,
                 pairs: DataFrame | None = None) -> tuple[DataFrame, dict]:
    """Jev's confident labels on `pairs` (default: the `labels.n` sample). Returns (labelled pairs, usage)."""
    todo = (sample(features, cfg) if pairs is None else pairs).select("l_id", "r_id")
    answers, usage = jev_answers(cfg, todo, left, right)
    kept = [(a["l_id"], a["r_id"], a["label"]) for a in answers if a["label"] is not None]
    usage.update({"asked": len(answers), "kept": len(kept)})
    lab = spark.createDataFrame(kept, "l_id string, r_id string, label double")
    return features.join(lab, ["l_id", "r_id"]), usage


AI_QUERY_FORMAT = json.dumps({"type": "json_schema", "json_schema": {"name": "verdict", "strict": True, "schema": {
    "type": "object", "required": ["verdict"], "additionalProperties": False,
    "properties": {"verdict": {"type": "string", "enum": ["same", "different", "cannot_tell"]}}}}})


def ai_query_labelled(spark: SparkSession, features: DataFrame, cfg: Config, left: DataFrame,
                      right: DataFrame) -> tuple[DataFrame, dict]:
    """The `labels.n` sample labelled by ai_query(labels.llm_endpoint, ...) on Databricks: one request per pair, run
    by the engine (no driver loop, no UDF). Paid: Model Serving tokens (paid_features.llm_labeller)."""
    fields = list(cfg.fields)
    rec = lambda side, p: side.select(F.col("id").alias(f"{p}_id"), F.to_json(F.struct(*fields)).alias(f"{p}_rec"))
    todo = sample(features, cfg).select("l_id", "r_id").join(rec(left, "l"), "l_id").join(rec(right, "r"), "r_id")
    thing = cfg.get("entity.name") or "record"
    prompt = F.concat(F.lit(f"Two {thing} records from two sources. A duplicate may carry typos, abbreviations, "
                            "missing, reordered or swapped fields. Do they describe one and the same "
                            f"{thing}? Answer cannot_tell when the fields shown do not settle it.\nRecord A: "),
                      F.col("l_rec"), F.lit("\nRecord B: "), F.col("r_rec"))
    endpoint = cfg.get("labels.llm_endpoint").replace("'", "")
    asked = todo.withColumn("_prompt", prompt).withColumn("_answer", F.expr(
        f"ai_query('{endpoint}', _prompt, responseFormat => '{AI_QUERY_FORMAT}')"))
    verdict = F.from_json("_answer", "verdict string")["verdict"]
    answered = asked.select("l_id", "r_id", verdict.alias("verdict")).collect()
    kept = [(r.l_id, r.r_id, 1.0 if r.verdict == "same" else 0.0) for r in answered if r.verdict in ("same", "different")]
    usage = {"labeller": "ai_query", "endpoint": endpoint, "asked": len(answered), "kept": len(kept),
             "verdicts": {v: sum(1 for r in answered if r.verdict == v) for v in ("same", "different", "cannot_tell")}}
    lab = spark.createDataFrame(kept, "l_id string, r_id string, label double")
    return features.join(lab, ["l_id", "r_id"]), usage


def labelled(spark: SparkSession, features: DataFrame, cfg: Config, left: DataFrame | None = None,
             right: DataFrame | None = None, usage: dict | None = None) -> DataFrame:
    """The candidate pairs that carry a label, with a double `label` column. `left`/`right` (entity sides) are
    needed by an LLM labeller, which reads the records; its usage (predicted and actual cost) lands in `usage`."""
    llm = cfg.require("labels.llm")
    if llm in ("jev", "ai_query"):
        if left is None or right is None:
            raise ValueError(f"labels.llm: {llm} needs the entity sides")
        fn = llm_labelled if llm == "jev" else ai_query_labelled
        lab, used = fn(spark, features, cfg, left, right)
        if usage is not None:
            usage.update(used)
        return lab
    source = cfg.require("labels.source")
    if source == "app":
        return app_labelled(spark, features, cfg, usage)
    return _source_labelled(spark, features, cfg, source)


def _source_labelled(spark: SparkSession, features: DataFrame, cfg: Config, source: str) -> DataFrame:
    if source == "truth_sample":
        truth = truth_pairs(spark, cfg)
        if truth is None:
            raise ValueError("labels.source: truth_sample needs evaluation.truth")
        hits = truth.withColumn("label", F.lit(1.0))
        return sample(features, cfg).join(hits, ["l_id", "r_id"], "left").fillna(0.0, ["label"])
    spec = {"path": cfg.get("labels.path")}
    lab = read_table(spark, cfg, spec).select(F.col("l_id").cast("string"), F.col("r_id").cast("string"),
                                              F.col("is_match").cast("double").alias("label"))
    return features.join(lab, ["l_id", "r_id"])


def app_labelled(spark: SparkSession, features: DataFrame, cfg: Config, usage: dict | None = None) -> DataFrame:
    """The arbitration app's current match / no-match decisions (labels/store.py) over the `labels.app_base` labels:
    on a pair both name, the reviewer's decision wins. A decision on a pair that is no longer a candidate is counted
    and left out (the features are the candidates'). Counts land in usage["app_labels"]."""
    from . import store
    app = store.training_labels(spark, cfg)
    base_name = cfg.get("labels.app_base")
    base = None if base_name == "none" else _source_labelled(spark, features, cfg, base_name).select(
        "l_id", "r_id", "label")
    merged = app if base is None else base.join(app.select("l_id", "r_id"), ["l_id", "r_id"], "left_anti") \
        .unionByName(app)
    out = features.join(merged, ["l_id", "r_id"])
    if usage is not None:
        n_app, n_used = app.count(), out.join(app.select("l_id", "r_id"), ["l_id", "r_id"]).count()
        usage["app_labels"] = {"store": {k: str(v) for k, v in store.location(cfg).items()}, "base": base_name,
                               "decisions": n_app, "used": n_used, "not_candidates": n_app - n_used,
                               "overrode_base": 0 if base is None else
                               base.join(app.select("l_id", "r_id"), ["l_id", "r_id"]).count()}
    return out


def split(labels: DataFrame, cfg: Config) -> tuple[DataFrame, DataFrame]:
    """(train, validation) by a hash of the left id: stable across runs and free of shared anchors."""
    cut = int(cfg.get("decision.validation_share") * 1000)
    bucket = F.pmod(F.xxhash64("l_id"), F.lit(1000))
    return labels.filter(bucket >= cut), labels.filter(bucket < cut)
