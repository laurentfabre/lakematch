"""MLlib estimators; fit is task-only, score is a lazy transformation."""
from pyspark.ml import Pipeline
from pyspark.ml.classification import GBTClassifier, LogisticRegression, RandomForestClassifier
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.functions import vector_to_array
from pyspark.sql import functions as F

from .features import feature_order


def train(features, labels, config):
    counts = labels.groupBy("a_id", "b_id").agg(F.countDistinct("label").alias("n"))
    if counts.filter("n > 1").limit(1).count():
        raise ValueError("Conflicting labels for the same pair")
    if labels.filter(F.col("label").isNull() | ~F.col("label").isin(0.0, 1.0)).limit(1).count():
        raise ValueError("Training labels must be 0 or 1; unsure labels must be excluded explicitly")
    training = features.join(labels.select("a_id", "b_id", "label").dropDuplicates(["a_id", "b_id"]), ["a_id", "b_id"])
    if {r.label for r in training.select("label").distinct().collect()} != {0.0, 1.0}:
        raise ValueError("Candidate training set must contain both positive and negative labels")
    spec = config["matcher"]
    options = {"featuresCol": "features", "labelCol": "label"}
    if spec["estimator"] == "gbt":
        estimator = GBTClassifier(**options, maxIter=spec["max_iter"], maxDepth=spec["max_depth"], seed=spec["seed"])
    elif spec["estimator"] == "random_forest":
        estimator = RandomForestClassifier(**options, numTrees=spec["max_iter"], maxDepth=spec["max_depth"], seed=spec["seed"])
    else:
        estimator = LogisticRegression(**options, maxIter=spec["max_iter"], regParam=0.01)
    return Pipeline(stages=[VectorAssembler(inputCols=feature_order(config), outputCol="features"), estimator]).fit(
        training.orderBy("a_id", "b_id"))


def score(features, model):
    return model.transform(features).withColumn("p", vector_to_array("probability")[1])
