#!/usr/bin/env python3
"""bench_bpid.py — BPID (Amazon, EMNLP 2024 Industry; Apache-2.0): personal-identity deduplication.

The public benchmark closest to the lake's `people` entity: profiles with fullname, email(s), phone(s), address(es)
and date of birth, multi-valued, reordered, reformatted and often missing; 10 000 annotator-labelled pairs. Published
F1 (paper, Table 5): Sudowoodo 0.788 (best), Ditto 0.752, Llama3-70B 0.729, GPT-4-turbo 0.687, rules ~0.608.

The release has no fixed split, so this file makes a deterministic one by pair hash: 70 % train / 10 % valid /
20 % test. Scores are therefore INDICATIVE against the paper, not strictly comparable.

    cheap    similarity features + gradient boosting, trained on TRAIN gold labels  (the Zingg / Magellan family)
    jev      Jev zero-shot, threshold tuned on VALID
    stack    logistic regression over [cheap score, Jev distribution], fitted on VALID
    jev->gb  the cheap matcher trained ONLY on Jev's confident labels of a train sample (no human label at all)

    /opt/homebrew/bin/python3 bench_bpid.py ask   [--test 800 --valid 300 --train 600]    # spends tokens, cached
    $ZINGG_VENV/bin/python   bench_bpid.py report
"""
from __future__ import annotations

import argparse
import asyncio
import difflib
import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
DATA = HERE / "data" / "bpid" / "data_release" / "matching_dataset.jsonl"
CACHE = HERE / "cache" / "bpid.people.jsonl"
MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}


def load() -> dict[str, list[dict]]:
    splits = {"train": [], "valid": [], "test": []}
    for line in DATA.read_text(encoding="utf-8").splitlines():
        j = json.loads(line)
        key = hashlib.sha1(line.encode()).hexdigest()[:16]
        bucket = int(key[:4], 16) % 10
        row = {"key": key, "a": j["profile1"], "b": j["profile2"], "y": int(j["match"] == "True")}
        splits["train" if bucket < 7 else "valid" if bucket == 7 else "test"].append(row)
    return splits


def sample(rows: list[dict], n: int) -> list[dict]:
    return sorted(rows, key=lambda r: r["key"])[:n]          # hash order = a fixed pseudo-random sample


def questions() -> dict:
    from typesafe_sdk import Score

    return {"relation": Score(
        instructions=[
            "`record_a` and `record_b` are customer profiles of people, each with a full name, e-mail addresses, phone "
            "numbers, postal addresses and a date of birth. How do they relate?",
            "The same person often appears with the name in a different order, a nickname, initials or typos, with "
            "dates written in different formats, and with different e-mail addresses, phones and postal addresses "
            "over time. Members of one household share a family name, an address and sometimes a phone without being "
            "the same person. An empty field is missing information, not a disagreement."],
        criteria=["They are two different people: the names or the dates of birth positively disagree.",
                  "They could be the same person, but the fields shown do not settle it.",
                  "They are one and the same person."])}


async def ask_all(rows: list[dict]) -> None:
    from mdm_jev import api_key
    from typesafe_sdk import AsyncTypeSafeClient

    os.environ["TYPESAFE_API_KEY"] = api_key()
    have = cached()
    todo = [r for r in rows if r["key"] not in have]
    print(f"BPID: {len(rows)} pairs wanted, {len(todo)} to ask")
    gate, lock, usage, asked = asyncio.Semaphore(12), asyncio.Lock(), [0, 0, 0], questions()

    async def one(client, r):
        async with gate:
            try:
                res = await client.system_one(state={"record_a": r["a"], "record_b": r["b"]}, questions=asked)
            except Exception:  # noqa: BLE001
                usage[2] += 1
                return
        s = res.answers["relation"]
        pr = s.probabilities
        pr = [float(pr[k]) for k in sorted(pr)] if isinstance(pr, dict) else [float(x) for x in pr]
        usage[0] += res.usage.input_tokens; usage[1] += res.usage.output_tokens
        async with lock:
            with CACHE.open("a") as fh:
                fh.write(json.dumps({"key": r["key"], "probs": [round(x, 5) for x in pr], "score": round(float(s.score), 4)}) + "\n")

    async with AsyncTypeSafeClient() as client:
        await asyncio.gather(*(one(client, r) for r in todo))
    print(f"  tokens in {usage[0]} out {usage[1]} errors {usage[2]}")


