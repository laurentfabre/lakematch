"""The one module where Spark sessions differ: session factory, is_remote(), capability probe, materialize().

Everything else in lakematch is written against the DataFrame API that a classic session, a local Spark Connect
server, Databricks serverless and Databricks classic all share. The constructs that only some of them allow
(SparkContext, cache(), local paths) are reached through this module and nowhere else — the portability lint in
tests/test_portability.py enforces it.

Modes (config `runtime.mode`, plus `runtime.connect` on the laptop):
    local            classic in-process session, master local[cores]
    local + connect  a local Spark Connect server (what serverless behaves like: a plan, no SparkContext)
    serverless       Databricks Connect, serverless compute (ZR-6)
    classic          Databricks Connect to a cluster on the paid workspace, profile from classic.profile (ZR-9)
"""
from __future__ import annotations

import logging
import os
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession

from .config import Config, MethodNotReady

log = logging.getLogger("lakematch")

# Keep a laptop session offline: the driver, the block manager and the Connect server bind to loopback only.
_LOOPBACK = {"spark.driver.host": "127.0.0.1", "spark.driver.bindAddress": "127.0.0.1"}


def is_remote(spark: SparkSession) -> bool:
    """True for any Spark Connect session (local server, serverless, Databricks Connect): no SparkContext there."""
    return type(spark).__module__.startswith(("pyspark.sql.connect", "databricks.connect"))


def _java_check() -> None:
    home = os.environ.get("JAVA_HOME")
    if not home:
        log.warning("JAVA_HOME is unset: Spark 4.1 needs Java 17 or 21 (it dies on 23+); source scripts/env.sh")


def session(cfg: Config) -> SparkSession:
    """Build the session the config asks for. Callers never branch on the mode after this."""
    mode = cfg.require("runtime.mode")
    cores, parts = cfg.get("runtime.cores"), str(cfg.get("runtime.shuffle_partitions"))
    if mode == "local":
        _java_check()
        os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
        if cfg.get("runtime.connect"):
            url = cfg.get("runtime.connect_url") or f"local[{cores}]"   # local[n] starts a server on loopback
            builder = SparkSession.builder.remote(url)
        else:
            builder = SparkSession.builder.master(f"local[{cores}]").config("spark.ui.enabled", "false")
            for k, v in _LOOPBACK.items():
                builder = builder.config(k, v)
        # Startup options: the classic builder and a local Connect server (remote("local[n]")) both apply them
        # when they launch the JVM.
        builder = builder.config("spark.driver.memory", cfg.get("runtime.driver_memory"))
        spark = builder.appName("lakematch").config("spark.sql.shuffle.partitions", parts).getOrCreate()
        if not is_remote(spark):
            spark.sparkContext.setLogLevel("ERROR")
        return spark
    # serverless / classic: Databricks Connect, imported lazily — never a dependency of the laptop engine.
    raise MethodNotReady(f"runtime.mode: '{mode}' is reached through Databricks Connect, wired in "
                         f"{'ZR-6' if mode == 'serverless' else 'ZR-9'}")


@dataclass
class Capabilities:
    remote: bool
    can_cache: bool
    can_checkpoint: bool            # localCheckpoint(): pins the data AND cuts the lineage
    local_filesystem: bool          # scratch data can live under storage.root on this machine
    spark_version: str
    notes: list[str] = field(default_factory=list)


def probe(spark: SparkSession) -> Capabilities:
    """Measure, once, what this session allows — instead of trusting the mode name."""
    remote = is_remote(spark)
    notes = []
    try:
        df = spark.range(1).cache()
        df.count()
        df.unpersist()
        can_cache = True
    except Exception as e:   # serverless: "PERSIST TABLE is not supported"
        can_cache = False
        notes.append(f"cache() refused: {type(e).__name__}")
    try:
        spark.range(1).localCheckpoint(eager=True).count()
        can_checkpoint = True
    except Exception as e:   # serverless: checkpoint() and localCheckpoint() raise
        can_checkpoint = False
        notes.append(f"localCheckpoint() refused: {type(e).__name__}")
    # A local Connect server shares this machine's filesystem; a Databricks session does not.
    local_fs = not type(spark).__module__.startswith("databricks.connect")
    return Capabilities(remote, can_cache, can_checkpoint, local_fs, spark.version, notes)


