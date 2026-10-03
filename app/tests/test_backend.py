"""The app's API over the laptop backend (local queue + Delta label store), through HTTP (FastAPI's TestClient).

Run: cd app && uv run pytest
"""
from __future__ import annotations

import json
import importlib
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

FIELDS = ["given_name", "surname", "date_of_birth"]


def _queue(dir_: Path, n: int = 6) -> None:
    rows = []
    for i in range(n):
        rec = lambda side: json.dumps({"given_name": f"ann{i}", "surname": "lee" if side == "l" else "leee",
                                       "date_of_birth": "19800101"})
        rows.append({"rank": i + 1, "l_id": f"l{i}", "r_id": f"r{i}", "p": 0.4 + i / 100, "threshold": 0.5,
                     "distance": 0.1 - i / 100, "queue_reason": "near_threshold" if i < 3 else "other",
                     "llm_label": ["same", "different", "unsure", None, None, None][i % 6],
                     "llm_p_same": 0.9, "linked": i % 2 == 0, "impact": 2, "cand_score": 0.8, "cand_rank": 1,
                     "l_record": rec("l"), "r_record": rec("r"), "model_version": "run abc", "run_id": "R1",
                     "created_at": None})
    (dir_ / "queue").mkdir(parents=True)
    table = pa.Table.from_pylist(rows).set_column(
        len(rows[0]) - 1, "created_at", pa.array([None] * n, pa.timestamp("us", tz="UTC")))
    pq.write_table(table, dir_ / "queue" / "part-0.parquet")
    (dir_ / "runs.jsonl").write_text(json.dumps({
        "run_id": "R1", "model_version": "run abc", "created_at": "2026-10-03T10:00:00Z", "threshold": 0.5,
        "evaluation": "truth", "precision": 0.99, "recall": 0.95, "f1": 0.97, "label_source": "truth_sample",
        "app_labels_used": 0, "labels_train": 300, "quarantined_left": 2, "quarantined_right": 1}) + "\n")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    _queue(tmp_path)
    monkeypatch.setenv("LAKEMATCH_APP_SOURCE", "local")
    monkeypatch.setenv("LAKEMATCH_APP_LABEL_STORE", "delta")
    monkeypatch.setenv("LAKEMATCH_APP_REVIEW_DIR", str(tmp_path))
    monkeypatch.setenv("LAKEMATCH_APP_LOCAL_USER", "tester@laptop")
    from lakematch_app.backend import settings
    settings.settings.cache_clear()
    from lakematch_app.backend import app as app_module
    with TestClient(importlib.reload(app_module).app) as c:
        yield c
    settings.settings.cache_clear()


def test_queue_order_and_fields(client):
    items = client.get("/api/queue/next", params={"n": 3}).json()["items"]
    assert [i["rank"] for i in items] == [1, 2, 3]
    f = {x["name"]: x for x in items[0]["fields"]}
    assert f["given_name"]["same"] and not f["surname"]["same"]


def test_label_records_provenance_and_leaves_queue(client):
    r = client.post("/api/labels", json={"l_id": "l0", "r_id": "r0", "decision": "match", "reason": "typo"})
    assert r.status_code == 200, r.text
    row = r.json()
    assert row["reviewer"] == "tester@laptop" and row["model_version"] == "run abc" and row["reason"] == "typo"
    assert row["p"] == pytest.approx(0.4) and row["queue_reason"] == "near_threshold" and row["is_match"] == 1.0
    assert row["labelled_at"].endswith("+00:00")
    assert client.get("/api/queue/next", params={"n": 1}).json()["items"][0]["rank"] == 2


def test_databricks_identity_header_wins(client):
    r = client.post("/api/labels", json={"l_id": "l1", "r_id": "r1", "decision": "no_match", "reason": "dob"},
                    headers={"X-Forwarded-Email": "someone@example.com"})
    assert r.json()["reviewer"] == "someone@example.com"


def test_rejects_unqueued_pair_and_empty_reason(client):
    assert client.post("/api/labels", json={"l_id": "x", "r_id": "y", "decision": "match", "reason": "r"}).status_code == 404
    assert client.post("/api/labels", json={"l_id": "l0", "r_id": "r0", "decision": "match", "reason": ""}).status_code == 422
    assert client.post("/api/labels", json={"l_id": "l0", "r_id": "r0", "decision": "maybe", "reason": "r"}).status_code == 422


def test_retract_puts_pair_back(client):
    client.post("/api/labels", json={"l_id": "l0", "r_id": "r0", "decision": "match", "reason": "typo"})
    r = client.post("/api/labels/retract", json={"l_id": "l0", "r_id": "r0"})
    assert r.status_code == 200 and r.json()["decision"] == "retract"
    assert client.get("/api/queue/next", params={"n": 1}).json()["items"][0]["rank"] == 1
    assert client.post("/api/labels/retract", json={"l_id": "l0", "r_id": "r0"}).status_code == 404


def test_skip_is_client_side(client):
    items = client.get("/api/queue/next", params={"n": 1, "skip": ["l0|r0", "l1|r1"]}).json()["items"]
    assert items[0]["rank"] == 3


def test_stats(client):
    client.post("/api/labels", json={"l_id": "l0", "r_id": "r0", "decision": "match", "reason": "a"})      # llm same
    client.post("/api/labels", json={"l_id": "l1", "r_id": "r1", "decision": "match", "reason": "b"})      # llm different
    client.post("/api/labels", json={"l_id": "l2", "r_id": "r2", "decision": "unsure", "reason": "c"})     # llm unsure
    s = client.get("/api/stats").json()
    assert s["labels"]["current"] == {"match": 2, "unsure": 1}
    assert s["labels"]["complete_provenance"] == 3
    assert s["agreement"]["pairs"] == 2 and s["agreement"]["agree"] == 1 and s["agreement"]["rate"] == 0.5
    assert s["queue"] == {"total": 6, "pending": 3, "labelled": 3, "pending_by_reason": {"other": 3},
                          "total_by_reason": {"near_threshold": 3, "other": 3}, "model_version": "run abc"}
    v = s["model_versions"][0]
    assert v["model_version"] == "run abc" and v["precision"] == 0.99 and v["human_labelled"] == 2
    assert v["human_precision"] is None or 0 <= v["human_precision"] <= 1     # p < threshold on both: model said no
    assert v["human_recall"] == 0.0
    assert s["quarantine"]["latest"]["left"] == 2


def test_restart_loses_nothing(client, tmp_path):
    """A new app process (Free Edition restarts apps every 24 h) sees every label: nothing lives in memory."""
    client.post("/api/labels", json={"l_id": "l0", "r_id": "r0", "decision": "match", "reason": "a"})
    from lakematch_app.backend import app as app_module
    with TestClient(importlib.reload(app_module).app) as fresh:
        assert fresh.get("/api/stats").json()["labels"]["events"] == 1
        assert fresh.get("/api/queue/next", params={"n": 1}).json()["items"][0]["rank"] == 2
