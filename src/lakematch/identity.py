"""Stable identity over clusters: mdm_id, the crosswalk and the merge/split log.

    mdm_id      "m_" + the first 12 hex digits of sha1(canonical key), the canonical key being the cluster's smallest
                record key ("<side>:<id>"). A first run is a pure function of the clusters: the same input gives the
                same ids. When the hash is already held by another id of this run or the previous one, the key is
                suffixed "#1", "#2", ... until free (deterministic).
    crosswalk   one row per record: record key -> mdm_id.
    carry-over  with the previous crosswalk, ids survive: each previous id is OWNED by the new cluster holding most of
                its surviving records (tie: smallest canonical key); a new cluster keeps the owned id with most of its
                records (tie: smallest id), and the other ids it owns merge into it. A new cluster owning no previous
                id gets a fresh id. A previous id with no surviving record retires.
    log         one event per id change:
                  create   a fresh id for a cluster with no previous record
                  split    a fresh id for a cluster whose records held previous ids it does not own (`from`: those ids)
                  merge    a previous id folded into a kept one (`into`)
                  move     records of a previous id that lives on elsewhere joined a kept id (`into`)
                  retire   a previous id whose records were all deleted
    reconcile   the log must explain the new id set exactly: previous ids − merged − retired + created + split = new
                ids; every record whose id changed has a merge or move (old into new) or split (new from old) event; no
                retired or merged id is still in use; every created/split id is new.
"""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict


def mdm_id(canonical_key: str) -> str:
    return "m_" + hashlib.sha1(canonical_key.encode("utf-8")).hexdigest()[:12]


def _fresh(canonical_key: str, taken: set[str]) -> str:
    i, cand = 0, mdm_id(canonical_key)
    while cand in taken:
        i += 1
        cand = mdm_id(f"{canonical_key}#{i}")
    taken.add(cand)
    return cand


def assign(clusters: dict[str, str], previous: dict[str, str] | None = None, run: str = "") -> tuple[dict[str, str], list[dict]]:
    """clusters: record key -> cluster key (smallest member). previous: the last crosswalk (record key -> mdm_id).
    Returns (crosswalk, events)."""
    previous = previous or {}
    members: dict[str, list[str]] = defaultdict(list)
    for rec, c in clusters.items():
        members[c].append(rec)
    canon = {c: min(ms) for c, ms in members.items()}
    order = sorted(members, key=lambda c: canon[c])

    # previous id -> how many of its surviving records sit in each new cluster
    spread: dict[str, Counter] = defaultdict(Counter)
    for rec, c in clusters.items():
        if rec in previous:
            spread[previous[rec]][c] += 1
    owner = {pid: min(cnt, key=lambda c: (-cnt[c], canon[c])) for pid, cnt in spread.items()}
    owned: dict[str, list[str]] = defaultdict(list)
    for pid, c in owner.items():
        owned[c].append(pid)

    taken = set(previous.values())
    out: dict[str, str] = {}
    events: list[dict] = []
    for c in order:
        ms = members[c]
        if owned[c]:
            here = Counter(previous[r] for r in ms if r in previous)
            keep = min(owned[c], key=lambda pid: (-here[pid], pid))
            for pid in sorted(owned[c]):
                if pid != keep:
                    events.append({"run": run, "event": "merge", "mdm_id": pid, "into": keep, "records": here[pid]})
            for pid in sorted(set(here) - set(owned[c])):     # records leaving an id that lives on elsewhere
                events.append({"run": run, "event": "move", "mdm_id": pid, "into": keep, "records": here[pid]})
            new = keep
        else:
            new = _fresh(canon[c], taken)
            came_from = sorted({previous[r] for r in ms if r in previous})
            if came_from:
                events.append({"run": run, "event": "split", "mdm_id": new, "from": came_from, "records": len(ms)})
            else:
                events.append({"run": run, "event": "create", "mdm_id": new, "records": len(ms)})
        for r in ms:
            out[r] = new
    for pid in sorted(set(previous.values()) - set(owner)):
        events.append({"run": run, "event": "retire", "mdm_id": pid, "records": 0})
    return out, events


def reconcile(previous: dict[str, str], current: dict[str, str], events: list[dict]) -> tuple[bool, list[str]]:
    """Does the log explain the change from `previous` to `current` exactly? Returns (ok, problems)."""
    prev_ids, new_ids = set(previous.values()), set(current.values())
    by = defaultdict(list)
    for e in events:
        by[e["event"]].append(e)
    merged = {e["mdm_id"] for e in by["merge"]}
    retired = {e["mdm_id"] for e in by["retire"]}
    created = {e["mdm_id"] for e in by["create"]}
    split = {e["mdm_id"] for e in by["split"]}
    problems = []
    expected = (prev_ids - merged - retired) | created | split
    if expected != new_ids:
        problems.append(f"id sets differ: {len(expected - new_ids)} expected but absent, "
                        f"{len(new_ids - expected)} present but unexplained")
    if (merged | retired) & new_ids:
        problems.append(f"{len((merged | retired) & new_ids)} merged/retired id(s) still in use")
    if (created | split) & prev_ids:
        problems.append(f"{len((created | split) & prev_ids)} created/split id(s) were already in use")
    if not merged <= prev_ids or not retired <= prev_ids:
        problems.append("a merge/retire event names an id the previous run did not have")
    for e in by["retire"]:
        if any(previous[r] == e["mdm_id"] for r in previous if r in current):
            problems.append(f"retired {e['mdm_id']} still has a surviving record")
    explained = {(e["mdm_id"], e["into"]) for e in by["merge"] + by["move"]} | \
                {(src, e["mdm_id"]) for e in by["split"] for src in e["from"]}
    unexplained = sum(1 for r, old in previous.items()
                      if r in current and current[r] != old and (old, current[r]) not in explained)
    if unexplained:
        problems.append(f"{unexplained} record(s) changed id with no merge/move/split event")
    moved = {e["mdm_id"] for e in by["move"]}
    if not moved <= (new_ids | merged):
        problems.append("a move event names an id that neither lives on nor merged")
    return not problems, problems
