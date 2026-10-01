"""From links to entities: clusters larger than two (`cluster.method`).

Every method reads the same input — the scored links at or above the decision threshold, an undirected edge list
(a, b, p) over record keys — and returns one cluster per record (records without a link are singletons). The edge list
is collected to the driver (it holds one row per link: 334 k rows on Splink historical_50k, 250 k at 10^6) and
union-find does the bookkeeping; the only Spark work inside a loop is verified merge's batched re-scoring. Clustering
is a job task (actions), never a pipeline flow.

    connected_components  every connected component of the link graph is one entity (transitive closure). One false
                          link joins two people.
    center                Hassanzadeh et al. 2009: edges by descending p; the first time a node is seen in an edge
                          with an unassigned partner it becomes a centre and the partner joins it; a node joins a
                          centre only through a direct link to that centre.
    star                  Aslam et al. 2004: nodes by descending degree; an unassigned node becomes a star centre and
                          every unassigned neighbour joins it.
    verified_merge        agglomerative, in rounds. Each round proposes, for every pair of current clusters joined by a
                          link, its best link; the proposals are taken best p first, each against the CURRENT (grown)
                          clusters. Before two clusters join, `cluster.representatives` members of each (the members
                          with the highest summed link p) are compared pairwise and scored by the model; one
                          representative pair below the threshold vetoes the merge. A pair not scored yet (a cluster grew
                          within the round) defers that merge: its pairs are scored in the next round's single batch, so
                          no merge is ever unverified. A round with no merge, nothing newly scored and nothing deferred is
                          the fixed point: the convergence test. `cluster.max_rounds` bounds the loop; reaching it
                          unconverged is reported, never hidden.

Ties are broken on record keys, so the same input gives the same clusters. A cluster's key is its smallest member.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable, Iterable

log = logging.getLogger("lakematch")

Edge = tuple[str, str, float]
Scorer = Callable[[list[tuple[str, str]]], dict[tuple[str, str], float]]


class _UnionFind:
    def __init__(self, nodes: Iterable[str]):
        self.parent = {n: n for n in nodes}

    def find(self, x: str) -> str:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> str:
        ra, rb = self.find(a), self.find(b)
        keep, drop = (ra, rb) if ra < rb else (rb, ra)        # the root is the smallest key: deterministic
        self.parent[drop] = keep
        return keep

    def clusters(self) -> dict[str, str]:
        return {n: self.find(n) for n in self.parent}


def _sorted_edges(edges: Iterable[Edge]) -> list[Edge]:
    canon = {}
    for a, b, p in edges:
        if a == b:
            continue
        k = (a, b) if a < b else (b, a)
        canon[k] = max(p, canon.get(k, p))
    return sorted(((a, b, p) for (a, b), p in canon.items()), key=lambda e: (-e[2], e[0], e[1]))


def _relabel(assign: dict[str, str]) -> dict[str, str]:
    """Cluster key = smallest member."""
    members = defaultdict(list)
    for n, c in assign.items():
        members[c].append(n)
    return {n: min(ms) for ms in members.values() for n in ms}


def connected_components(nodes: Iterable[str], edges: Iterable[Edge]) -> dict[str, str]:
    uf = _UnionFind(nodes)
    for a, b, _ in _sorted_edges(edges):
        uf.union(a, b)
    return _relabel(uf.clusters())


def center(nodes: Iterable[str], edges: Iterable[Edge]) -> dict[str, str]:
    assign: dict[str, str] = {}
    centres: set[str] = set()
    for a, b, _ in _sorted_edges(edges):
        if a not in assign and b not in assign:
            centres.add(a)
            assign[a] = a
            assign[b] = a
        elif a in centres and b not in assign:
            assign[b] = a
        elif b in centres and a not in assign:
            assign[a] = b
    return _relabel({n: assign.get(n, n) for n in nodes})


def star(nodes: Iterable[str], edges: Iterable[Edge]) -> dict[str, str]:
    nbrs = defaultdict(set)
    for a, b, _ in _sorted_edges(edges):
        nbrs[a].add(b)
        nbrs[b].add(a)
    nodes = list(nodes)
    assign: dict[str, str] = {}
    for n in sorted(nodes, key=lambda x: (-len(nbrs[x]), x)):
        if n in assign:
            continue
        assign[n] = n
        for m in sorted(nbrs[n]):
            assign.setdefault(m, n)
    return _relabel(assign)


def verified_merge(nodes: Iterable[str], edges: Iterable[Edge], threshold: float, score: Scorer,
                   representatives: int = 3, max_rounds: int = 20, allowed: Callable[[str, str], bool] | None = None
                   ) -> tuple[dict[str, str], dict]:
    """Returns (assignment, stats). `score` maps record-key pairs to p (one batched call per round); `allowed`
    filters the representative pairs the model can score (linkage: one left and one right record)."""
    edges = _sorted_edges(edges)
    uf = _UnionFind(nodes)
    known = {(a, b): p for a, b, p in edges}           # every link is already scored
    strength = defaultdict(float)
    for a, b, p in edges:
        strength[a] += p
        strength[b] += p
    members = {n: [n] for n in uf.parent}
    vetoed: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    stats = {"rounds": 0, "merges": 0, "vetoes": 0, "scored_pairs": 0, "converged": False}

    def reps(root: str) -> tuple[str, ...]:
        ms = sorted(members[root], key=lambda x: (-strength[x], x))
        return tuple(sorted(ms[:representatives]))

    def key(a: str, b: str) -> tuple[str, str]:
        return (a, b) if a < b else (b, a)

    def unknown(pa, pb) -> set[tuple[str, str]]:
        return {key(x, y) for x in pa for y in pb if key(x, y) not in known and (allowed is None or allowed(x, y))}

    deferred: set[tuple[str, str]] = set()
    for rnd in range(1, max_rounds + 1):
        stats["rounds"] = rnd
        best: dict[tuple[str, str], float] = {}
        for a, b, p in edges:                       # best link per pair of current clusters
            ra, rb = uf.find(a), uf.find(b)
            if ra != rb:
                k = key(ra, rb)
                if k not in best:
                    best[k] = p                     # edges are sorted: the first one is the best
        proposals = [k for k, _ in sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))
                     if (reps(k[0]), reps(k[1])) not in vetoed]
        # one batched scoring per round: the round-start representatives of every proposal + last round's deferrals
        need = sorted(deferred.union(*(unknown(reps(a), reps(b)) for a, b in proposals)) - set(known))
        if need:
            got = score(need)
            stats["scored_pairs"] += len(need)
            for k in need:
                known[k] = got.get(k, 0.0)
        deferred, merged = set(), 0
        for ra, rb in proposals:                    # best first; clusters grow within the round
            x, y = uf.find(ra), uf.find(rb)
            if x == y:
                continue
            pa, pb = reps(x), reps(y)
            if (pa, pb) in vetoed:
                continue
            missing = unknown(pa, pb)
            if missing:                             # grown since the batch: verify next round, never unverified
                deferred |= missing
                continue
            if any(known[key(u, v)] < threshold for u in pa for v in pb if key(u, v) in known):
                vetoed.add((pa, pb))
                stats["vetoes"] += 1
                continue
            root = uf.union(x, y)
            gone = y if root == x else x
            members[root] = members[root] + members.pop(gone)
            merged += 1
        stats["merges"] += merged
        if not merged and not need and not deferred:
            stats["converged"] = True               # fixed point: no merge, nothing new scored, nothing pending
            break
    log.info("verified_merge: %s", stats)
    return _relabel(uf.clusters()), stats


METHODS = ("verified_merge", "connected_components", "center", "star")


def run(method: str, nodes: Iterable[str], edges: Iterable[Edge], threshold: float, score: Scorer | None = None,
        representatives: int = 3, max_rounds: int = 20, allowed=None) -> tuple[dict[str, str], dict]:
    nodes = list(nodes)
    edges = [e for e in edges if e[2] >= threshold]
    if method == "connected_components":
        return connected_components(nodes, edges), {}
    if method == "center":
        return center(nodes, edges), {}
    if method == "star":
        return star(nodes, edges), {}
    if method == "verified_merge":
        if score is None:
            raise ValueError("cluster.method verified_merge needs a scorer for representative pairs")
        return verified_merge(nodes, edges, threshold, score, representatives, max_rounds, allowed)
    raise ValueError(f"unknown cluster method {method}")
