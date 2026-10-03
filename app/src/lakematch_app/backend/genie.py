"""The Genie panel (ZR-8): questions to the lakematch Genie agent, asked *as the signed-in user*.

paid_features.genie_auth_mode is `user`: Genie bills since July 2026 and only users get the free allowance, so the
app never asks with its service principal. On Databricks the platform hands the app the user's token, downscoped to
the app's user_api_scopes (dashboards.genie, sql), in X-Forwarded-Access-Token; without it the call is refused. On a
laptop (no Databricks Apps proxy) the user is the one of the local profile (DATABRICKS_CONFIG_PROFILE in .env).
"""
from __future__ import annotations

import os
from datetime import timedelta

from databricks.sdk import WorkspaceClient

MAX_ROWS = 50


class NoUserToken(PermissionError):
    """Running as a Databricks App but the request carries no user token (user authorization not granted)."""


def on_databricks() -> bool:
    return bool(os.environ.get("DATABRICKS_APP_NAME"))


def user_client(token: str | None) -> tuple[WorkspaceClient, str]:
    if token:
        cfg_host = os.environ.get("DATABRICKS_HOST") or WorkspaceClient().config.host
        host = cfg_host if cfg_host.startswith("http") else f"https://{cfg_host}"
        return WorkspaceClient(host=host, token=token, auth_type="pat"), "on_behalf_of_user"
    if on_databricks():
        raise NoUserToken("no X-Forwarded-Access-Token: the app needs user authorization (scope dashboards.genie)")
    return WorkspaceClient(), "local_profile"


def ask(space_id: str, question: str, token: str | None, conversation_id: str | None = None) -> dict:
    w, auth = user_client(token)
    asked_as = w.current_user.me().user_name
    wait = timedelta(minutes=5)
    if conversation_id:
        msg = w.genie.create_message_and_wait(space_id, conversation_id, question, timeout=wait)
    else:
        msg = w.genie.start_conversation_and_wait(space_id, question, timeout=wait)
    out: dict = {"asked_as": asked_as, "auth": auth, "conversation_id": msg.conversation_id,
                 "status": msg.status.value if msg.status else None, "sql": None, "text": None, "columns": [],
                 "rows": [], "error": str(msg.error.error) if msg.error else None}
    for a in msg.attachments or []:
        if a.text and a.text.content:
            out["text"] = a.text.content
        if a.query:
            out["sql"] = a.query.query
            out["text"] = out["text"] or a.query.description
            res = w.genie.get_message_attachment_query_result(space_id, msg.conversation_id or "", msg.message_id or msg.id or "",
                                                              a.attachment_id or "")
            sr = res.statement_response
            if sr and sr.manifest and sr.manifest.schema:
                out["columns"] = [c.name for c in sr.manifest.schema.columns or []]
            if sr and sr.result:
                out["rows"] = [list(r) for r in (sr.result.data_array or [])[:MAX_ROWS]]
    return out
