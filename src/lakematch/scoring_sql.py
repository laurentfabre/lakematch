"""The fitted classifier as one Spark SQL expression: scoring with built-ins only (ZR-6).

Why: a Databricks serverless pipeline fails when `pyspark.ml` (or MLflow) is imported in it — the runtime's notebook
"advice" hook crashes looking for a notebook socket (measured 2026-10-02, update 9bef97). Scoring inside the pipeline
therefore uses this expression; MLlib stays in the job tasks that train. A side effect: the scoring stage has no UDF
and no MLlib operator, so Photon can run all of it (bench/PHOTON.md measures it).

The expression is compiled from the SAVED pipeline (stages/1_*: Spark's own Parquet + JSON), read with pyarrow only,
so the semantics are Spark's, not a re-implementation of its training:

    tree node     CASE WHEN `feature` <= threshold THEN <left> ELSE <right> END    (ContinuousSplit.shouldGoLeft)
    gbt           p = 1 / (1 + exp(-2 · Σ_i w_i · tree_i))      w_i = treesMetadata weight, leaf = prediction
    random_forest p = Σ_i leaf_i / n_trees                        leaf = impurityStats[1] / Σ impurityStats
    logistic      p = 1 / (1 + exp(-(b + Σ_j c_j · x_j)))

tracking.log_run checks the expression against `model.transform` on the validation pairs before it accepts a run.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path


def _num(x: float) -> str:
    return f"({float(x)!r}D)"                    # repr round-trips; D = a DOUBLE literal, not a DECIMAL


def _col(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def _parquet_rows(directory: Path) -> list[dict]:
    import pyarrow.parquet as pq
    rows = []
    for f in sorted(glob.glob(str(directory / "*.parquet"))):
        rows += pq.read_table(f).to_pylist()
    return rows


def _tree(nodes: dict[int, dict], node_id: int, feature_cols: list[str], leaf) -> str:
    n = nodes[node_id]
    if n["leftChild"] < 0:
        return _num(leaf(n))
    split = n["split"]
    if split["numCategories"] != -1:
        raise ValueError("scoring_sql: categorical splits do not occur over a VectorAssembler of numeric features")
    test = f"{_col(feature_cols[split['featureIndex']])} <= {_num(split['leftCategoriesOrThreshold'][0])}"
    return (f"CASE WHEN {test} THEN {_tree(nodes, n['leftChild'], feature_cols, leaf)} "
            f"ELSE {_tree(nodes, n['rightChild'], feature_cols, leaf)} END")


def _trees(stage: Path, feature_cols: list[str], leaf) -> tuple[list[str], list[float]]:
    by_tree: dict[int, dict[int, dict]] = {}
    for r in _parquet_rows(stage / "data"):
        by_tree.setdefault(r["treeID"], {})[r["nodeData"]["id"]] = r["nodeData"]
    weights = {r["_1"]: r["_3"] for r in _parquet_rows(stage / "treesMetadata")}
    ids = sorted(by_tree)
    return [_tree(by_tree[t], 0, feature_cols, leaf) for t in ids], [weights[t] for t in ids]


def compile_saved(pipeline_dir: str | Path, feature_cols: list[str]) -> str:
    """The match probability `p` as a Spark SQL expression over the comparison-vector columns."""
    stages = sorted(Path(pipeline_dir, "stages").iterdir())
    stage = next(s for s in stages if not s.name.split("_", 1)[1].startswith("VectorAssembler"))
    meta = json.loads(Path(glob.glob(str(stage / "metadata" / "part-*"))[0]).read_text())
    kind = meta["class"].rsplit(".", 1)[1]
    if kind == "GBTClassificationModel":
        trees, weights = _trees(stage, feature_cols, lambda n: n["prediction"])
        margin = " + ".join(f"{_num(w)} * ({t})" for t, w in zip(trees, weights))
        return f"1.0D / (1.0D + exp(-2.0D * ({margin})))"
    if kind == "RandomForestClassificationModel":
        def leaf(n):
            stats = n["impurityStats"]
            return stats[1] / sum(stats) if sum(stats) else 0.0
        trees, _ = _trees(stage, feature_cols, leaf)
        return f"({' + '.join(f'({t})' for t in trees)}) / {_num(len(trees))}"
    if kind == "LogisticRegressionModel":
        row = _parquet_rows(stage / "data")[0]
        if row["isMultinomial"] or row["numClasses"] != 2:
            raise ValueError("scoring_sql: binary logistic regression only")
        coef, b = row["coefficientMatrix"]["values"], row["interceptVector"]["values"][0]
        margin = " + ".join([_num(b)] + [f"{_num(c)} * {_col(f)}" for c, f in zip(coef, feature_cols)])
        return f"1.0D / (1.0D + exp(-({margin})))"
    raise ValueError(f"scoring_sql: no compiler for {kind}")
