"""Optional offline embedding job; pair scoring sees materialized arrays only.

Prepare a SentenceTransformer snapshot separately; no model downloads here.
JSONL output must be visible to Spark (local path or Databricks Volume).
Driver memory is bounded by batch size. Auto keeps stable missing-value columns
when the extra/model is unavailable; explicit local selection fails instead.
"""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import time
import warnings

from pyspark.sql import functions as F

from .features import embedding_fields


def availability(config):
    spec = config["features"]["embeddings"]
    if not embedding_fields(config):
        return None
    if not spec["model"] or not Path(spec["model"]).is_dir():
        return "No prepared local embedding model directory; auto mode emits missing-value features"
    if importlib.util.find_spec("sentence_transformers") is None:
        return "Install the optional embeddings extra; auto mode emits missing-value features"
    return None


def model_digest(directory):
    digest = hashlib.sha256()
    for path in sorted(Path(directory).rglob("*")):
        if path.is_file() and not any(part.startswith(".") for part in path.relative_to(directory).parts):
            digest.update(str(path.relative_to(directory)).encode() + b"\0")
            with path.open("rb") as stream:
                while block := stream.read(1024 * 1024):
                    digest.update(block)
    return digest.hexdigest()


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def prepare(frame, config, output, *, provider=None, batch_size=128):
    names = embedding_fields(config)
    if not names:
        return frame, {"status": "disabled", "records": 0}
    reason = availability(config) if provider is None else None
    if reason:
        if config["features"]["embeddings"]["provider"] == "local":
            raise ValueError(reason)
        warnings.warn(reason, RuntimeWarning, stacklevel=2)
        for name in names:
            frame = frame.withColumn(f"lm_emb_{name}", F.array().cast("array<double>"))
        return frame, {"status": "unavailable", "reason": reason}
    if batch_size < 1:
        raise ValueError("Embedding batch_size must be positive")
    started = time.perf_counter()
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    model = config["features"]["embeddings"]["model"]
    digest = model_digest(model) if provider is None else "injected-test-provider"
    if provider is None:
        from sentence_transformers import SentenceTransformer
        provider = SentenceTransformer(model, device="cpu", local_files_only=True, trust_remote_code=False)
    count, dimension = 0, None
    def encode(rows, stream):
        nonlocal count, dimension
        result = [{"rec_id": row.rec_id} for row in rows]
        for name in names:
            nonempty = [(i, row[name]) for i, row in enumerate(rows) if row[name]]
            vectors = provider.encode([t for _, t in nonempty], batch_size=batch_size,
                                      normalize_embeddings=True, show_progress_bar=False) if nonempty else []
            if len(vectors) != len(nonempty):
                raise ValueError("Embedding provider returned the wrong number of vectors")
            for record in result:
                record[f"lm_emb_{name}"] = []
            for (i, _), vector in zip(nonempty, vectors):
                values = [float(x) for x in vector]
                if not values or not all(math.isfinite(x) for x in values) or not any(values):
                    raise ValueError("Embedding provider returned an empty, zero or nonfinite vector")
                dimension = dimension or len(values)
                if dimension != len(values):
                    raise ValueError("Embedding provider returned inconsistent vector dimensions")
                result[i][f"lm_emb_{name}"] = values
        for record in result:
            stream.write(json.dumps(record, allow_nan=False) + "\n")
        count += len(rows)
    with path.open("w") as stream:
        batch = []
        for row in frame.select("rec_id", *names).toLocalIterator():
            batch.append(row)
            if len(batch) == batch_size:
                encode(batch, stream)
                batch = []
        if batch:
            encode(batch, stream)
    schema = "rec_id string, " + ", ".join(f"lm_emb_{n} array<double>" for n in names)
    vectors = frame.sparkSession.read.schema(schema).json(str(path.resolve()))
    seconds = time.perf_counter() - started
    report = {"status": "prepared", "provider": "local", "model_sha256": digest,
              "records": count, "dimension": dimension, "seconds": seconds,
              "seconds_per_100000_records_extrapolated": seconds * 100000 / count if count else None,
              "batch_size": batch_size, "output_sha256": file_digest(path)}
    path.with_suffix(".manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    return frame.join(vectors, "rec_id", "left"), report