def cached() -> dict[str, dict]:
    return {j["key"]: j for j in map(json.loads, CACHE.read_text().splitlines())} if CACHE.exists() else {}


# ---- the classical matcher's features ------------------------------------------------------------------------------
def dob(text: str) -> tuple | None:
    t = re.findall(r"[a-z]+|\d+", (text or "").lower())
    nums = [int(x) for x in t if x.isdigit()]
    mon = next((MONTHS[x[:3]] for x in t if x[:3] in MONTHS and not x.isdigit()), None)
    year = next((n for n in nums if n > 31), None)
    rest = [n for n in nums if n <= 31]
    if year is None:
        return None
    if mon is None and len(rest) >= 2:
        return (year, frozenset(rest[:2]))                       # day/month order is ambiguous: compare as a set
    return (year, frozenset([mon] + rest[:1])) if mon else (year, frozenset(rest))


def best(xs: list[str], ys: list[str], f) -> float:
    return max((f(x, y) for x in xs for y in ys), default=-1.0)


def ratio(x: str, y: str) -> float:
    return difflib.SequenceMatcher(None, x, y).ratio()


def feats(r: dict) -> list[float]:
    a, b = r["a"], r["b"]
    na, nb = (a.get("fullname") or "").lower(), (b.get("fullname") or "").lower()
    ta, tb = sorted(na.split()), sorted(nb.split())
    f = [ratio(" ".join(ta), " ".join(tb)) if ta and tb else -1.0,
         len(set(ta) & set(tb)) / max(len(set(ta) | set(tb)), 1) if ta and tb else -1.0,
         float(bool(ta and tb and {t[0] for t in ta} == {t[0] for t in tb}))]
    ea, eb = [e.lower() for e in a.get("email") or []], [e.lower() for e in b.get("email") or []]
    f += [float(bool(set(ea) & set(eb))) if ea and eb else -1.0,
          best([e.split("@")[0] for e in ea], [e.split("@")[0] for e in eb], ratio),
          best([e.split("@")[0] for e in ea], [nb.replace(" ", "")], ratio), best([e.split("@")[0] for e in eb], [na.replace(" ", "")], ratio)]
    pa, pb = [re.sub(r"\D", "", p)[-8:] for p in a.get("phone") or []], [re.sub(r"\D", "", p)[-8:] for p in b.get("phone") or []]
    f += [float(bool(set(pa) & set(pb))) if pa and pb else -1.0, best(pa, pb, ratio)]
    aa, ab = [x.lower() for x in a.get("addr") or []], [x.lower() for x in b.get("addr") or []]
    jac = lambda x, y: len(set(x.split()) & set(y.split())) / max(len(set(x.split()) | set(y.split())), 1)  # noqa: E731
    f += [best(aa, ab, jac), best(aa, ab, ratio)]
    da, db = dob(a.get("dob") or ""), dob(b.get("dob") or "")
    f += [-1.0, -1.0] if da is None or db is None else [float(da[0] == db[0]), float(da == db)]
    f += [float(not ea or not eb), float(not pa or not pb), float(not aa or not ab)]
    return f


