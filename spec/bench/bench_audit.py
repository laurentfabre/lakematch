#!/usr/bin/env python3
"""bench_audit.py — data hygiene checks raised by the independent review (ASTRA_REVIEW.md). No tokens spent.

1. Duplicate pairs across splits. The Magellan splits contain identical pairs in TRAIN and TEST; a related-demo
   prompt then shows a test pair its own labelled copy. Few-shot results are re-scored on the de-duplicated test set.
2. Controlled wording comparison: v0 (generic) vs v1 (+ identity rule) on the pairs BOTH have judged — the v1 cache
   grew with later experiments, so the two columns of table A were not the same population.

    $ZINGG_VENV/bin/python bench_audit.py
"""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bench_cascade as bc, bench_fewshot as fs, bench_pairs as bp
from bench_stats import boot, f1

print("1. few-shot on the de-duplicated test set (test pairs also present in TRAIN or in the judged VALID removed)")
print(f"   {'dataset':<27}{'test':>6}{'dupes':>7}{'own pair in demos':>19}   {'zero-shot':>10}{'k10':>8}{'diff':>8}{'95 % CI':>20}")
for name in ("Structured_Amazon-Google", "Structured_Walmart-Amazon", "Textual_Abt-Buy", "bpid"):
    ds = fs.dataset(name)
    train_keys = {r["key"] for r in ds["train"]}; valid_keys = {r["key"] for r in ds["valid"]}
    k10 = {j["id"]: j["answers"] for j in map(json.loads, (fs.CACHE / f"fs.{name}.k10.jsonl").read_text().splitlines())}
    yv = np.array([r["y"] for r in ds["valid"]])
    tz = bc.tune(np.array([ds["zs"][r["key"]]["probs"][2] for r in ds["valid"]]), yv)
    tk = bc.tune(np.array([k10[r["key"]]["relation"]["probs"][2] for r in ds["valid"]]), yv)
    clean = [r for r in ds["test"] if r["key"] not in train_keys and r["key"] not in valid_keys]
    dup = len(ds["test"]) - len(clean)
    own = sum(1 for r in ds["test"] if r["key"] in train_keys)
    for label, rows in (("all", ds["test"]), ("dedup", clean)):
        y = np.array([r["y"] for r in rows])
        a = np.array([ds["zs"][r["key"]]["probs"][2] for r in rows]) >= tz
        b = np.array([k10[r["key"]]["relation"]["probs"][2] for r in rows]) >= tk
        _, _, lo, hi, _ = boot(a, b, y)
        print(f"   {name + ' ' + label:<27}{len(rows):>6}{dup if label == 'all' else 0:>7}{own if label == 'all' else 0:>19}   {f1(a, y):>10.3f}{f1(b, y):>8.3f}{f1(b, y) - f1(a, y):>+8.3f}{f'[{lo:+.3f}, {hi:+.3f}]':>20}")

print("\n2. generic wording (v0) vs + identity rule (v1) on the SAME pairs, thresholds from the shared valid pairs")
print(f"   {'dataset':<27}{'test':>6}{'pos':>5}{'v0':>8}{'v1':>8}{'diff':>8}{'95 % CI':>20}")
for name in ("Structured_Amazon-Google", "Structured_Walmart-Amazon", "Textual_Abt-Buy", "Structured_Beer", "Structured_Fodors-Zagats", "Structured_iTunes-Amazon"):
    c0, c1 = bp.cached(bp.CACHE / f"{name}.v0.jsonl"), bp.cached(bp.CACHE / f"{name}.v1.jsonl")
    both = lambda split: [r for r in bp.load(name, split) if r["key"] in c0 and r["key"] in c1]
    va, te = both("valid"), both("test")
    yv, yt = np.array([r["y"] for r in va]), np.array([r["y"] for r in te])
    p = lambda c, rows: np.array([c[r["key"]]["probs"][2] for r in rows])
    a, b = p(c0, te) >= bc.tune(p(c0, va), yv), p(c1, te) >= bc.tune(p(c1, va), yv)
    _, _, lo, hi, _ = boot(a, b, yt)
    print(f"   {name:<27}{len(te):>6}{int(yt.sum()):>5}{f1(a, yt):>8.3f}{f1(b, yt):>8.3f}{f1(b, yt) - f1(a, yt):>+8.3f}{f'[{lo:+.3f}, {hi:+.3f}]':>20}")
