"""Pairwise metrics against a truth set. Bootstrap intervals and the benchmark table are the harness's job (ZR-3)."""
from __future__ import annotations

from pyspark.sql import DataFrame, functions as F


def prf(tp: int, n_pred: int, n_true: int) -> dict:
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_true if n_true else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"links": n_pred, "tp": tp, "fp": n_pred - tp, "fn": n_true - tp,
            "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}


def pairwise(links: DataFrame, truth: DataFrame, candidates: DataFrame, train_anchors: DataFrame | None = None) -> dict:
    """Precision / recall / F1 of `links`, candidate recall of `candidates`, and the same on held-out left records
    (those that contributed no training label) when `train_anchors` is given."""
    links, truth = links.select("l_id", "r_id").distinct(), truth.select("l_id", "r_id")
    n_true = truth.count()
    tp = links.join(truth, ["l_id", "r_id"]).count()
    out = {"all": prf(tp, links.count(), n_true)}
    out["candidate_recall"] = round(candidates.select("l_id", "r_id").join(truth, ["l_id", "r_id"]).count()
                                    / n_true, 4) if n_true else 0.0
    if train_anchors is not None:
        held_links = links.join(train_anchors, "l_id", "left_anti")
        held_truth = truth.join(train_anchors, "l_id", "left_anti")
        out["held_out"] = prf(held_links.join(held_truth, ["l_id", "r_id"]).count(), held_links.count(),
                              held_truth.count())
    return out


def trivial_baseline(candidates: DataFrame, truth: DataFrame) -> dict:
    """Always link the nearest neighbour: the baseline every benchmark prints first."""
    nn = candidates.filter(F.col("cand_rank") == 1)
    return prf(nn.join(truth.select("l_id", "r_id"), ["l_id", "r_id"]).count(), nn.count(), truth.count())