class Runtime:
    """A session plus what it may do. `materialize()` is the one escape hatch for iterative or reused plans."""

    def __init__(self, cfg: Config, spark: SparkSession | None = None):
        self.cfg = cfg
        self.spark = spark or session(cfg)
        self.caps = probe(self.spark)
        self.run_id = uuid.uuid4().hex[:12]
        self._scratch: list[tuple[str, str]] = []      # (kind, location) to delete at close()
        self._cached: list[DataFrame] = []

    @property
    def remote(self) -> bool:
        return self.caps.remote

    def strategy(self) -> str:
        want = self.cfg.get("runtime.materialize")
        if want == "auto":
            return "checkpoint" if self.caps.can_checkpoint else "cache" if self.caps.can_cache else "table"
        if want == "checkpoint" and not self.caps.can_checkpoint:
            raise RuntimeError("runtime.materialize: checkpoint, but this session refuses localCheckpoint()")
        if want == "cache" and not self.caps.can_cache:
            raise RuntimeError("runtime.materialize: cache, but this session refuses cache()")
        return want

    def scratch_path(self, name: str) -> Path:
        root = self.cfg.path(self.cfg.get("storage.root"))
        return root / "_scratch" / self.run_id / name

    def materialize(self, df: DataFrame, name: str) -> DataFrame:
        """Pin `df` so later actions do not recompute it, and cut its lineage where possible: localCheckpoint() where
        allowed (a long plan reused many times otherwise exhausts the analyser), else cache(), else write a scratch
        table and read it back. The caller cannot tell which happened; scratch data is deleted by close()."""
        how = self.strategy()
        if how == "checkpoint":
            return df.localCheckpoint(eager=True)
        if how == "cache":
            df = df.cache()
            df.count()                                 # compute now, so the pin is real
            self._cached.append(df)
            return df
        catalog = self.cfg.get("storage.catalog")
        if catalog:
            table = f"{catalog}.lm_scratch_{self.run_id}_{name}"
            df.write.mode("overwrite").saveAsTable(table)
            self._scratch.append(("table", table))
            return self.spark.table(table)
        if not self.caps.local_filesystem:
            raise RuntimeError("materialize: no storage.catalog and no local filesystem to write scratch data to")
        path = self.scratch_path(name)
        df.write.mode("overwrite").parquet(str(path))
        self._scratch.append(("path", str(path)))
        return self.spark.read.parquet(str(path))

    def temp_view(self, df: DataFrame, prefix: str) -> str:
        """Register a session temp view under a unique name (Connect resolves views by name at execution)."""
        name = f"{prefix}_{self.run_id}_{uuid.uuid4().hex[:6]}"
        df.createOrReplaceTempView(name)
        return name

    def save_ml(self, model, path: Path) -> None:
        """Save a fitted Spark ML model where this process can read it back (the MLflow artifact upload). A local
        session or a local Connect server writes the local filesystem; serverless needs a UC volume (ZR-6)."""
        if not self.caps.local_filesystem:
            raise RuntimeError("save_ml: the session cannot write the local filesystem — a UC volume path lands in ZR-6")
        model.write().overwrite().save(str(path))

    def close(self, stop: bool = False) -> None:
        for df in self._cached:
            try:
                df.unpersist()
            except Exception:
                pass
        for kind, where in self._scratch:
            if kind == "table":
                self.spark.sql(f"DROP TABLE IF EXISTS {where}")
            else:
                shutil.rmtree(where, ignore_errors=True)
        run_dir = self.scratch_path("x").parent
        if run_dir.exists():
            shutil.rmtree(run_dir, ignore_errors=True)
        self._scratch.clear()
        self._cached.clear()
        if stop:
            self.spark.stop()