def report(_args) -> int:
    import numpy as np
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_predict
    import bench_cascade as bc

    sp, have = load(), cached()
    print(f"split sizes: train {len(sp['train'])} valid {len(sp['valid'])} test {len(sp['test'])}")
    X = lambda rows: np.array([feats(r) for r in rows])          # noqa: E731
    Y = lambda rows: np.array([r["y"] for r in rows])            # noqa: E731
    J = lambda rows: np.array([have[r["key"]]["probs"] + [have[r["key"]]["score"] / 2] for r in rows])  # noqa: E731
    cheap = GradientBoostingClassifier(n_estimators=300, max_depth=3, random_state=0).fit(X(sp["train"]), Y(sp["train"]))
    test_all, valid_all = sp["test"], sp["valid"]
    p_all = cheap.predict_proba(X(test_all))[:, 1]
    t_cheap = bc.tune(cheap.predict_proba(X(valid_all))[:, 1], Y(valid_all))
    print(f"  {'cheap (gold-trained) on the FULL test split':<52} n {len(test_all):>5}  P %.3f R %.3f F1 %.3f" % bc.f1_at(p_all, Y(test_all), t_cheap))

    test = [r for r in test_all if r["key"] in have]
    valid = [r for r in valid_all if r["key"] in have]
    train_j = [r for r in sp["train"] if r["key"] in have]
    if len(test) < 50 or len(valid) < 50:
        print("  (no Jev judgments cached yet: run `ask`)")
        return 0
    yte, yva = Y(test), Y(valid)
    pte, pva = cheap.predict_proba(X(test))[:, 1], cheap.predict_proba(X(valid))[:, 1]
    jte, jva = J(test), J(valid)
    rows_out = [("cheap (gold-trained, 7 000 labels)", bc.f1_at(pte, yte, t_cheap))]
    for name, col in (("jev zero-shot, P(same)", 2), ("jev zero-shot, expected score", 3)):
        rows_out.append((name, bc.f1_at(jte[:, col], yte, bc.tune(jva[:, col], yva))))
    sva, ste = np.hstack([X(valid), pva[:, None], jva]), np.hstack([X(test), pte[:, None], jte])
    stack = GradientBoostingClassifier(n_estimators=150, max_depth=2, random_state=0)
    t_stack = bc.tune(cross_val_predict(stack, sva, yva, cv=5, method="predict_proba")[:, 1], yva)
    rows_out.append((f"stack: features + cheap + Jev (fitted on {len(valid)} valid)", bc.f1_at(stack.fit(sva, yva).predict_proba(ste)[:, 1], yte, t_stack)))
    lr = LogisticRegression(max_iter=1000)
    s2v, s2t = np.hstack([pva[:, None], jva]), np.hstack([pte[:, None], jte])
    t2 = bc.tune(cross_val_predict(lr, s2v, yva, cv=5, method="predict_proba")[:, 1], yva)
    rows_out.append(("stack (logistic): cheap score + Jev only", bc.f1_at(lr.fit(s2v, yva).predict_proba(s2t)[:, 1], yte, t2)))
    if len(train_j) >= 100:                                         # no human label anywhere
        jt = J(train_j)
        keep = (jt[:, 0] >= 0.9) | (jt[:, 2] >= 0.9)
        lab = (jt[:, 2] >= 0.9).astype(int)[keep]
        wrong = int((lab != Y(train_j)[keep]).sum())
        gb = GradientBoostingClassifier(n_estimators=200, max_depth=3, random_state=0).fit(X(train_j)[keep], lab)
        # its threshold also comes from Jev: Jev's confident labels on VALID
        kv = (jva[:, 0] >= 0.9) | (jva[:, 2] >= 0.9)
        tj = bc.tune(gb.predict_proba(X(valid))[kv, 1], (jva[:, 2] >= 0.9).astype(int)[kv])
        rows_out.append((f"jev->gb: trained on {int(keep.sum())} Jev labels ({wrong} wrong), no human", bc.f1_at(gb.predict_proba(X(test))[:, 1], yte, tj)))
    print(f"  on the {len(test)} test pairs Jev judged ({int(yte.sum())} matches):")
    for name, (p, r, f) in rows_out:
        print(f"    {name:<62} P {p:.3f}  R {r:.3f}  F1 {f:.3f}")
    # how good are Jev's confident answers as labels?
    for tau in (0.8, 0.9, 0.95):
        k = (jte[:, 0] >= tau) | (jte[:, 2] >= tau)
        acc = float(((jte[:, 2] >= tau).astype(int)[k] == yte[k]).mean())
        print(f"    Jev confident at tau {tau}: {100 * k.mean():.0f} % of pairs, label accuracy {acc:.3f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask"); a.add_argument("--test", type=int, default=800); a.add_argument("--valid", type=int, default=300)
    a.add_argument("--train", type=int, default=600)
    sub.add_parser("report")
    args = ap.parse_args()
    if args.cmd == "report":
        return report(args)
    sp = load()
    CACHE.parent.mkdir(exist_ok=True)
    asyncio.run(ask_all(sample(sp["test"], args.test) + sample(sp["valid"], args.valid) + sample(sp["train"], args.train)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
