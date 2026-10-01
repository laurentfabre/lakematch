"""ZR-4: the four clustering methods, verified merge's veto and convergence, and stable identity."""
import random

import pytest

from lakematch import cluster, identity

# two true entities {a1 a2 a3} and {b1 b2 b3}, one false bridge a3-b1 (p 0.6) above a 0.5 threshold
NODES = ["a1", "a2", "a3", "b1", "b2", "b3", "z"]
EDGES = [("a1", "a2", 0.95), ("a2", "a3", 0.9), ("a1", "a3", 0.85),
         ("b1", "b2", 0.97), ("b2", "b3", 0.92), ("b1", "b3", 0.88), ("a3", "b1", 0.6)]
TRUE_P = {frozenset(p): (0.9 if p[0][0] == p[1][0] else 0.05)
          for p in [(x, y) for x in NODES for y in NODES if x < y]}


def scorer(calls):
    def score(pairs):
        calls.append(len(pairs))
        return {p: TRUE_P[frozenset(p)] for p in pairs}
    return score


def groups(assign):
    out = {}
    for n, c in assign.items():
        out.setdefault(c, set()).add(n)
    return sorted(sorted(g) for g in out.values())


def test_connected_components_follow_the_false_bridge():
    got, _ = cluster.run("connected_components", NODES, EDGES, 0.5)
    assert groups(got) == [["a1", "a2", "a3", "b1", "b2", "b3"], ["z"]]
    assert got["b3"] == "a1"                                   # cluster key = smallest member


def test_verified_merge_vetoes_the_bridge_and_converges():
    calls = []
    got, stats = cluster.run("verified_merge", NODES, EDGES, 0.5, score=scorer(calls))
    assert groups(got) == [["a1", "a2", "a3"], ["b1", "b2", "b3"], ["z"]]
    assert stats["converged"] and stats["vetoes"] >= 1 and stats["merges"] == 4
    assert stats["rounds"] < 20 and calls                      # it scored representative pairs, in batches


def test_verified_merge_reports_non_convergence():
    _, stats = cluster.run("verified_merge", NODES, EDGES, 0.5, score=scorer([]), max_rounds=1)
    assert not stats["converged"]


def test_center_and_star():
    c, _ = cluster.run("center", NODES, EDGES, 0.5)
    s, _ = cluster.run("star", NODES, EDGES, 0.5)
    assert ["z"] in groups(c) and ["z"] in groups(s)
    assert all(len(g) <= 4 for g in groups(c))                 # a centre takes only its direct neighbours
    for got in (c, s):                                         # every record has exactly one cluster
        assert set(got) == set(NODES)


def test_methods_are_deterministic_under_edge_order():
    rng = random.Random(0)
    for m in ("connected_components", "center", "star"):
        ref, _ = cluster.run(m, NODES, EDGES, 0.5)
        for _ in range(5):
            e = EDGES[:]
            rng.shuffle(e)
            assert cluster.run(m, list(reversed(NODES)), e, 0.5)[0] == ref
    ref, _ = cluster.run("verified_merge", NODES, EDGES, 0.5, score=scorer([]))
    shuffled = EDGES[:]
    rng.shuffle(shuffled)
    assert cluster.run("verified_merge", NODES, shuffled, 0.5, score=scorer([]))[0] == ref


# --- identity ------------------------------------------------------------------------------------------------------
def test_first_run_ids_are_a_pure_function_of_the_clusters():
    clusters = {"l:1": "l:1", "l:2": "l:1", "l:3": "l:3"}
    xw, ev = identity.assign(clusters)
    assert xw["l:1"] == xw["l:2"] == identity.mdm_id("l:1") and xw["l:3"] == identity.mdm_id("l:3")
    assert [e["event"] for e in ev] == ["create", "create"]
    again, ev2 = identity.assign(clusters, previous=xw)
    assert again == xw and ev2 == []                            # unchanged input: no id changes, empty log
    assert identity.reconcile(xw, again, ev2)[0]


def test_merge_split_move_retire_reconcile():
    prev_clusters = {"r1": "r1", "r2": "r1", "r3": "r3", "r4": "r3", "r5": "r5", "r6": "r6", "r7": "r7", "r8": "r7"}
    prev, _ = identity.assign(prev_clusters)
    # r1+r3 groups merge; r5 deleted (retire); r7/r8 split; r6 moves into r1's entity; r9 added
    new_clusters = {"r1": "r1", "r2": "r1", "r3": "r1", "r4": "r1", "r6": "r1", "r7": "r7", "r8": "r8", "r9": "r9"}
    cur, ev = identity.assign(new_clusters, previous=prev, run="2")
    kinds = sorted(e["event"] for e in ev)
    assert kinds == ["create", "merge", "merge", "retire", "split"], ev
    assert cur["r1"] == prev["r1"] and cur["r7"] == prev["r7"] and cur["r8"] != prev["r8"]
    ok, problems = identity.reconcile(prev, cur, ev)
    assert ok, problems


def test_move_event_and_reconcile_rejects_a_doctored_log():
    prev, _ = identity.assign({"a": "a", "b": "a", "c": "a", "x": "x"})
    cur, ev = identity.assign({"a": "a", "b": "a", "c": "x", "x": "x"}, previous=prev)
    assert any(e["event"] == "move" for e in ev)
    assert identity.reconcile(prev, cur, ev)[0]
    assert not identity.reconcile(prev, cur, [e for e in ev if e["event"] != "move"])[0]
    assert not identity.reconcile(prev, {**cur, "a": "m_000000000000"}, ev)[0]


def test_hash_collision_takes_the_next_suffix():
    taken = {identity.mdm_id("k")}
    assert identity._fresh("k", taken) == identity.mdm_id("k#1")
