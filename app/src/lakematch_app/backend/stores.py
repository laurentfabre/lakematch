"""Queue sources and label stores. The label rows follow the engine's contract, lakematch/labels/store.py
STORE_COLUMNS (tests/test_contract.py checks the two agree); the app never imports the engine.

Sources (the queue and the run history, read-only):
    LocalSource       <review_dir>/queue (Parquet) and <review_dir>/runs.jsonl
    WarehouseSource   <schema>.lm_review_queue and <schema>.lm_review_runs through the SQL warehouse

Label stores (append-only; a pair's label is its latest row, `retract` withdraws it):
    LocalDeltaStore      <review_dir>/labels, a Delta directory (deltalake)
    WarehouseDeltaStore  <schema>.lm_review_labels, a Delta table, INSERT through the SQL warehouse
    LakebaseStore        a Postgres table in Lakebase (psycopg), created on first use
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from functools import lru_cache
from typing import Any, Protocol

LABEL_COLUMNS: list[tuple[str, str]] = [
    ("l_id", "string"), ("r_id", "string"), ("decision", "string"), ("is_match", "double"),
    ("reviewer", "string"), ("labelled_at", "timestamp"), ("model_version", "string"), ("p", "double"),
    ("threshold", "double"), ("reason", "string"), ("queue_reason", "string"), ("llm_label", "string"),
    ("run_id", "string"), ("label_id", "string"),
]
LABEL_NAMES = [n for n, _ in LABEL_COLUMNS]
QUEUE_META = ["rank", "l_id", "r_id", "p", "threshold", "distance", "queue_reason", "llm_label", "llm_p_same",
              "linked", "impact", "cand_score", "cand_rank", "model_version", "run_id"]
QUEUE_FULL = QUEUE_META + ["l_record", "r_record", "created_at"]


def _iso(v: Any) -> Any:
    if isinstance(v, datetime):
        return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()
    return v


def _plain(row: dict) -> dict:
    return {k: _iso(v) for k, v in row.items()}


class Source(Protocol):
    def queue(self, *, full: bool, limit: int | None = None) -> list[dict]: ...
    def pair(self, l_id: str, r_id: str) -> dict | None: ...
    def runs(self) -> list[dict]: ...
    def describe(self) -> str: ...


class LabelStore(Protocol):
    def append(self, row: dict) -> None: ...
    def events(self) -> list[dict]: ...
    def describe(self) -> str: ...


# --- laptop ---------------------------------------------------------------------------------------------------------

class LocalSource:
    def __init__(self, review_dir: Path):
        self.dir = review_dir

    def describe(self) -> str:
        return f"local files {self.dir}"

    def queue(self, *, full: bool, limit: int | None = None) -> list[dict]:
        import pyarrow.parquet as pq
        path = self.dir / "queue"
        if not path.exists():
            return []
        rows = pq.read_table(path, columns=QUEUE_FULL if full else QUEUE_META).to_pylist()
        rows.sort(key=lambda r: r["rank"])
        return [_plain(r) for r in (rows[:limit] if limit else rows)]

    def pair(self, l_id: str, r_id: str) -> dict | None:
        return next((r for r in self.queue(full=True) if r["l_id"] == l_id and r["r_id"] == r_id), None)

    def runs(self) -> list[dict]:
        path = self.dir / "runs.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class LocalDeltaStore:
    def __init__(self, review_dir: Path):
        self.path = review_dir / "labels"

    def describe(self) -> str:
        return f"Delta directory {self.path}"

    @staticmethod
    def _schema():
        import pyarrow as pa
        kinds = {"string": pa.string(), "double": pa.float64(), "timestamp": pa.timestamp("us", tz="UTC")}
        return pa.schema([(n, kinds[t]) for n, t in LABEL_COLUMNS])

    def append(self, row: dict) -> None:
        import pyarrow as pa
        from deltalake import write_deltalake
        rec = dict(row)
        rec["labelled_at"] = datetime.fromisoformat(rec["labelled_at"])
        table = pa.Table.from_pylist([rec], schema=self._schema())
        write_deltalake(str(self.path), table, mode="append")   # optimistic commit: safe across app workers

    def events(self) -> list[dict]:
        from deltalake import DeltaTable
        if not (self.path / "_delta_log").is_dir():
            return []
        return [_plain(r) for r in DeltaTable(str(self.path)).to_pyarrow_table(columns=LABEL_NAMES).to_pylist()]


# --- SQL warehouse --------------------------------------------------------------------------------------------------

class Warehouse:
    """Statement Execution API with the app's own credentials (its service principal on Databricks, the profile in
    .env on a laptop). A stopped serverless warehouse starts on the first statement; this waits for it."""
    TYPES = {"string": "STRING", "double": "DOUBLE", "timestamp": "TIMESTAMP", "int": "INT"}

    def __init__(self, warehouse_id: str | None):
        if not warehouse_id:
            raise RuntimeError("LAKEMATCH_APP_SOURCE=warehouse needs DATABRICKS_SQL_WAREHOUSE_ID (the app's "
                               "sql-warehouse resource)")
        from databricks.sdk import WorkspaceClient
        self.ws, self.id = WorkspaceClient(), warehouse_id

    def run(self, sql: str, params: dict[str, tuple[Any, str]] | None = None, timeout_s: float = 180) -> list[dict]:
        from databricks.sdk.service.sql import (Disposition, Format, StatementParameterListItem, StatementState)
        items = [StatementParameterListItem(name=k, value=None if v is None else str(v), type=self.TYPES[t])
                 for k, (v, t) in (params or {}).items()]
        api = self.ws.statement_execution
        r = api.execute_statement(statement=sql, warehouse_id=self.id, parameters=items or None, wait_timeout="30s",
                                  disposition=Disposition.INLINE, format=Format.JSON_ARRAY)
        sid = r.statement_id or ""
        state = r.status.state if r.status else None
        deadline = time.time() + timeout_s
        while state in (StatementState.PENDING, StatementState.RUNNING):
            if time.time() > deadline:
                api.cancel_execution(sid)
                raise TimeoutError(f"statement still {state} after {timeout_s:.0f} s")
            time.sleep(1.0)
            r = api.get_statement(sid)
            state = r.status.state if r.status else None
        if state != StatementState.SUCCEEDED:
            err = r.status.error.message if r.status and r.status.error else state
            raise RuntimeError(f"SQL warehouse: {err}")
        if not r.manifest or not r.manifest.schema or not r.manifest.schema.columns:
            return []
        cols = [(c.name, (c.type_name.value if c.type_name else "STRING")) for c in r.manifest.schema.columns]
        data = list((r.result.data_array if r.result else None) or [])
        for n in range(1, r.manifest.total_chunk_count or 1):
            data += api.get_statement_result_chunk_n(sid, n).data_array or []
        return [{name: _cast(v, kind) for (name, kind), v in zip(cols, row)} for row in data]


def _cast(v: str | None, kind: str) -> Any:
    if v is None:
        return None
    if kind in ("DOUBLE", "FLOAT", "DECIMAL"):
        return float(v)
    if kind in ("INT", "LONG", "SHORT", "BYTE"):
        return int(v)
    if kind == "BOOLEAN":
        return v.lower() == "true"
    if kind == "TIMESTAMP":
        return datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    return v


class WarehouseSource:
    def __init__(self, wh: Warehouse, schema: str):
        self.wh, self.schema = wh, schema

    def describe(self) -> str:
        return f"{self.schema}.lm_review_queue via SQL warehouse {self.wh.id}"

    def queue(self, *, full: bool, limit: int | None = None) -> list[dict]:
        cols = ", ".join(QUEUE_FULL if full else QUEUE_META)
        lim = f" LIMIT {int(limit)}" if limit else ""
        try:
            return self.wh.run(f"SELECT {cols} FROM {self.schema}.lm_review_queue ORDER BY rank{lim}")
        except RuntimeError as e:
            if "TABLE_OR_VIEW_NOT_FOUND" in str(e):
                return []
            raise

    def pair(self, l_id: str, r_id: str) -> dict | None:
        rows = self.wh.run(f"SELECT {', '.join(QUEUE_FULL)} FROM {self.schema}.lm_review_queue "
                           "WHERE l_id = :l AND r_id = :r", {"l": (l_id, "string"), "r": (r_id, "string")})
        return rows[0] if rows else None

    def runs(self) -> list[dict]:
        try:
            return self.wh.run(f"SELECT * FROM {self.schema}.lm_review_runs ORDER BY created_at")
        except RuntimeError as e:
            if "TABLE_OR_VIEW_NOT_FOUND" in str(e):
                return []
            raise


class WarehouseDeltaStore:
    def __init__(self, wh: Warehouse, schema: str):
        self.wh, self.table = wh, f"{schema}.lm_review_labels"

    def describe(self) -> str:
        return f"Delta table {self.table} via SQL warehouse {self.wh.id}"

    def append(self, row: dict) -> None:
        names = ", ".join(LABEL_NAMES)
        marks = ", ".join(f":{n}" for n in LABEL_NAMES)
        self.wh.run(f"INSERT INTO {self.table} ({names}) VALUES ({marks})",
                    {n: (row[n], t) for n, t in LABEL_COLUMNS})

    def events(self) -> list[dict]:
        return self.wh.run(f"SELECT {', '.join(LABEL_NAMES)} FROM {self.table}")


# --- Lakebase (paid_features.lakebase_label_store) ------------------------------------------------------------------

class LakebaseStore:
    """Postgres. Under `apx dev`: the dev server's embedded database (APX_DEV_DB_PORT / APX_DEV_DB_PWD). As a
    Databricks App: the database resource's PGHOST / PGPORT / PGUSER (the service principal) / PGAPPNAME (the
    instance), with a short-lived OAuth credential per connection. The engine reads the same rows through the Lakebase
    database catalog registered in Unity Catalog (labels.store.table)."""
    PG = {"string": "TEXT", "double": "DOUBLE PRECISION", "timestamp": "TIMESTAMPTZ"}

    def __init__(self, table: str, database: str):
        self.table, self.database = table, database
        self._ready = False

    def describe(self) -> str:
        where = "embedded dev Postgres" if os.environ.get("APX_DEV_DB_PORT") else f"Lakebase {os.environ.get('PGHOST')}"
        return f"Postgres table {self.table} ({where})"

    def _connect(self):
        import psycopg
        port = os.environ.get("APX_DEV_DB_PORT")
        if port:
            return psycopg.connect(host="localhost", port=int(port), user="postgres", dbname="postgres",
                                   password=os.environ.get("APX_DEV_DB_PWD"), sslmode="disable", autocommit=True)
        from databricks.sdk import WorkspaceClient
        ws, instance = WorkspaceClient(), os.environ["PGAPPNAME"]
        token = ws.database.generate_database_credential(instance_names=[instance]).token
        return psycopg.connect(host=os.environ["PGHOST"], port=int(os.environ.get("PGPORT", "5432")),
                               user=os.environ.get("PGUSER") or ws.config.client_id, dbname=self.database,
                               password=token, sslmode="require", autocommit=True)

    def _ensure(self, conn) -> None:
        if self._ready:                      # a cache of "CREATE IF NOT EXISTS already ran", not of data
            return
        schema = self.table.split(".")[0] if "." in self.table else None
        cols = ", ".join(f"{n} {self.PG[t]}" for n, t in LABEL_COLUMNS)
        with conn.cursor() as cur:
            if schema:
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            cur.execute(f"CREATE TABLE IF NOT EXISTS {self.table} ({cols}, PRIMARY KEY (label_id))")
        self._ready = True

    def append(self, row: dict) -> None:
        with self._connect() as conn:
            self._ensure(conn)
            with conn.cursor() as cur:
                cur.execute(f"INSERT INTO {self.table} ({', '.join(LABEL_NAMES)}) "
                            f"VALUES ({', '.join(['%s'] * len(LABEL_NAMES))})", [row[n] for n in LABEL_NAMES])

    def events(self) -> list[dict]:
        with self._connect() as conn:
            self._ensure(conn)
            with conn.cursor() as cur:
                cur.execute(f"SELECT {', '.join(LABEL_NAMES)} FROM {self.table}")
                return [_plain(dict(zip(LABEL_NAMES, r))) for r in cur.fetchall()]


@lru_cache(maxsize=4)
def _warehouse(warehouse_id: str | None) -> Warehouse:
    return Warehouse(warehouse_id)       # one authenticated client per process: credentials, not data


def build(cfg) -> tuple[Source, LabelStore]:
    """The configured source and label store (cheap objects, built per request)."""
    wh = _warehouse(cfg.warehouse_id) if cfg.source == "warehouse" else None
    source = LocalSource(cfg.require_review_dir()) if wh is None else WarehouseSource(wh, cfg.schema_name)
    if cfg.label_store == "lakebase":
        return source, LakebaseStore(cfg.lakebase_table, cfg.lakebase_database)
    if wh is None:
        return source, LocalDeltaStore(cfg.require_review_dir())
    return source, WarehouseDeltaStore(wh, cfg.schema_name)
