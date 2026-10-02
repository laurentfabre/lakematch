"""The composite lakematch model, logged as MLflow models-from-code (ZR-5; tracking.py logs it).

One pyfunc whose artifacts are the whole bundle: the fitted Spark ML pipeline (assembler + classifier), the run's
config (feature and candidate spec), the label-set digest and the decision thresholds. Input = one row per pair
(l_id, r_id and the comparison vector the config names); output = l_id, r_id, p (match probability) and
above_threshold. The cardinality policy is a set-level decision over all pairs of a run (decision.links), so the
pair-level model stops at the threshold.

Self-contained on purpose: it imports pyspark and mlflow only, so a model resolved by run id or by alias loads
anywhere those two are installed. The Spark pipeline is loaded on the first predict, not at load time, so loading
the model (signature, metadata, thresholds) never starts a JVM.
"""
import json

import mlflow
from mlflow.pyfunc import PythonModel


class LakematchPairModel(PythonModel):
    def load_context(self, context):
        self._pipeline_path = context.artifacts["spark_pipeline"]
        with open(context.artifacts["config"]) as fh:
            self.config = json.load(fh)
        with open(context.artifacts["thresholds"]) as fh:
            self.thresholds = json.load(fh)
        with open(context.artifacts["label_set"]) as fh:
            self.label_set = json.load(fh)
        self.feature_cols = self.thresholds["feature_cols"]
        self._pipeline = None

    def _spark(self):
        from pyspark.sql import SparkSession
        active = SparkSession.getActiveSession()
        if active is not None:
            return active
        try:
            from pyspark.sql.connect.session import SparkSession as ConnectSession
            active = ConnectSession.getActiveSession()
        except ImportError:
            active = None
        return active or SparkSession.builder.master("local[1]").config("spark.ui.enabled", "false").getOrCreate()

    def predict(self, context, model_input, params=None):
        from pyspark.ml import PipelineModel
        from pyspark.ml.functions import vector_to_array

        spark = self._spark()
        if self._pipeline is None:
            self._pipeline = PipelineModel.load(self._pipeline_path)
        cols = ["l_id", "r_id", *self.feature_cols]
        pdf = model_input[cols].astype({c: "float64" for c in self.feature_cols})
        pdf = pdf.astype({"l_id": "str", "r_id": "str"})
        scored = self._pipeline.transform(spark.createDataFrame(pdf))
        out = (scored.withColumn("p", vector_to_array("probability")[1])     # = matcher.score
               .select("l_id", "r_id", "p").toPandas())
        out = out.set_index(["l_id", "r_id"]).reindex(list(zip(pdf["l_id"], pdf["r_id"]))).reset_index()
        out["above_threshold"] = out["p"] >= self.thresholds["threshold"]
        return out


mlflow.models.set_model(LakematchPairModel())
