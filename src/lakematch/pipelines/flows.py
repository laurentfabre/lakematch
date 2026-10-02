"""The Databricks pipeline (ZR-6): ONE serverless Spark Declarative Pipeline (Free Edition runs one active pipeline per
type), every lazy stage a materialized view. Open-source pipelines API only (`pyspark.pipelines`).

    lm_left_valid, lm_right_valid             inputs past the quality gate (quality.engine: dqx on Databricks, D18;
                                              expectations: Lakeflow expect_all_or_drop, counts in the event log)
    lm_left_quarantine, lm_right_quarantine   the rows the gate refused, with `_errors` / `_warnings`
    lm_left_entity, lm_right_entity           entity view + record-level features (features.prepare_sides)
    lm_candidates                             candidates.generate with the plan task's plan: no action in the flow
    lm_features                               comparison vectors (l_id, r_id, feature columns)
    lm_scores                                 p from the champion's compiled scoring expression
    lm_links                                  decision policy: threshold + cardinality

Settings (pipeline `configuration`): `lakematch.config`, the YAML path (a synced workspace file); the source root
(`src/`) is on sys.path through the pipeline's `root_path`.

Read at import (allowed there, not inside a dataset function): `<storage.root>/candidate_plan.json` from the plan
task and `<storage.root>/champion.json` from the train task (tracking.write_handoff). Neither MLlib nor MLflow is
imported here: either one crashes a serverless pipeline (the runtime's notebook advice hook, measured 2026-10-02), so
scoring is the compiled expression (scoring_sql.py) and the registry is read by the job tasks around the pipeline.
The job refreshes valid → features, trains, then refreshes scores and links; until a champion exists the scores
view is an empty placeholder, and the cluster task refuses links whose model_version is not the one @alias names.
"""
import json
from pathlib import Path

from pyspark import pipelines as dp
from pyspark.sql import SparkSession, functions as F

from lakematch import candidates, decision, entity, features, quality
from lakematch.config import load
from lakematch.io import read_table

spark = SparkSession.active()
CFG = load(spark.conf.get("lakematch.config"))
ROOT = CFG.path(CFG.get("storage.root"))


def _json(name: str):
    p = Path(ROOT) / name
    return json.loads(p.read_text()) if p.exists() else None


PLAN = _json("candidate_plan.json")
CHAMPION = _json("champion.json")
SIDES = ("left", "right")
SPARK_VERSION = spark.version


def _entity(df, side: str, check: bool):
    return entity.prepare(df, CFG, CFG.get(f"inputs.{side}.id"), check=check)


# Column lists, worked out here at import from the inputs' headers (no data read): an open-source flow refuses any
# plan analysis (df.columns) inside a dataset function; Databricks allows it, but one code path serves both.
ENTITY_COLUMNS = [df.columns for df in features.prepare_sides(
    *[_entity(read_table(spark, CFG, CFG.get(f"inputs.{s}")).limit(0), s, check=True) for s in SIDES], CFG)]


def _gate(side: str):
    spec = CFG.get(f"inputs.{side}")
    return quality.engine(CFG).split(read_table(spark, CFG, spec), quality.input_specs(CFG, spec["id"], side))


def _define_gate(side: str):
    if CFG.get("quality.engine") == "expectations":      # Lakeflow expectations: counts land in the event log
        from lakematch.quality import expectations
        spec = CFG.get(f"inputs.{side}")
        drop, warn, dataset = expectations.constraints(quality.input_specs(CFG, spec["id"], side))

        @dp.materialized_view(name=f"lm_{side}_valid", comment=f"{side} input past the quality gate (expectations)")
        @dp.expect_all_or_drop(drop)
        @dp.expect_all(warn or {"always": "true"})
        def valid():
            return expectations.with_dataset_flags(read_table(spark, CFG, spec), dataset)
    else:
        @dp.materialized_view(name=f"lm_{side}_valid", comment=f"{side} input past the quality gate")
        def valid():
            return _gate(side)[0]

    @dp.materialized_view(name=f"lm_{side}_quarantine", comment=f"{side} rows the quality gate refused")
    def quarantined():
        return _gate(side)[1]


def _sides():
    ents = [_entity(spark.read.table(f"lm_{s}_valid"), s, check=False) for s in SIDES]
    return features.prepare_sides(ents[0], ents[1], CFG)


def _define_entity(i: int, side: str):
    @dp.materialized_view(name=f"lm_{side}_entity", comment=f"{side} entity view with record-level features")
    def ent():
        return _sides()[i]


for _i, _side in enumerate(SIDES):
    _define_gate(_side)
    _define_entity(_i, _side)


@dp.materialized_view(name="lm_candidates", comment="candidate pairs: proposals ranked by IDF gram cosine, top k")
def lm_candidates():
    if PLAN is None:
        raise ValueError(f"{ROOT}/candidate_plan.json is missing: the job's plan task writes it before this refresh")
    return candidates.generate(spark.read.table("lm_left_entity"), spark.read.table("lm_right_entity"), CFG,
                               plan=PLAN)


def _pairs():
    left, right = spark.read.table("lm_left_entity"), spark.read.table("lm_right_entity")
    pre = lambda df, cols, p, idc: df.select([F.col(c).alias(idc if c == "id" else f"{p}{c}") for c in cols])
    joined = (spark.read.table("lm_candidates").join(pre(left, ENTITY_COLUMNS[0], "l_", "l_id"), "l_id")
              .join(pre(right, ENTITY_COLUMNS[1], "r_", "r_id"), "r_id"))
    return features.compare(joined, CFG, spark_version=SPARK_VERSION)


@dp.materialized_view(name="lm_features", comment="comparison vectors of the candidate pairs")
def lm_features():
    df, cols = _pairs()
    return df.select("l_id", "r_id", *cols)


@dp.materialized_view(name="lm_scores", comment="match probability from the champion's compiled expression")
def lm_scores():
    feats = spark.read.table("lm_features")
    if CHAMPION is None:                       # first refresh of a new deployment: nothing trained yet
        return feats.select("l_id", "r_id", F.lit(None).cast("double").alias("p"),
                            F.lit(None).cast("string").alias("model_version")).limit(0)
    return feats.select("l_id", "r_id", F.expr(CHAMPION["expr"]).alias("p"),
                        F.lit(str(CHAMPION["version"])).alias("model_version"))


@dp.materialized_view(name="lm_links", comment="links: threshold and cardinality policy of the champion")
def lm_links():
    scores = spark.read.table("lm_scores")
    threshold = CHAMPION["threshold"] if CHAMPION else 1.1
    return decision.links(scores, threshold, CFG, columns=["l_id", "r_id", "p", "model_version"])
