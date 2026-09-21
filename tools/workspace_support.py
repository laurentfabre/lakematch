"""Shared, bounded helpers for this campaign's deployment scripts."""
import time

HOST = "https://fevm-gdpr2.cloud.databricks.com"
CATALOG = "gdpr2_catalog"
SCHEMA = "lakematch_20260919"
NAMESPACE = CATALOG + "." + SCHEMA
VOLUME = NAMESPACE + ".artifacts"
INPUT_ROOT = f"/Volumes/{CATALOG}/{SCHEMA}/artifacts/serverless_frozen"
APP = "lakematch-review-20260919"
WAREHOUSE_NAME = "lakematch-20260919-evidence-20260920T041603Z-35e82ec0"


def client(profile):
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.core import Config
    if profile != "fevm-gdpr2":
        raise ValueError("This campaign is authorized only for explicitly selected fevm-gdpr2")
    w = WorkspaceClient(config=Config(profile=profile, http_timeout_seconds=55, retry_timeout_seconds=60))
    if w.config.host.rstrip("/") != HOST:
        raise ValueError("Selected profile points to a different workspace")
    return w


def sql(w, warehouse, statement):
    """At most 120 seconds per statement; cancel pending work on all exits."""
    response = w.statement_execution.execute_statement(
        warehouse_id=warehouse, statement=statement, wait_timeout="50s")
    deadline = time.monotonic() + 70
    try:
        while response.status.state.value in {"PENDING", "RUNNING"}:
            if time.monotonic() >= deadline:
                raise TimeoutError("Deployment SQL exceeded 120 seconds")
            time.sleep(2)
            response = w.statement_execution.get_statement(response.statement_id)
        if response.status.state.value != "SUCCEEDED":
            raise RuntimeError(f"Deployment SQL failed: {response.status.error}")
        return response.result.data_array if response.result else []
    finally:
        if response.status.state.value in {"PENDING", "RUNNING"}:
            w.statement_execution.cancel_execution(response.statement_id)
