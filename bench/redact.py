"""Identities never enter the public repository: committed evidence names roles, not people or workspaces.

`redact(text)` replaces e-mail addresses, Databricks workspace URLs and Databricks App URLs before a result file is
written. A Databricks user, service principal or app id stays (opaque, and needed to read the evidence).
"""
from __future__ import annotations

import re

RULES = [
    (re.compile(r"https://dbc-[0-9a-f]{8}-[0-9a-f]{4}\.cloud\.databricks\.com(/\?o=\d+)?"), "<workspace>"),
    (re.compile(r"https://[a-z0-9-]+-\d{10,}\.[a-z0-9.-]*databricksapps\.com"), "<app url>"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@(?!laptop\b)[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+\b"), "<user>"),
]


def redact(text: str) -> str:
    for pattern, repl in RULES:
        text = pattern.sub(repl, text)
    return text
