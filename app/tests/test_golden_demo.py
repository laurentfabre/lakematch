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


def test_comparisons_follow_each_publications_actual_source_versions(client):
    catalog = client.get("/api/demo/golden-records").json()
    observed = 0
    for company in catalog["companies"]:
        for publication in catalog["publications"]:
            entity = client.get(f"/api/demo/golden-records/{company['master_id']}?publication={publication}").json()["entity"]
            comparison = entity["comparison"]
            assert comparison["pair_origin"] == "explicit_comparison"
            assert comparison["probability"] is None
            assert comparison["decision"]["auto_merge_eligible"] is False
            assert len(comparison["fields"]) == 7
            for index, record in enumerate(comparison["records"]):
                source = next(s for s in entity["sources"] if s["source_id"] == record["source_id"] and s["source_key"] == record["source_key"])
                assert record["version"] == source["version"]
                side = "left" if index == 0 else "right"
                assert all(f[side]["value"] == source["values"].get(f["name"]) for f in comparison["fields"])
            observed += 1
    assert observed == 12
    assert client.get("/api/queue").json() == []
    assert client.get("/api/reviews").json() == []


def test_comparison_explains_identifier_conflict_normalization_and_deletion(client):
    companies = client.get("/api/demo/golden-records").json()["companies"]
    def comparison(name, publication="second"):
        company = next(c for c in companies if c["legal_name"] == name)
        return client.get(f"/api/demo/golden-records/{company['master_id']}?publication={publication}").json()["entity"]["comparison"]
    harbor = comparison("Harbor Industrial Ltd")
    assert harbor["decision"]["rule_id"] == "identifier_conflict"
    identifier = next(f for f in harbor["fields"] if f["name"] == "registration_id")
    assert {identifier[s]["value"] for s in ("left", "right")} == {"TEST-GB-004", "TEST-GB-005"}
    assert identifier["comparison"] == "differ"
    name = next(f for f in comparison("Cedar Logistics SAS")["fields"] if f["name"] == "legal_name")
    assert name["comparison"] == "agree" and name["raw_equal"] is False
    assert name["left"]["normalized"] == name["right"]["normalized"] == "cedar logistics"
    old, current = comparison("Atlas Supplies SAS", "first"), comparison("Atlas Supplies SAS")
    assert old["decision"]["route"] == "review"
    assert current["decision"]["route"] == "exclude"
    assert current["decision"]["rule_id"] == "deleted_source"
    assert all(f["comparison"] == "unavailable" for f in current["fields"])
    assert old["evidence_sha256"] != current["evidence_sha256"]


@pytest.mark.parametrize("mutation", ["source_version", "raw_value", "fields", "merge_authority"])
def test_inconsistent_comparison_projection_is_rejected_even_with_new_bundle_checksum(tmp_path, monkeypatch, mutation):
    from hashlib import sha256
    payload = golden_demo.read_demo().model_dump()
    comparison = payload["publications"][0]["entities"][0]["comparison"]
    if mutation == "source_version":
        comparison["records"][0]["version"] += 1
    elif mutation == "raw_value":
        comparison["fields"][0]["left"]["value"] = "Unrelated value"
    elif mutation == "fields":
        comparison["fields"][0] = comparison["fields"][1]
    else:
        comparison["decision"]["auto_merge_eligible"] = True
    payload.pop("bundle_sha256")
    payload["bundle_sha256"] = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    asset = tmp_path / "demo/company_lineage.json"
    asset.parent.mkdir()
    asset.write_text(json.dumps(payload))
    monkeypatch.setattr(golden_demo, "files", lambda _: tmp_path)
    with pytest.raises(ValueError):
        golden_demo.read_demo()
