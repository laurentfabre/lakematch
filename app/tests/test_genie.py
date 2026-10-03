"""The Genie panel (ZR-8): gated by paid_features.genie, and asked as the signed-in user, never as the app.

Run: cd app && uv run pytest tests/test_genie.py
"""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


def _client(monkeypatch, tmp_path, genie_on: bool):
    monkeypatch.setenv("LAKEMATCH_APP_SOURCE", "local")
    monkeypatch.setenv("LAKEMATCH_APP_REVIEW_DIR", str(tmp_path))
    monkeypatch.setenv("LAKEMATCH_APP_GENIE", "true" if genie_on else "false")
    monkeypatch.setenv("LAKEMATCH_APP_GENIE_SPACE_ID", "space123")
    from lakematch_app.backend import settings
    settings.settings.cache_clear()
    from lakematch_app.backend import app as app_module
    return TestClient(importlib.reload(app_module).app)


def test_panel_hidden_when_off(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path, False) as c:
        assert c.get("/api/genie/config").json()["enabled"] is False
        assert c.post("/api/genie/ask", json={"question": "how many links?"}).status_code == 404


def test_panel_shown_when_on_and_asks_with_the_user_token(monkeypatch, tmp_path):
    from lakematch_app.backend import genie
    seen = {}

    def fake_ask(space_id, question, token, conversation_id=None):
        seen.update(space_id=space_id, question=question, token=token)
        return {"asked_as": "someone@example.com", "auth": "on_behalf_of_user", "conversation_id": "c1",
                "status": "COMPLETED", "sql": "SELECT 1", "text": None, "columns": ["n"], "rows": [["1"]], "error": None}
    monkeypatch.setattr(genie, "ask", fake_ask)
    with _client(monkeypatch, tmp_path, True) as c:
        cfg = c.get("/api/genie/config").json()
        assert cfg["enabled"] is True and cfg["space_id"] == "space123"
        r = c.post("/api/genie/ask", json={"question": "how many links?"},
                   headers={"X-Forwarded-Access-Token": "user-token-abc"})
        assert r.status_code == 200 and r.json()["asked_as"] == "someone@example.com"
    assert seen == {"space_id": "space123", "question": "how many links?", "token": "user-token-abc"}


def test_user_client_uses_the_forwarded_token(monkeypatch):
    """The client is built from the forwarded user token (the SDK resolves the host over the network when a client
    is built, so the class is replaced by a recorder here)."""
    from lakematch_app.backend import genie
    built = {}
    monkeypatch.setattr(genie, "WorkspaceClient", lambda **kw: built.update(kw) or "client")
    monkeypatch.setenv("DATABRICKS_HOST", "example.cloud.databricks.com")
    w, auth = genie.user_client("user-token-abc")
    assert auth == "on_behalf_of_user" and w == "client"
    assert built == {"host": "https://example.cloud.databricks.com", "token": "user-token-abc", "auth_type": "pat"}


def test_never_falls_back_to_the_app_identity_on_databricks(monkeypatch):
    from lakematch_app.backend import genie
    monkeypatch.setenv("DATABRICKS_APP_NAME", "lakematch")
    with pytest.raises(genie.NoUserToken):
        genie.user_client(None)
