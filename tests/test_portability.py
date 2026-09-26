"""The portability lint (spec/BRIEF.md, *Portability rules*): constructs that break on Spark Connect / serverless
appear nowhere in the engine except runtime.py, the one module allowed to know about sessions."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "lakematch"
FORBIDDEN = {
    "sparkContext": r"\bsparkContext\b",
    "_jvm": r"\b_jvm\b",
    ".rdd": r"\.rdd\b",
    "udf.register": r"udf\.register",
    "createGlobalTempView": r"createGlobalTempView|createOrReplaceGlobalTempView",
    "cache/persist/checkpoint": r"\.(cache|persist|checkpoint|localCheckpoint)\(",
    "python udf on a default path": r"\b(F\.udf|pandas_udf|@udf)\b",
}


def test_no_forbidden_construct_outside_runtime():
    hits = []
    for path in SRC.rglob("*.py"):
        if path.name == "runtime.py":
            continue
        for n, line in enumerate(path.read_text().splitlines(), 1):
            code = line.split("#", 1)[0]
            for name, pattern in FORBIDDEN.items():
                if re.search(pattern, code):
                    hits.append(f"{path.relative_to(SRC)}:{n}: {name}")
    assert not hits, "\n".join(hits)
