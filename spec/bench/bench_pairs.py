#!/usr/bin/env python3
"""bench_pairs.py — Jev as a zero-shot pair matcher on the public Magellan/DeepMatcher benchmarks.

The fixed test splits (Ditto's mirror, data/<Group>_<Name>/{train,valid,test}.txt) make the F1 comparable with the
published numbers. Protocol: the decision threshold is chosen on a sample of the VALID split, then frozen and
reported on TEST. Every judgment is cached in cache/<dataset>.<variant>.jsonl keyed by the pair's content hash, so a
rerun, a new threshold or a new metric costs nothing.

    python3 bench_pairs.py run  Structured_Beer --variant v0 [--split test] [--limit N]
    python3 bench_pairs.py report                      # every cached dataset x variant, valid-tuned threshold

All data here is public benchmark data; nothing personal is sent.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from mdm_jev import api_key  # noqa: E402

DATA, CACHE = HERE / "data", HERE / "cache"
CONCURRENCY = 12

# What the two records are, per dataset: the only dataset-specific text a variant may use.
DOMAIN = {
    "Fodors-Zagats": ("restaurant", "restaurant listings from two guides (Fodor's and Zagat)"),
    "Beer": ("beer", "beer listings from two rating sites (BeerAdvocate and RateBeer)"),
    "iTunes-Amazon": ("song", "music track listings from iTunes and Amazon Music"),
    "Amazon-Google": ("software product", "software product offers from Amazon and Google Shopping"),
    "Walmart-Amazon": ("product", "electronics product offers from Walmart and Amazon"),
    "DBLP-ACM": ("publication", "bibliographic records of computer-science papers from DBLP and the ACM library"),
    "Abt-Buy": ("product", "consumer-electronics product offers from Abt.com and Buy.com"),
}

RULES = {
    "Fodors-Zagats": "The same restaurant keeps its name, street address and phone number; cuisine labels and the "
                     "`class` number differ between guides and are not evidence. Two branches of one chain at "
                     "different addresses are different restaurants.",
    "Beer": "The same beer has the same brewery and the same beer name; style wording and ABV formatting vary "
            "between sites. A different vintage, barrel-aged, imperial or otherwise named variant from the same "
            "brewery is a different beer.",
    "iTunes-Amazon": "The same track has the same song title, artist and album; price, copyright text and date "
                     "formats differ between stores. A remix, live, clean/explicit or differently-featured version, "
                     "or the same song on a different album, is a different track.",
    "Amazon-Google": "The same product is the same software title in the same edition, version, platform and "
                     "licence type. A different version or year, an upgrade versus a full licence, a different "
                     "number of users, or a different platform is a different product. Prices differ between shops "
                     "and manufacturer is often missing.",
    "Walmart-Amazon": "The same product has the same brand and the same model number or an equivalent model "
                      "designation. A different colour, capacity, size or pack count is a different product. Titles "
                      "are worded differently between shops and prices differ.",
    "DBLP-ACM": "The same publication has the same title and the same authors; venue names are abbreviated "
                "differently and author lists may be truncated or use initials. A different year together with a "
                "different venue usually means a different paper (for example a conference and a journal version).",
    "Abt-Buy": "The same product has the same brand and the same model number or designation, which often appears "
               "inside the name or description. A different colour, size or capacity suffix on the model is a "
               "different product. One side often has a long description and the other none.",
}


def parse(line: str) -> tuple[dict, dict, int]:
    left, right, label = line.rstrip("\n").split("\t")
    def rec(text):
        out = {}
        for part in re.split(r"\bCOL ", text):
            if " VAL" in part:
                key, _, val = part.partition(" VAL")
                out[key.strip()] = re.sub(r"\s+", " ", val.replace("`", "").replace(" '", " ").strip(" '")).strip()
        return out
    return rec(left), rec(right), int(label)


def load(dataset: str, split: str) -> list[dict]:
    rows = []
    for line in (DATA / dataset / f"{split}.txt").read_text(encoding="utf-8").splitlines():
        a, b, y = parse(line)
        key = hashlib.sha1(json.dumps([a, b], sort_keys=True).encode()).hexdigest()[:16]
        rows.append({"key": key, "a": a, "b": b, "y": y})
    return rows


def questions(dataset: str, variant: str) -> dict:
    from typesafe_sdk import Noul, Score

    name = dataset.split("_", 1)[1]
    noun, what = DOMAIN[name]
    if variant == "v0":      # the generic wording mdm_jev.py shipped with
        return {"relation": Score(
            instructions=[f"How do `record_a` and `record_b` relate? They are {what}.",
                          "An empty field is missing information, not a disagreement."],
            criteria=[f"They describe two different {noun}s.",
                      f"They could be the same {noun}, but the fields shown do not settle it.",
                      f"They describe one and the same {noun}."])}
    if variant == "v1":      # + the domain's identity rule (what makes two records the same real-world thing)
        return {"relation": Score(
            instructions=[f"How do `record_a` and `record_b` relate? They are {what}.",
                          {"identity_rule": RULES[name]},
                          "An empty field is missing information, not a disagreement. Wording, formatting and price "
                          "differences between the two sources are expected and are not disagreements."],
            criteria=[f"They describe two different {noun}s: some identifying attribute positively disagrees.",
                      f"They could be the same {noun}, but the fields shown do not settle it.",
                      f"They describe one and the same {noun}: the identifying attributes agree."])}
    if variant == "v2":      # v1 as a direct Noul: P(same) without a middle level
        return {"same": Noul(
            instructions=[f"`record_a` and `record_b` are {what}. Do they refer to one and the same real-world {noun}?",
                          {"identity_rule": RULES[name]},
                          "An empty field is missing information, not a disagreement. Wording, formatting and price "
                          "differences between the two sources are expected and are not disagreements."])}
    raise SystemExit(f"unknown variant {variant}")


STAT = "same"      # "same" = P(top level); "score" = expected level / 2, which lets "unsure" count for half


def p_same(answer: dict) -> float:
    if "probs" not in answer:
        return answer["noul"]
    return answer["score"] / 2 if STAT == "score" else answer["probs"][2]


async def judge(rows: list[dict], dataset: str, variant: str, path: Path) -> dict:
    import os
    from typesafe_sdk import AsyncTypeSafeClient

    os.environ["TYPESAFE_API_KEY"] = api_key() or sys.exit("no TYPESAFE_API_KEY")
    asked, gate, usage = questions(dataset, variant), asyncio.Semaphore(CONCURRENCY), {"in": 0, "out": 0, "err": 0}
    lock = asyncio.Lock()

    async def one(client, row):
        async with gate:
            try:
                r = await client.system_one(state={"record_a": row["a"], "record_b": row["b"]}, questions=asked)
            except Exception as err:  # noqa: BLE001
                usage["err"] += 1
                return
        out = {"key": row["key"]}
        if "relation" in r.answers:
            s = r.answers["relation"]
            pr = s.probabilities
            out["probs"] = [round(float(x), 5) for x in ([pr[k] for k in sorted(pr)] if isinstance(pr, dict) else pr)]
            out["score"] = round(float(s.score), 4)
        else:
            out["noul"] = round(float(r.answers["same"].noul), 5)
        usage["in"] += r.usage.input_tokens
        usage["out"] += r.usage.output_tokens
        async with lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(out) + "\n")

    async with AsyncTypeSafeClient() as client:
        await asyncio.gather(*(one(client, r) for r in rows))
    return usage


def cached(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {j["key"]: j for j in map(json.loads, path.read_text(encoding="utf-8").splitlines())}


def prf(pairs: list[tuple[float, int]], tau: float) -> tuple[float, float, float]:
    tp = sum(1 for p, y in pairs if p >= tau and y == 1)
    fp = sum(1 for p, y in pairs if p >= tau and y == 0)
    fn = sum(1 for p, y in pairs if p < tau and y == 1)
    pr = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    return pr, rc, (2 * pr * rc / (pr + rc) if pr + rc else 0.0)


def best_tau(pairs: list[tuple[float, int]]) -> float:
    grid = [i / 100 for i in range(5, 100, 5)]
    return max(grid, key=lambda t: (prf(pairs, t)[2], -abs(t - 0.5)))


def cmd_run(args) -> int:
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"{args.dataset}.{args.variant}.jsonl"
    rows = load(args.dataset, args.split)
    if args.limit and len(rows) > args.limit:      # stratified-by-nothing but reproducible sample
        rows = random.Random(7).sample(rows, args.limit)
    have = cached(path)
    todo = [r for r in rows if r["key"] not in have]
    print(f"{args.dataset} {args.split} variant {args.variant}: {len(rows)} pairs, {len(todo)} to ask")
    if todo:
        usage = asyncio.run(judge(todo, args.dataset, args.variant, path))
        print(f"  tokens in {usage['in']} out {usage['out']} errors {usage['err']}")
    return 0


def cmd_report(args) -> int:
    print(f"{'dataset':<28}{'variant':<8}{'n_test':>7}{'pos':>5}{'tau(valid)':>11}{'P':>7}{'R':>7}{'F1':>7}   {'F1@0.5':>7}{'F1 oracle':>10}")
    for path in sorted(CACHE.glob("*.jsonl")):
        dataset, _, variant = path.name[:-6].rpartition(".")     # usage.jsonl has no variant part
        if variant not in ("v0", "v1", "v2") or not (DATA / dataset / "test.txt").exists():
            continue                     # other experiments share this cache directory
        have = cached(path)
        def scored(split):
            return [(p_same(have[r["key"]]), r["y"]) for r in load(dataset, split) if r["key"] in have]
        test, valid = scored("test"), scored("valid")
        if not test:
            continue
        tau = best_tau(valid) if len(valid) >= 50 else 0.5
        p, r, f = prf(test, tau)
        print(f"{dataset:<28}{variant:<8}{len(test):>7}{sum(y for _, y in test):>5}{tau if len(valid) >= 50 else float('nan'):>11.2f}"
              f"{p:>7.3f}{r:>7.3f}{f:>7.3f}   {prf(test, 0.5)[2]:>7.3f}{prf(test, best_tau(test))[2]:>10.3f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.set_defaults(fn=cmd_run)
    r.add_argument("dataset"); r.add_argument("--variant", default="v0")
    r.add_argument("--split", default="test"); r.add_argument("--limit", type=int, default=0)
    rp = sub.add_parser("report"); rp.set_defaults(fn=cmd_report)
    rp.add_argument("--stat", choices=["same", "score"], default="same")
    args = ap.parse_args()
    global STAT
    STAT = getattr(args, "stat", "same")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
