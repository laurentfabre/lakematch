from copy import deepcopy
import json

from fastapi.testclient import TestClient
import pytest

from lakematch_review.backend.app import app
from lakematch_review.backend import golden_demo
from lakematch_review.backend.router import get_actor


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABRICKS_APP_NAME", raising=False)
    monkeypatch.setenv("LAKEMATCH_REVIEW_STORE", "sqlite")
    monkeypatch.setenv("LAKEMATCH_REVIEW_DATABASE", str(tmp_path / "unused.sqlite"))
    with TestClient(app) as client:
        yield client


def test_synthetic_detail_explains_override_and_historical_values(client):
    catalog = client.get("/api/demo/golden-records").json()
    assert catalog["kind"] == "synthetic_company_demo"
    assert len(catalog["companies"]) == 6
    master_id = catalog["default_master_id"]
    first = client.get(f"/api/demo/golden-records/{master_id}?publication=first").json()
    second = client.get(f"/api/demo/golden-records/{master_id}?publication=second").json()
    assert first["membership_basis"] == "synthetic_fixture_truth"
    assert first["entity"]["values"]["legal_name"] == "Cedar Components SA"
    assert second["entity"]["values"]["legal_name"] == "Cedar Components — reviewed name"
    assert first["entity"]["revision"] == 1 and second["entity"]["revision"] == 2
    assert first["entity"]["identity_revision"] == second["entity"]["identity_revision"] == 1
    assert len(second["entity"]["fields"]) == 8
    field = next(f for f in second["entity"]["fields"] if f["name"] == "legal_name")
    assert field["reason"] == "approved_override" and field["decision_id"]
    assert field["approved_by"] == "synthetic_approver"
    assert {a["source_id"] for a in field["alternatives"]} == {"erp_vendor", "crm_account"}
    assert first["snapshot_sha256"] != second["snapshot_sha256"]
    # Loading a demo never populates or labels the real review queue.
    assert client.get("/api/queue").json() == []
    assert client.get("/api/reviews").json() == []


def test_deleted_source_remains_explainable_in_older_publication(client):
    catalog = client.get("/api/demo/golden-records").json()
    atlas = next(c for c in catalog["companies"] if c["legal_name"] == "Atlas Supplies SAS")
    url = f"/api/demo/golden-records/{atlas['master_id']}"
    old = client.get(url + "?publication=first").json()["entity"]
    new = client.get(url + "?publication=second").json()["entity"]
    assert not any(s["deleted"] for s in old["sources"])
    assert sum(s["deleted"] for s in new["sources"]) == 1
    assert any(a["excluded"] == "deleted" for f in new["fields"] for a in f["alternatives"])


def test_demo_has_no_write_or_arbitrary_publication_route(client):
    base = "/api/demo/golden-records"
    master_id = client.get(base).json()["default_master_id"]
    assert client.get(base + "/not-a-uuid").status_code == 422
    assert client.get(base + "/ffffffff-ffff-ffff-ffff-ffffffffffff").status_code == 404
    assert client.get(base + f"/{master_id}?publication=live").status_code == 422
    assert client.post(base + f"/{master_id}", json={"legal_name": "Overwrite"}).status_code == 405


def test_failed_asset_load_is_visible_without_partial_demo(client, monkeypatch):
    def unavailable():
        raise ValueError("corrupted artifact")
    monkeypatch.setattr(golden_demo, "read_demo", unavailable)
    response = client.get("/api/demo/golden-records")
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]


def test_demo_routes_keep_the_existing_session_dependency(client):
    from fastapi import HTTPException
    def denied():
        raise HTTPException(401, "Session required")
    app.dependency_overrides[get_actor] = denied
    try:
        assert client.get("/api/demo/golden-records").status_code == 401
        assert client.get("/api/demo/golden-records/00000000-0000-0000-0000-000000000001").status_code == 401
    finally:
        app.dependency_overrides.pop(get_actor)


def test_packaged_data_is_detached_and_detects_corruption(tmp_path, monkeypatch):
    original = golden_demo.read_demo()
    changed = deepcopy(original)
    changed.publications[0].entities[0].values["legal_name"] = "Mutation"
    assert golden_demo.read_demo() == original
    asset = tmp_path / "demo/company_lineage.json"
    asset.parent.mkdir()
    asset.write_text(json.dumps(changed.model_dump()))
    monkeypatch.setattr(golden_demo, "files", lambda _: tmp_path)
    with pytest.raises(ValueError, match="checksum differs"):
        golden_demo.read_demo()
    asset.write_bytes(b"x" * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match="exceeds"):
        golden_demo.read_demo()
