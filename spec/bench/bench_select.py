#!/usr/bin/env python3
"""bench_select.py — "select among candidates" vs independent pair judgments (ComEM, COLING 2025), with Jev.

The Magellan test pairs share anchor records: grouping them by the left record rebuilds the candidate set a blocker
would hand to the matcher. Two ways to spend Jev on one anchor with k candidates:

    pairwise   k requests, one Score each (bench_pairs variant v1)      — candidates cannot see each other
    select     ceil(k/4) requests, one Choice each: candidate_1..4 or none — candidates compete

Both are judged on exactly the same pairs (a reproducible sample of anchors), thresholds tuned on VALID.

    python3 bench_select.py run Structured_Amazon-Google --anchors 250
    python3 bench_select.py report
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import hashlib
import json
import os
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bench_pairs as bp  # noqa: E402

K = 4


def groups(dataset: str, split: str, n_anchors: int) -> list[list[dict]]:
    by = collections.defaultdict(list)
    for r in bp.load(dataset, split):
        by[json.dumps(r["a"], sort_keys=True)].append(r)
    keys = sorted(by)
    random.Random(11).shuffle(keys)
    return [by[k] for k in keys[:n_anchors]]


def chunks(group: list[dict]) -> list[list[dict]]:
    group = sorted(group, key=lambda r: r["key"])
    return [group[i:i + K] for i in range(0, len(group), K)]


def question(dataset: str, k: int):
    from typesafe_sdk import Choice

    name = dataset.split("_", 1)[1]
    noun, what = bp.DOMAIN[name]
    criteria = {f"candidate_{i + 1}": f"`candidates[{i}]` is the same {noun} as `anchor`." for i in range(k)}
    criteria["none"] = f"None of the candidates is the same {noun} as `anchor`."
    return {"pick": Choice(
        instructions=[f"`anchor` and `candidates` are {what}. Which candidate, if any, is one and the same {noun} as `anchor`?",
                      {"identity_rule": bp.RULES[name]},
                      "At most one candidate is the same. Candidates are often near-misses of each other: compare them "
                      "against the anchor and against one another. An empty field is missing information, not a "
                      "disagreement; wording, formatting and price differences between the sources are expected."],
        criteria=criteria)}


async def run_select(todo: list[list[dict]], dataset: str, path: Path) -> dict:
    from typesafe_sdk import AsyncTypeSafeClient

    os.environ["TYPESAFE_API_KEY"] = bp.api_key() or sys.exit("no key")
    gate, lock, usage = asyncio.Semaphore(bp.CONCURRENCY), asyncio.Lock(), {"in": 0, "out": 0, "err": 0, "req": 0}

    async def one(client, chunk):
        async with gate:
            try:
                r = await client.system_one(state={"anchor": chunk[0]["a"], "candidates": [c["b"] for c in chunk]},
                                            questions=question(dataset, len(chunk)))
            except Exception:  # noqa: BLE001
                usage["err"] += 1
                return
        probs = r.answers["pick"].probabilities
        usage["in"] += r.usage.input_tokens; usage["out"] += r.usage.output_tokens; usage["req"] += 1
        async with lock:
            with path.open("a", encoding="utf-8") as fh:
                for i, c in enumerate(chunk):
                    fh.write(json.dumps({"key": c["key"], "noul": round(float(probs.get(f"candidate_{i + 1}", 0.0)), 5),
                                         "k": len(chunk)}) + "\n")

    async with AsyncTypeSafeClient() as client:
        await asyncio.gather(*(one(client, c) for c in todo))
    return usage


def cmd_run(args) -> int:
    bp.CACHE.mkdir(exist_ok=True)
    sel_path = bp.CACHE / f"{args.dataset}.select.jsonl"
    pair_path = bp.CACHE / f"{args.dataset}.v1.jsonl"
    for split, n in (("test", args.anchors), ("valid", args.anchors // 2)):
        gs = groups(args.dataset, split, n)
        rows = [r for g in gs for r in g]
        have_sel, have_pair = bp.cached(sel_path), bp.cached(pair_path)
        todo_sel = [c for g in gs for c in chunks(g) if any(r["key"] not in have_sel for r in c)]
        todo_pair = [r for r in rows if r["key"] not in have_pair]
        print(f"{args.dataset} {split}: {len(gs)} anchors, {len(rows)} pairs | select requests to send {len(todo_sel)} | pairwise to send {len(todo_pair)}")
        if todo_sel:
            print("  select  ", asyncio.run(run_select(todo_sel, args.dataset, sel_path)))
        if todo_pair:
            print("  pairwise", asyncio.run(bp.judge(todo_pair, args.dataset, "v1", pair_path)))
    return 0


def cmd_report(args) -> int:
    print(f"{'dataset':<27}{'pairs':>6}{'pos':>5} | {'pairwise F1':>11} {'P':>6} {'R':>6} | {'select F1':>10} {'P':>6} {'R':>6} | {'mean F1':>8} {'P':>6} {'R':>6}")
    for sel_path in sorted(bp.CACHE.glob("*.select.jsonl")):
        dataset = sel_path.name[:-len(".select.jsonl")]
        if not (bp.DATA / dataset / "test.txt").exists():
            continue                     # bench_pipeline.py keeps its own *.select.jsonl here
        sel, pair = bp.cached(sel_path), bp.cached(bp.CACHE / f"{dataset}.v1.jsonl")
        def cols(split):
            rows = [r for r in bp.load(dataset, split) if r["key"] in sel and r["key"] in pair]
            return ([(bp.p_same(pair[r["key"]]), r["y"]) for r in rows], [(sel[r["key"]]["noul"], r["y"]) for r in rows],
                    [((bp.p_same(pair[r["key"]]) + sel[r["key"]]["noul"]) / 2, r["y"]) for r in rows])
        (pv, sv, mv), (pt, st, mt) = cols("valid"), cols("test")
        out = []
        for v, t in ((pv, pt), (sv, st), (mv, mt)):
            p, r, f = bp.prf(t, bp.best_tau(v))
            out += [f, p, r]
        print(f"{dataset:<27}{len(pt):>6}{sum(y for _, y in pt):>5} | {out[0]:>11.3f} {out[1]:>6.3f} {out[2]:>6.3f} | "
              f"{out[3]:>10.3f} {out[4]:>6.3f} {out[5]:>6.3f} | {out[6]:>8.3f} {out[7]:>6.3f} {out[8]:>6.3f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.set_defaults(fn=cmd_run); r.add_argument("dataset"); r.add_argument("--anchors", type=int, default=250)
    sub.add_parser("report").set_defaults(fn=cmd_report)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
