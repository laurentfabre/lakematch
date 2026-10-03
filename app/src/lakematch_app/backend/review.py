"""What the API does, over a source and a label store (stores.py). Stateless: every call reads the store.

A pair leaves the queue once its current label (latest row) is match, no_match or unsure; a `retract` row puts it
back. The provenance of a label — model version, p, threshold, why the pair was queued, the LLM's opinion — comes from
the queue row on the server, never from the browser; the reviewer comes from the Databricks Apps identity headers (or
the laptop user), and the time from the server's clock.
"""
from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone

DECISIONS = {"match": 1.0, "no_match": 0.0, "unsure": None}


class NotQueued(LookupError):
    """The pair is not in the current queue."""


class NothingToUndo(LookupError):
    """The pair carries no current label."""


def current(events: list[dict]) -> dict[tuple[str, str], dict]:
    """(l_id, r_id) -> the pair's latest row, retracted pairs dropped."""
    latest: dict[tuple[str, str], dict] = {}
    for e in sorted(events, key=lambda e: (e["labelled_at"], e["label_id"])):
        latest[(e["l_id"], e["r_id"])] = e
    return {k: e for k, e in latest.items() if e["decision"] != "retract"}


def fields(item: dict) -> list[dict]:
    left = json.loads(item.get("l_record") or "{}")
    right = json.loads(item.get("r_record") or "{}")
    names = list(left) + [n for n in right if n not in left]
    norm = lambda v: "".join(ch for ch in str(v or "").lower() if ch.isalnum())
    return [{"name": n, "left": left.get(n), "right": right.get(n),
             "same": norm(left.get(n)) == norm(right.get(n)) and bool(norm(left.get(n)))} for n in names]


def next_items(source, store, skip: set[tuple[str, str]], n: int = 1) -> list[dict]:
    done = set(current(store.events()))
    exclude = done | skip
    rows = source.queue(full=True, limit=n + len(exclude))
    out = [r for r in rows if (r["l_id"], r["r_id"]) not in exclude][:n]
    return [{**r, "fields": fields(r)} for r in out]


def label(source, store, *, l_id: str, r_id: str, decision: str, reason: str, reviewer: str) -> dict:
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {', '.join(DECISIONS)}")
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("a label needs a reason")
    item = source.pair(l_id, r_id)
    if item is None:
        raise NotQueued(f"{l_id} / {r_id} is not in the review queue")
    row = _row(item, decision=decision, is_match=DECISIONS[decision], reason=reason[:500], reviewer=reviewer)
    store.append(row)
    return row


def retract(source, store, *, l_id: str, r_id: str, reviewer: str, reason: str = "") -> dict:
    cur = current(store.events()).get((l_id, r_id))
    if cur is None:
        raise NothingToUndo(f"{l_id} / {r_id} carries no label")
    item = source.pair(l_id, r_id) or cur
    row = _row(item, decision="retract", is_match=None, reviewer=reviewer,
               reason=(reason or "").strip()[:500] or f"undo of '{cur['decision']}' ({cur['label_id']})")
    store.append(row)
    return row


def _row(item: dict, **kw) -> dict:
    return {"l_id": item["l_id"], "r_id": item["r_id"], "decision": kw["decision"], "is_match": kw["is_match"],
            "reviewer": kw["reviewer"], "labelled_at": datetime.now(timezone.utc).isoformat(),
            "model_version": item.get("model_version"), "p": item.get("p"), "threshold": item.get("threshold"),
            "reason": kw["reason"], "queue_reason": item.get("queue_reason"), "llm_label": item.get("llm_label"),
            "run_id": item.get("run_id"), "label_id": str(uuid.uuid4())}


def stats(source, store) -> dict:
    """Label counts, human-LLM agreement, precision / recall per model version, queue depth, quarantine counts."""
    events, queue, runs = store.events(), source.queue(full=False), source.runs()
    cur = current(events)
    decided = {k: e for k, e in cur.items() if e["decision"] in ("match", "no_match")}

    labels = {"events": len(events), "retracted": sum(e["decision"] == "retract" for e in events),
              "current": dict(Counter(e["decision"] for e in cur.values())),
              "by_reviewer": dict(Counter(e["reviewer"] for e in cur.values())),
              "complete_provenance": sum(all(e.get(k) not in (None, "") for k in
                                             ("reviewer", "labelled_at", "model_version", "reason")) for e in events)}

    both = [(e["decision"], e["llm_label"]) for e in decided.values() if e.get("llm_label") in ("same", "different")]
    agree = sum((h == "match") == (m == "same") for h, m in both)
    agreement = {"pairs": len(both), "agree": agree, "rate": round(agree / len(both), 4) if both else None,
                 "confusion": {f"{h}/{m}": n for (h, m), n in sorted(Counter(both).items())},
                 "llm_unsure_on_labelled": sum(e.get("llm_label") == "unsure" for e in decided.values()),
                 "llm_opinions_in_queue": sum(q.get("llm_label") is not None for q in queue)}

    per: dict[str, list[dict]] = defaultdict(list)
    for e in decided.values():
        per[e["model_version"]].append(e)
    versions = []
    seen = []
    for r in runs:                               # in run order; a version labelled but absent from history last
        if r["model_version"] not in seen:
            seen.append(r["model_version"])
    seen += sorted(v for v in per if v not in seen)
    for v in seen:
        run = next((r for r in reversed(runs) if r["model_version"] == v), {})
        hl = per.get(v, [])
        said = [e for e in hl if e["p"] is not None and e["threshold"] is not None and e["p"] >= e["threshold"]]
        human_match = [e for e in hl if e["decision"] == "match"]
        tp = sum(e["decision"] == "match" for e in said)
        versions.append({
            "model_version": v, "run_id": run.get("run_id"), "created_at": run.get("created_at"),
            "threshold": run.get("threshold"), "evaluation": run.get("evaluation"),
            "precision": run.get("precision"), "recall": run.get("recall"), "f1": run.get("f1"),
            "label_source": run.get("label_source"), "app_labels_used": run.get("app_labels_used"),
            "labels_train": run.get("labels_train"),
            "human_labelled": len(hl),
            "human_precision": round(tp / len(said), 4) if said else None,
            "human_recall": round(tp / len(human_match), 4) if human_match else None})

    pending = [q for q in queue if (q["l_id"], q["r_id"]) not in cur]
    depth = {"total": len(queue), "pending": len(pending), "labelled": len(queue) - len(pending),
             "pending_by_reason": dict(Counter(q["queue_reason"] for q in pending)),
             "total_by_reason": dict(Counter(q["queue_reason"] for q in queue)),
             "model_version": queue[0]["model_version"] if queue else None}

    quarantine = [{"run_id": r["run_id"], "model_version": r["model_version"], "created_at": r.get("created_at"),
                   "left": r.get("quarantined_left") or 0, "right": r.get("quarantined_right") or 0} for r in runs]
    return {"labels": labels, "agreement": agreement, "model_versions": versions, "queue": depth,
            "quarantine": {"latest": quarantine[-1] if quarantine else None, "history": quarantine}}
