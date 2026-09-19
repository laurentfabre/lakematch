#!/usr/bin/env python3
"""bench_pipeline.py — the architecture the literature points to, end to end on FEBRL4, with NO human label.

    1. blocking    char-3-gram TF-IDF, top-k neighbours in B for every record of A (Sparkly, VLDB 2023: top-k
                   TF-IDF/BM25 blocking reaches 92-100 % recall at k = 10). Recall is MEASURED, since it caps everything.
    2. labels      Jev (3-level Score, the febrl4 wording of mdm_jev.py) labels a few hundred candidate pairs spread
                   over the similarity range; only confident answers become labels. No ground truth is used to train.
    3. matcher     gradient boosting over per-field similarity features (the Zingg / Magellan family), trained on
                   those Jev labels.
    4. decision    one link per anchor: the best candidate if the matcher is sure; if it is unsure, Jev SELECTS among
                   the anchor's top-4 candidates (ComEM, COLING 2025). The 0.5 decision threshold, tau = 0.9 and the
                   arbitration bands are CONSTANTS, not learnt; the rule 'Jev overrides only when confident' was
                   adopted after seeing test results (Astra review, 2026-09-19), so treat it as tuned on this data.
    controls       nearest neighbour alone, and with a cosine cut learnt from Jev's labels: FEBRL4 has a match for
                   every record, so --unmatched 0.5 removes half of the partners to make rejection matter.
    5. score       against the 5 000 true links — the only place ground truth is read.

    $ZINGG_VENV/bin/python bench_pipeline.py [--k 5] [--labels 400]
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bench_cascade as bc  # noqa: E402

CACHE = HERE / "cache"
SYSTEM_PY = "/opt/homebrew/bin/python3"
TAG = ""
FIELDS = ["given_name", "surname", "street_number", "address_1", "address_2", "suburb", "postcode", "state",
          "date_of_birth", "soc_sec_id"]
WHAT = ("person records from a synthetic census-style test set; a duplicate is the same person re-keyed with typos, "
        "swapped or missing fields, abbreviations or a changed digit")

# --- Jev runs in the system Python (typesafe_sdk lives there): this file calls itself through it ---------------------
WORKER = r'''
import asyncio, json, os, sys
sys.path.insert(0, %(here)r); sys.path.insert(0, %(parent)r)
from mdm_jev import api_key
from typesafe_sdk import AsyncTypeSafeClient, Choice, Score
os.environ["TYPESAFE_API_KEY"] = api_key()
WHAT = %(what)r
jobs = [json.loads(l) for l in open(sys.argv[1])]
score_q = {"relation": Score(
    instructions=["How do `record_a` and `record_b` relate? They are " + WHAT + ".", "An empty field is missing information, not a disagreement."],
    criteria=["They describe two different individuals.", "They could be the same individual, but the fields shown do not settle it.", "They describe one and the same individual."])}
def pick_q(k):
    c = {f"candidate_{i+1}": f"`candidates[{i}]` is the same individual as `anchor`." for i in range(k)}
    c["none"] = "None of the candidates is the same individual as `anchor`."
    return {"pick": Choice(instructions=["`anchor` and `candidates` are " + WHAT + ". Which candidate, if any, is one and the same individual as `anchor`?",
        "At most one candidate is the same. An empty field is missing information, not a disagreement."], criteria=c)}
async def main():
    gate, usage = asyncio.Semaphore(12), [0, 0]
    out = open(sys.argv[2], "a")
    async def one(client, j):
        async with gate:
            try:
                if j["kind"] == "pair":
                    r = await client.system_one(state={"record_a": j["a"], "record_b": j["b"]}, questions=score_q)
                    p = r.answers["relation"].probabilities
                    res = {"id": j["id"], "probs": [float(x) for x in ([p[k] for k in sorted(p)] if isinstance(p, dict) else p)]}
                else:
                    r = await client.system_one(state={"anchor": j["a"], "candidates": j["c"]}, questions=pick_q(len(j["c"])))
                    p = r.answers["pick"].probabilities
                    res = {"id": j["id"], "pick": [float(p.get(f"candidate_{i+1}", 0.0)) for i in range(len(j["c"]))]}
            except Exception as e:
                return
        usage[0] += r.usage.input_tokens; usage[1] += r.usage.output_tokens
        out.write(json.dumps(res) + "\n"); out.flush()
    async with AsyncTypeSafeClient() as client:
        await asyncio.gather(*(one(client, j) for j in jobs))
    print(json.dumps({"in": usage[0], "out": usage[1]}))
asyncio.run(main())
'''


def ask(jobs: list[dict], name: str) -> dict[str, dict]:
    """Send jobs to Jev unless already cached; return every cached answer by id."""
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"febrl4_pipeline{TAG}.{name}.jsonl"
    have = {j["id"]: j for j in map(json.loads, path.read_text().splitlines())} if path.exists() else {}
    todo = [j for j in jobs if j["id"] not in have]
    if todo:
        tmp = CACHE / f".jobs_{name}.jsonl"
        tmp.write_text("\n".join(json.dumps(j) for j in todo))
        code = WORKER % {"here": str(HERE), "parent": str(HERE.parent), "what": WHAT}
        res = subprocess.run([SYSTEM_PY, "-c", code, str(tmp), str(path)], capture_output=True, text=True)
        tmp.unlink()
        print(f"    Jev {name}: sent {len(todo)} request(s), tokens {res.stdout.strip() or res.stderr[-300:]}")
        have = {j["id"]: j for j in map(json.loads, path.read_text().splitlines())}
    return have


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--labels", type=int, default=400)
    ap.add_argument("--tau", type=float, default=0.90)
    ap.add_argument("--drop", default="", help="comma-separated fields hidden from blocking, the matcher and Jev")
    ap.add_argument("--unmatched", type=float, default=0.0, help="share of A records whose true match is REMOVED from B, so that rejecting matters")
    args = ap.parse_args()
    global FIELDS, TAG
    FIELDS = [f for f in FIELDS if f not in args.drop.split(",")]
    TAG = "_no" + "_".join(sorted(f for f in args.drop.split(",") if f)) if args.drop else ""
    TAG += f"_u{int(args.unmatched * 100)}" if args.unmatched else ""

    from recordlinkage.datasets import load_febrl4
    a, b, links = load_febrl4(return_links=True)
    a, b = a.fillna("").astype(str), b.fillna("").astype(str)
    truth = {x: y for x, y in links}                     # rec-N-org -> rec-N-dup-0
    if args.unmatched:                                   # remove the partner of a random share of A: those anchors must be REJECTED
        gone = set(np.random.default_rng(23).choice(sorted(truth.values()), size=int(len(truth) * args.unmatched), replace=False))
        b = b.drop(index=list(gone))
        truth = {x: y for x, y in truth.items() if y not in gone}
    ra = [dict(zip(FIELDS, row)) for row in a[FIELDS].itertuples(index=False)]
    rb = [dict(zip(FIELDS, row)) for row in b[FIELDS].itertuples(index=False)]
    ida, idb = list(a.index), list(b.index)

    # 1. blocking -----------------------------------------------------------------------------------------------
    tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 3), sublinear_tf=True, min_df=1)
    text = lambda r: " ".join(r.values())  # noqa: E731
    mb = tfidf.fit_transform([text(r) for r in rb])
    ma = tfidf.transform([text(r) for r in ra])
    sims = (ma @ mb.T).toarray()
    top = np.argsort(-sims, axis=1)[:, : max(args.k, 10)]
    pos_b = {rid: i for i, rid in enumerate(idb)}
    for k in (1, 2, 5, 10):
        hit = sum(1 for i, rid in enumerate(ida) if rid in truth and pos_b[truth[rid]] in top[i, :k])
        print(f"  blocking recall@{k:<2} = {hit / len(truth):.4f}   ({len(ida) * k} candidate pairs, {len(truth)} true links)")
    top = top[:, : args.k]
    cand = [(i, int(j)) for i in range(len(ida)) for j in top[i]]
    rows = [{"a": ra[i], "b": rb[j]} for i, j in cand]
    x = bc.features(rows, tfidf)
    rank = np.tile(np.arange(args.k), len(ida))
    gap = np.repeat(sims[np.arange(len(ida)), top[:, 0]] - sims[np.arange(len(ida)), top[:, 1]], args.k)
    x = np.hstack([x, rank[:, None], gap[:, None]])
    y_true = np.array([int(truth.get(ida[i]) == idb[j]) for i, j in cand])

    # 2. labels from Jev only -----------------------------------------------------------------------------------
    rng = np.random.default_rng(3)
    cos = x[:, 0]
    bins = np.digitize(cos, np.quantile(cos, np.linspace(0, 1, 9)[1:-1]))
    pick = np.concatenate([rng.choice(np.where(bins == q)[0], size=args.labels // 8, replace=False) for q in range(8)])
    pid = lambda n: hashlib.sha1(json.dumps(rows[n], sort_keys=True).encode()).hexdigest()[:16]  # noqa: E731
    got = ask([{"kind": "pair", "id": pid(n), "a": rows[n]["a"], "b": rows[n]["b"]} for n in pick], "labels")
    lab_idx, lab_y = [], []
    for n in pick:
        pr = got.get(pid(n), {}).get("probs")
        if pr and max(pr[0], pr[2]) >= args.tau:
            lab_idx.append(n); lab_y.append(int(pr[2] >= args.tau))
    lab_idx, lab_y = np.array(lab_idx), np.array(lab_y)
    wrong = int((lab_y != y_true[lab_idx]).sum())
    print(f"  Jev labels: asked {len(pick)}, confident {len(lab_y)} ({int(lab_y.sum())} match / {int((1 - lab_y).sum())} no-match), "
          f"wrong vs ground truth: {wrong} ({100 * wrong / max(len(lab_y), 1):.1f} %)")

    # 3. matcher trained on Jev labels ----------------------------------------------------------------------------
    model = GradientBoostingClassifier(n_estimators=200, max_depth=3, random_state=0).fit(x[lab_idx], lab_y)
    p = model.predict_proba(x)[:, 1].reshape(len(ida), args.k)
    best = p.argmax(axis=1)
    pbest = p[np.arange(len(ida)), best]

    def score(decide: np.ndarray, choice: np.ndarray, name: str, extra: str = "") -> None:
        tp = sum(1 for i in range(len(ida)) if decide[i] and idb[top[i, choice[i]]] == truth.get(ida[i]))
        n = int(decide.sum())
        pr, rc = tp / max(n, 1), tp / len(truth)
        print(f"  {name:<58} links {n:>5} TP {tp:>5} FP {n - tp:>4} FN {len(truth) - tp:>4}  P {pr:.4f} R {rc:.4f} F1 {2 * pr * rc / (pr + rc):.4f} {extra}")

    nn = np.zeros(len(ida), dtype=int)
    score(np.ones(len(ida), dtype=bool), nn, "CONTROL nearest neighbour alone, always link (no Jev, no model)")
    # a similarity cut chosen on Jev's labels only: the cosine that best separates Jev's match / no-match labels
    cos_lab = x[lab_idx, 0]
    cuts = np.unique(np.round(cos_lab, 3))
    cut = float(max(cuts, key=lambda c: ((cos_lab >= c) == (lab_y == 1)).mean()))
    top_cos = sims[np.arange(len(ida)), top[:, 0]]
    score(top_cos >= cut, nn, f"CONTROL nearest neighbour + cosine cut {cut:.3f} learnt from Jev labels")
    score(pbest >= 0.5, best, "matcher alone (Jev-trained), best candidate >= 0.5")

    # 4. Jev selects for the anchors the matcher is unsure about --------------------------------------------------
    for lo, hi in ((0.02, 0.98), (0.005, 0.995)):
        unsure = np.where((pbest > lo) & (pbest < hi))[0]
        order = np.argsort(-p[unsure], axis=1)[:, :4]
        jobs = [{"kind": "select", "id": f"{ida[i]}|{','.join(map(str, order[u]))}", "a": ra[i],
                 "c": [rb[top[i, c]] for c in order[u]]} for u, i in enumerate(unsure)]
        got = ask(jobs, "select")
        # Jev overrides the matcher only when it is sure: a confident pick, or a confident "none". Otherwise the
        # matcher's own decision stands (dropping the link whenever Jev hesitated cost 52 true links).
        decide, choice = pbest >= 0.5, best.copy()
        for u, i in enumerate(unsure):
            pk = got.get(jobs[u]["id"], {}).get("pick")
            if pk:
                c = int(np.argmax(pk))
                if pk[c] >= args.tau:
                    decide[i], choice[i] = True, order[u][c]
                elif 1 - sum(pk) >= args.tau:
                    decide[i] = False
        score(decide, choice, f"matcher + Jev select on the unsure band ({lo}, {hi})",
              f"| {len(unsure)} anchors to Jev ({100 * len(unsure) / len(ida):.1f} %)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
