"""All session differences and materialization side effects live here."""
from dataclasses import asdict, dataclass
from pathlib import Path
import re
from uuid import uuid4

from pyspark.sql import SparkSession

# Match the local IPv4 bind address and macOS offline sandbox's loopback rule.
# Java's dual-stack IPv4-mapped sockets are not recognized as localhost there.
LOCAL_JAVA_OPTIONS = "-Djava.net.preferIPv4Stack=true"


def is_remote(spark):
    return type(spark).__module__.startswith("pyspark.sql.connect")


def create_session(config):
    runtime = config["runtime"]
    if runtime["mode"] == "local":
        builder = SparkSession.builder.appName("lakematch")
        settings = {"spark.sql.shuffle.partitions": "4", "spark.sql.ansi.enabled": "true",
                    "spark.sql.session.timeZone": "UTC"}
        if runtime["connect"]:
            builder = builder.remote(runtime["remote"])
        else:
            builder = (builder.master(runtime["master"]).config("spark.ui.enabled", "false")
                       .config("spark.driver.extraJavaOptions", LOCAL_JAVA_OPTIONS)
                       .config("spark.driver.bindAddress", "127.0.0.1"))
        for key, value in settings.items():
            builder = builder.config(key, value)
        return builder.getOrCreate()
    profile = runtime["cli_profile"] if runtime["mode"] == "serverless" else config["classic"]["profile"]
    if not profile:
        raise ValueError("An explicitly selected Databricks CLI profile is required")
    try:
        from databricks.connect import DatabricksSession
    except ImportError as exc:
        raise RuntimeError("Use a separate Databricks Connect environment; never install it over OSS PySpark") from exc
    builder = DatabricksSession.builder.profile(profile)
    if runtime["mode"] == "serverless":
        builder = builder.serverless(True)
    return builder.getOrCreate()


@dataclass(frozen=True)
class Capabilities:
    spark_version: str
    connect: bool
    cache: bool
    cache_observation: str
    photon: str = "untested: requires query-profile evidence"

    def to_dict(self):
        return asdict(self)


def probe(spark):
    """Job-time capability test; never called from a declarative flow."""
    frame = spark.range(1)
    cached = None
    try:
        cached = frame.cache()
        cached.count()
        allowed, observation = True, "cache and count succeeded"
    except Exception as exc:
        # Only an explicit unsupported capability may trigger the table path.
        error = getattr(exc, "getCondition", lambda: None)() or ""
        message = str(exc)
        unsupported = ("NOT_SUPPORTED" in error or "UNSUPPORTED" in error or
                       "not supported" in message.lower())
        if not unsupported:
            raise
        allowed, observation = False, f"{type(exc).__name__}: {error or message[:200]}"
    finally:
        if cached is not None:
            cached.unpersist()
    return Capabilities(spark.version, is_remote(spark), allowed, observation)


class Materializer:
    """Job-scoped materialization, with owned-resource cleanup on all exit paths.

    Local tables use Parquet so Delta is not a mandatory package. Databricks table
    materialization requires an explicitly owned scratch schema and uses Delta.
    """

    def __init__(self, spark, config, capabilities):
        self.spark, self.config, self.capabilities = spark, config, capabilities
        self.prefix = f"lm_{uuid4().hex}"
        self.cached, self.tables, self.events = [], [], []

    def __enter__(self):
        return self

    def materialize(self, frame, name):
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_]*", name):
            raise ValueError("Materialization name must be a simple identifier")
        mode = self.config["runtime"]["materialize"]
        if mode == "cache" and not self.capabilities.cache:
            raise RuntimeError("Caching was explicitly requested but the capability probe rejected it")
        if mode != "table" and self.capabilities.cache:
            result = frame.cache()
            self.cached.append(result)
            result.count()
            self.events.append({"name": name, "strategy": "cache"})
            return result
        schema = self.config["storage"]["scratch_schema"]
        local = self.config["runtime"]["mode"] == "local"
        if not local and not schema:
            raise ValueError("Table materialization requires an owned storage.scratch_schema")
        parts = ([*schema.split(".")] if schema else []) + [f"{self.prefix}_{name}_{len(self.tables)}"]
        if any(not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", p) for p in parts):
            raise ValueError("Scratch schema must contain simple dot-separated identifiers")
        table = ".".join(f"`{p}`" for p in parts)
        self.tables.append(table)  # Include partially-created writes in cleanup.
        frame.write.format("parquet" if local else "delta").mode("error").saveAsTable(table)
        self.events.append({"name": name, "strategy": "table", "table": table})
        return self.spark.table(table)

    def close(self):
        errors = []
        for frame in reversed(self.cached):
            try:
                frame.unpersist(blocking=True)
            except Exception as exc:
                errors.append(str(exc))
        for table in reversed(self.tables):
            try:
                self.spark.sql(f"DROP TABLE IF EXISTS {table}").collect()
            except Exception as exc:
                errors.append(str(exc))
        self.cached.clear()
        self.tables.clear()
        if errors:
            raise RuntimeError(f"Materialization cleanup failed: {errors}")

    def __exit__(self, exc_type, exc, traceback):
        self.close()
