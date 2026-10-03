"""The label rows the app writes are the rows the engine reads: lakematch/labels/store.py STORE_COLUMNS.

The app never imports the engine at run time; this test reads the engine's source (the repository's src/) only to
compare the two declarations, so it runs without pyspark installed.
"""
from __future__ import annotations

import ast
from pathlib import Path

from lakematch_app.backend.stores import LABEL_COLUMNS

ENGINE_STORE = Path(__file__).resolve().parents[2] / "src" / "lakematch" / "labels" / "store.py"


def test_label_columns_match_the_engine():
    tree = ast.parse(ENGINE_STORE.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.AnnAssign) and getattr(n.target, "id", "") == "STORE_COLUMNS")
    engine = [tuple(e.value for e in t.elts) for t in node.value.elts]
    assert engine == LABEL_COLUMNS


def test_app_does_not_import_the_engine():
    src = Path(__file__).resolve().parents[1] / "src"
    for f in src.rglob("*.py"):
        text = f.read_text()
        assert "import lakematch\n" not in text and "from lakematch." not in text and "from lakematch " not in text, f
