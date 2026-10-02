"""The pair classifier: an MLlib estimator over the comparison vector (`matcher.estimator`).

Training is a job-task step (MLlib `fit` is an action, refused inside a pipeline flow). Scoring is lazy: either
`model.transform`, or the same model compiled to one Spark SQL expression (scoring_sql.py) — what the Databricks
pipeline uses, since importing pyspark.ml there crashes the runtime. tracking.py logs both to MLflow (ZR-5, ZR-6).
"""
from __future__ import annotations

from pyspark.ml import Pipeline, PipelineModel
from pyspark.ml.classification import GBTClassifier, LogisticRegression, RandomForestClassifier
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.functions import vector_to_array
from pyspark.sql import DataFrame, functions as F

from .config import Config

# Starting hyper-parameters (the prototype's); ZR-3 compares them on validation data. matcher.params overrides.
ESTIMATORS = {
    "gbt": (GBTClassifier, {"maxIter": 60, "maxDepth": 3}),
    "logistic_regression": (LogisticRegression, {"maxIter": 100, "regParam": 0.001}),
    "random_forest": (RandomForestClassifier, {"numTrees": 100, "maxDepth": 6}),
}


def train(labelled: DataFrame, feature_cols: list[str], cfg: Config) -> PipelineModel:
    name = cfg.require("matcher.estimator")
    cls, params = ESTIMATORS[name]
    params = {**params, **(cfg.get("matcher.params") or {})}
    if name != "logistic_regression":                    # the tree ensembles are randomised; fix their seed
        params.setdefault("seed", cfg.get("matcher.seed"))
    est = cls(featuresCol="features", labelCol="label", **params)
    return Pipeline(stages=[VectorAssembler(inputCols=feature_cols, outputCol="features"), est]).fit(labelled)


def score(model: PipelineModel | str, pairs: DataFrame) -> DataFrame:
    """Adds `p`, the probability of a match; drops MLlib's working columns. `model` may be the compiled SQL
    expression of a fitted model (scoring_sql.compile_saved): same p, no MLlib."""
    if isinstance(model, str):
        return pairs.withColumn("p", F.expr(model))
    out = model.transform(pairs).withColumn("p", vector_to_array("probability")[1])
    return out.drop("features", "rawPrediction", "probability", "prediction")
