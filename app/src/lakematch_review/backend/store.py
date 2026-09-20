"""SQLite locally; parameterized Statement Execution against Delta remotely.

Delta deployment uses one app worker and a process lock to serialize reviews.
This is not a distributed lease: do not deploy multiple writers to these tables.
Queue and metadata are prepared by jobs, never accepted from a browser.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading

from .models import PairOut, ReviewIn, ReviewOut, SnapshotOut, StatsOut

_writer = threading.RLock()
MAX_SNAPSHOT = 10000
TABLE_DDL = {
    "review_queue": "pair_id STRING, a_id STRING, b_id STRING, model_version STRING, uncertainty DOUBLE, impact BIGINT, payload STRING",
    "review_labels": "request_id STRING, pair_id STRING, payload STRING",
    "review_metadata": "key STRING, payload STRING",
}


class Conflict(ValueError):
    pass


def pair_key(model, a, b):
    return hashlib.sha256(json.dumps([model, a, b], separators=(",", ":")).encode()).hexdigest()


class Store:
    def query(self, sql, params=None):
        raise NotImplementedError

    def table(self, name):
        raise NotImplementedError

    @contextmanager
    def transaction(self):
        with _writer:
            yield

    def enqueue(self, pair: PairOut):
        """Job-only producer; no browser endpoint exposes queue writes."""
        if pair.pair_id != pair_key(pair.model_version, pair.a_id, pair.b_id):
            raise ValueError("Queue key must bind both records and the immutable model")
        with self.transaction():
            table = self.table("review_queue")
            existing = self.query(f"SELECT payload FROM {table} WHERE pair_id=:id", {"id": pair.pair_id})
            if existing:
                if PairOut.model_validate_json(existing[0][0]) != pair:
                    raise Conflict("A different queue item already uses this key")
                return
            uncertainty = 0.0 if pair.llm_decision == "unsure" else abs(pair.probability - pair.threshold)
            self.query(f"INSERT INTO {table} VALUES (:id,:a,:b,:model,:u,:impact,:payload)",
                       dict(id=pair.pair_id, a=pair.a_id, b=pair.b_id, model=pair.model_version,
                            u=str(uncertainty), impact=pair.impact, payload=pair.model_dump_json()))

    def queue(self, limit=20):
        q, labels = self.table("review_queue"), self.table("review_labels")
        rows = self.query(f"SELECT q.payload FROM {q} q WHERE NOT EXISTS (SELECT 1 FROM {labels} l WHERE l.pair_id=q.pair_id) ORDER BY q.uncertainty, q.impact DESC, q.pair_id LIMIT :limit", {"limit": limit})
        return [PairOut.model_validate_json(r[0]) for r in rows]

    def bounded_payloads(self, name):
        rows = self.query(f"SELECT payload FROM {self.table(name)} LIMIT {MAX_SNAPSHOT + 1}")
        if len(rows) > MAX_SNAPSHOT:
            raise ValueError("Review snapshot exceeds 10,000 rows; prepare a smaller review batch")
        return [json.loads(r[0]) for r in rows]

    def reviews(self):
        # Delta physical scan order is not a provenance order. Canonicalize
        # before snapshots/readback so a restart cannot reorder the history.
        return sorted((ReviewOut.model_validate(r) for r in self.bounded_payloads("review_labels")),
                      key=lambda r: (r.reviewed_at, r.request_id))

    def review(self, incoming: ReviewIn, user: str):
        with self.transaction():
            table = self.table("review_labels")
            previous = self.query(f"SELECT payload FROM {table} WHERE request_id=:id", {"id": incoming.request_id})
            if previous:
                existing = ReviewOut.model_validate_json(previous[0][0])
                if any(getattr(existing, k) != v for k, v in incoming.model_dump().items()) or existing.user != user:
                    raise Conflict("This request ID already belongs to a different review")
                return existing
            rows = self.query(f"SELECT payload FROM {self.table('review_queue')} WHERE pair_id=:id", {"id": incoming.pair_id})
            if len(rows) != 1:
                raise KeyError("Pair is not in this review batch")
            pair = PairOut.model_validate_json(rows[0][0])
            if pair.model_version != incoming.model_version:
                raise Conflict("The displayed model is stale; reload the queue")
            if self.query(f"SELECT payload FROM {table} WHERE pair_id=:id", {"id": pair.pair_id}):
                raise Conflict("This pair has already been reviewed; reload the queue")
            review = ReviewOut(**incoming.model_dump(), a_id=pair.a_id, b_id=pair.b_id,
                               user=user, reviewed_at=datetime.now(timezone.utc).isoformat())
            self.query(f"INSERT INTO {table} (request_id, pair_id, payload) VALUES (:request, :pair, :payload)",
                       {"request": review.request_id, "pair": review.pair_id, "payload": review.model_dump_json()})
            return review

    def snapshot(self):
        reviews = self.reviews()
        labels = {}
        for r in reviews:
            if r.decision == "unsure":
                continue
            pair, label = (r.a_id, r.b_id), int(r.decision == "match")
            if pair in labels and labels[pair] != label:
                raise Conflict("Conflicting labels across models require adjudication before training")
            labels[pair] = label
        canonical = [[a, b, float(y)] for (a, b), y in sorted(labels.items())]
        digest = hashlib.sha256(json.dumps(canonical, separators=(",", ":")).encode()).hexdigest()
        return SnapshotOut(labels=[{"a_id": a, "b_id": b, "label": y} for (a, b), y in sorted(labels.items())],
                           reviews=reviews, label_set_sha256=digest,
                           excluded_unsure=sum(r.decision == "unsure" for r in reviews))

    def stats(self):
        pairs = {p["pair_id"]: p for p in self.bounded_payloads("review_queue")}
        reviews = self.reviews()
        metadata = {k: json.loads(str(v)) for k, v in self.query(f"SELECT key, payload FROM {self.table('review_metadata')}")}
        compared = [r for r in reviews if r.decision != "unsure" and pairs.get(r.pair_id, {}).get("llm_decision") in {"match", "no_match"}]
        return StatsOut(queue_depth=len(set(pairs) - {r.pair_id for r in reviews}), reviewed=len(reviews),
                        match=sum(r.decision == "match" for r in reviews),
                        no_match=sum(r.decision == "no_match" for r in reviews),
                        unsure=sum(r.decision == "unsure" for r in reviews),
                        quarantine=metadata.get("quarantine"),
                        llm_compared=len(compared),
                        llm_agreement=sum(r.decision == pairs[r.pair_id]["llm_decision"] for r in compared) / len(compared) if compared else None,
                        evaluations=metadata.get("evaluations", []))


class SQLiteStore(Store):
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")
        for name, ddl in TABLE_DDL.items():
            self.connection.execute(f"CREATE TABLE IF NOT EXISTS {name} ({ddl.replace('STRING', 'TEXT')})")
        self.connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS review_request ON review_labels(request_id)")
        self.connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS review_pair ON review_labels(pair_id)")
        self.connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS queue_pair ON review_queue(pair_id)")
        self.connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS metadata_key ON review_metadata(key)")

    def table(self, name):
        if name not in TABLE_DDL:
            raise ValueError("Unknown review table")
        return name

    def query(self, sql, params=None):
        return self.connection.execute(sql, params or {}).fetchall()

    @contextmanager
    def transaction(self):
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def close(self):
        self.connection.close()


class DeltaStore(Store):
    def __init__(self, client, warehouse, schema):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*\.[A-Za-z_][A-Za-z_0-9]*", schema):
            raise ValueError("Expected a catalog.schema identifier")
        self.client, self.warehouse, self.schema = client, warehouse, schema

    def table(self, name):
        if name not in TABLE_DDL:
            raise ValueError("Unknown review table")
        return ".".join(f"`{p}`" for p in [*self.schema.split("."), name])

    def query(self, sql, params=None):
        from databricks.sdk.service.sql import StatementParameterListItem, StatementState, ExecuteStatementRequestOnWaitTimeout
        response = self.client.statement_execution.execute_statement(
            warehouse_id=self.warehouse, statement=sql,
            parameters=[StatementParameterListItem(name=k, value=str(v), type="BIGINT" if isinstance(v, int) else "STRING") for k, v in (params or {}).items()],
            wait_timeout="50s", on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CANCEL, row_limit=MAX_SNAPSHOT + 1,
        )
        if not response.status or response.status.state != StatementState.SUCCEEDED:
            if response.statement_id:
                self.client.statement_execution.cancel_execution(response.statement_id)
            raise RuntimeError("Review storage query failed or exceeded 50 seconds")
        if response.manifest and response.manifest.truncated:
            raise ValueError("Review query exceeded its bounded result size")
        if response.result and response.result.next_chunk_index is not None:
            raise ValueError("Review query exceeded a single result chunk")
        return (response.result.data_array or []) if response.result else []

    def close(self):
        pass
