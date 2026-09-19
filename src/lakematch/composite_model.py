"""Models-from-code entry point for driver/job batch prediction.

Input is a complete candidate-pair snapshot with raw record JSON and the frozen
retrieval features. Cardinality is applied over that snapshot, not across calls.
"""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import tempfile

import mlflow
import pandas as pd
from pyspark.ml import PipelineModel
from pyspark.sql import functions as F

from lakematch import decision, embeddings, entity, feature_stats, features, matcher
from lakematch.config import from_dict
from lakematch.runtime import active_or_create, model_artifact_path


class PairModel(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        from lakematch.tracking import validate_artifacts
        validate_artifacts(context.artifacts)
        self.contract = json.loads(Path(context.artifacts["contract"]).read_text())
        raw = deepcopy(self.contract["config"])
        if "embedding_model" in context.artifacts:
            raw["features"]["embeddings"]["model"] = context.artifacts["embedding_model"]
        self.config = from_dict(raw)
        if features.feature_order(self.config) != self.contract["feature_order"]:
            raise ValueError("Composite model feature order differs from its recorded contract")
        self.artifacts = context.artifacts
        self.model = None

    def native_model(self, spark=None):
        spark = spark or active_or_create(self.config)
        if self.model is None:
            self.model = PipelineModel.load(model_artifact_path(self.artifacts["pipeline"]))
        return self.model

    def predict(self, context, model_input: pd.DataFrame, params=None) -> pd.DataFrame:
        if len(model_input) > self.config["candidates"]["max_pairs"]:
            raise ValueError("Composite model input exceeds its recorded candidate-pair budget")
        if not len(model_input):
            return pd.DataFrame({"a_id": pd.Series(dtype=str), "b_id": pd.Series(dtype=str),
                                 "p": pd.Series(dtype=float), "is_link": pd.Series(dtype=bool)})
        records = {"left": {}, "right": {}}
        pairs, seen = [], set()
        for i, row in enumerate(model_input.to_dict(orient="records")):
            a, b = row["a_id"], row["b_id"]
            if not isinstance(a, str) or not isinstance(b, str) or not a or not b or (a, b) in seen:
                raise ValueError("Candidate pairs need nonempty IDs and unique pair keys")
            seen.add((a, b))
            for side, key in (("left", a), ("right", b)):
                value = json.loads(row[side])
                if not isinstance(value, dict) or set(value) - set(self.config.fields):
                    raise ValueError("Pair record JSON must contain only configured fields")
                if key in records[side] and records[side][key] != value:
                    raise ValueError("One record ID has conflicting payloads within the candidate snapshot")
                records[side][key] = value
            cos, rank, gap = float(row["cos"]), int(row["rank"]), float(row["gap"])
            if (not math.isfinite(cos) or not math.isfinite(gap) or not 0 <= cos <= 1 or
                    rank < 1 or rank != row["rank"] or not 0 <= gap <= 1):
                raise ValueError("Invalid candidate retrieval features")
            pairs.append((a, b, cos, rank, gap, i))
        spark = active_or_create(self.config)
        schema = f"{self.config['entity']['id_column']} string, " + ", ".join(
            f"{n} " + ("array<string>" if spec.get("multiple") else "string")
            for n, spec in self.config["entity"]["fields"].items())
        def prepared(side):
            rows = []
            for ident, values in records[side].items():
                row = {self.config["entity"]["id_column"]: ident}
                for name, spec in self.config["entity"]["fields"].items():
                    value = values.get(name)
                    if spec.get("multiple"):
                        if value is not None and not isinstance(value, list):
                            raise ValueError("Configured multi-valued field must be a JSON array")
                        row[name] = [str(v) if v is not None else None for v in value] if value is not None else None
                    else:
                        if isinstance(value, (list, dict)):
                            raise ValueError("Configured scalar field cannot be an array/object")
                        row[name] = str(value) if value is not None else None
                rows.append(row)
            frame = entity.prepare(spark.createDataFrame(rows, schema), self.config)
            if "idf_token_cosine" in self.config["features"]["multi_token"]:
                vocabulary = spark.read.parquet(model_artifact_path(self.artifacts["idf"]))
                frame = feature_stats.attach_idf(frame, vocabulary, self.config)
            return frame
        a, b = prepared("left"), prepared("right")
        candidates = spark.createDataFrame(pairs, "a_id string, b_id string, cos double, rank long, gap double, lm_order long")
        # The Databricks job sets MLFLOW_DFS_TMP to its owned UC Volume.
        with tempfile.TemporaryDirectory(prefix="lakematch-predict-", dir=os.environ.get("MLFLOW_DFS_TMP")) as temporary:
            a, _ = embeddings.prepare(a, self.config, Path(temporary) / "left.jsonl")
            b, _ = embeddings.prepare(b, self.config, Path(temporary) / "right.jsonl")
            comparisons = features.build(candidates, a, b, self.config)
            scored = matcher.score(comparisons, self.native_model(spark))
            selected = decision.links(scored, self.config).select("a_id", "b_id", F.lit(True).alias("is_link"))
            result = (scored.select("a_id", "b_id", "p").join(selected, ["a_id", "b_id"], "left")
                      .fillna(False, ["is_link"]).join(candidates.select("a_id", "b_id", "lm_order"), ["a_id", "b_id"])
                      .orderBy("lm_order").select("a_id", "b_id", "p", "is_link").toPandas())
        return result


mlflow.models.set_model(PairModel())
