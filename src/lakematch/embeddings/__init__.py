"""Embedding providers for organisation and title fields (D12). The vector is computed once per record at the entity
stage and kept in the entity table (`emb_<field>`, unit length, array<float>); pairs compare it with a built-in dot
product.

    features.embeddings.provider
        none                 no embedding feature
        auto                 the local provider if the `embeddings` extra is installed AND the model is already on
                             this machine; otherwise skipped with a warning (a laptop run never downloads)
        local                a model2vec static model (MIT), loaded from the Hugging Face cache or downloaded once
        databricks_endpoint  a Databricks embedding endpoint (features.embeddings.model, e.g. databricks-gte-large-en)
                             through the built-in SQL function ai_query: no Python UDF, so it also runs inside a
                             pipeline flow. Paid (Model Serving): needs paid_features.embedding_endpoint (ZR-6)

model2vec static models are a token -> vector table plus a mean: no GPU, no torch, a few thousand records per second
on one core. The model (features.embeddings.model) is picked by validation F1 in bench/ablation.py.
Computing the vector is a pandas UDF — record-level, once, flagged; it never runs per pair.
"""
# No `from __future__ import annotations` here: pandas_udf reads the type hints at definition time.
import logging

from pyspark.sql import DataFrame, functions as F

from ..config import Config

log = logging.getLogger("lakematch")
_MODELS: dict[str, object] = {}         # per process: path -> loaded StaticModel (executors reuse it across batches)
_RESOLVED: dict[tuple, object] = {}


class ProviderUnavailable(RuntimeError):
    pass


def _load(path: str):
    if path not in _MODELS:
        from model2vec import StaticModel
        _MODELS[path] = StaticModel.from_pretrained(path)
    return _MODELS[path]


def encode_texts(path: str, texts: list[str]):
    """Unit-length float32 vectors for `texts` (a numpy array, one row per text)."""
    import numpy as np
    vecs = np.asarray(_load(path).encode(list(texts)), dtype="float32")
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / np.where(norms == 0, 1, norms)


class LocalProvider:
    kind = "local"

    def __init__(self, model: str, cached_only: bool):
        try:
            import model2vec  # noqa: F401
            from huggingface_hub import snapshot_download
        except ImportError as e:
            raise ProviderUnavailable("the `embeddings` extra is not installed (pip install lakematch[embeddings])") from e
        try:
            self.path = snapshot_download(model, local_files_only=cached_only)
        except Exception as e:
            raise ProviderUnavailable(f"model {model} is not on this machine" if cached_only
                                      else f"model {model} could not be fetched: {e}") from e
        self.model = model
        self._udf = None

    def encode(self, texts: list[str]):
        return encode_texts(self.path, texts)

    def udf(self):
        if self._udf is None:
            import pandas as pd
            from pyspark.sql.functions import pandas_udf
            path = self.path

            @pandas_udf("array<float>")
            def embed(texts: pd.Series) -> pd.Series:
                vecs = encode_texts(path, texts.fillna("").tolist())
                return pd.Series([v.tolist() for v in vecs])
            self._udf = embed
        return self._udf

    def add_column(self, df: DataFrame, field: str) -> DataFrame:
        col = F.col(field)
        return df.withColumn(f"emb_{field}", F.when(F.length(col) > 0, self.udf()(col)))


class EndpointProvider:
    """ai_query(<endpoint>, text) -> array<float>, normalised to unit length with built-ins."""
    kind = "databricks_endpoint"

    def __init__(self, endpoint: str):
        self.model = endpoint

    def add_column(self, df: DataFrame, field: str) -> DataFrame:
        name = self.model.replace("'", "")
        raw = F.expr(f"ai_query('{name}', CAST(`{field}` AS STRING))").cast("array<float>")
        unit = F.transform(raw, lambda x: x / F.sqrt(F.aggregate(raw, F.lit(0.0), lambda a, y: a + y * y)))
        return df.withColumn(f"emb_{field}", F.when(F.length(F.col(field)) > 0, unit.cast("array<float>")))


def resolve(cfg: Config, quiet: bool = False):
    """The provider the config asks for, or None when the embedding feature is off or unavailable."""
    kind = cfg.require("features.embeddings.provider")
    model = cfg.get("features.embeddings.model")
    key = (kind, model)
    if key in _RESOLVED:
        return _RESOLVED[key]
    provider = None
    if kind == "databricks_endpoint":
        if not cfg.get("paid_features.embedding_endpoint"):
            raise ProviderUnavailable("features.embeddings.provider databricks_endpoint is a paid feature: set "
                                      "paid_features.embedding_endpoint: true")
        provider = EndpointProvider(model)
    if kind in ("auto", "local"):
        try:
            provider = LocalProvider(model, cached_only=(kind == "auto"))
        except ProviderUnavailable as e:
            if kind == "local":
                raise
            if not quiet:
                log.warning("embeddings: provider auto skipped the embedding feature — %s", e)
    _RESOLVED[key] = provider
    return provider
