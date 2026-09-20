"""Validation retrieval universes; confirmation labels never enter evaluation."""
from .corpora import canonical


def training_ids(corpus):
    if corpus.retrieval:
        return [{r["rec_id"] for r in records if r["split"] == "train"}
                for records in (corpus.left, corpus.right)]
    return [{p[key] for p in corpus.pairs if p["split"] == "train"} for key in ("a_id", "b_id")]


def validation_scope(corpus, scope):
    if scope not in {"transductive", "disjoint"}:
        raise ValueError("Unknown retrieval scope")
    records = (corpus.left, corpus.right)
    valid = [p for p in corpus.pairs if p["split"] == "valid"]
    ids = [{r["rec_id"] for r in rows} for rows in records]
    removed = [0, 0]
    if scope == "disjoint":
        trained = training_ids(corpus)
        def identity(row):
            return canonical({name: row.get(name) for name in corpus.fields})
        seen = {identity(row) for rows, keys in zip(records, trained) for row in rows if row["rec_id"] in keys}
        if corpus.retrieval:
            ids = [{r["rec_id"] for r in rows if r["split"] == "valid"} for rows in records]
        else:
            ids = [{p[key] for p in valid} for key in ("a_id", "b_id")]
        for side, rows in enumerate(records):
            excluded = {r["rec_id"] for r in rows if r["rec_id"] in ids[side] and identity(r) in seen}
            ids[side] -= excluded
            removed[side] = len(excluded)
        assert not any(identity(r) in seen for rows, keys in zip(records, ids) for r in rows if r["rec_id"] in keys)
    positives = {(p["a_id"], p["b_id"]): p["group"] for p in valid if p["label"] == 1.
                 and p["a_id"] in ids[0] and p["b_id"] in ids[1]}
    return ids, positives, {"scope": scope, "left_records": len(ids[0]), "right_records": len(ids[1]),
        "validation_positives": len(positives), "original_validation_positives": sum(p["label"] == 1. for p in valid),
        "training_overlapping_records_removed": removed,
        "definition": "full unlabelled universe" if scope == "transductive" else
            "validation records only, excluding canonical records seen on either training side"}
