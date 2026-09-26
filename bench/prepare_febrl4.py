#!/usr/bin/env python3
"""Write the FEBRL4 example inputs: FEBRL4 with half the true partners removed from the right side.

The original FEBRL4 links every left record to exactly one right record, so "always link the nearest neighbour"
scores 1.000 on it. Removing half the partners (the same draw as the 2026-09-19 measurements, seed 23) makes the
matcher reject 2 500 left records, which is the task the benchmarks care about.

Offline: recordlinkage ships the FEBRL files inside the package (`pip install -e ".[bench]"`).

    python bench/prepare_febrl4.py [--out data/febrl4] [--unmatched 0.5]
"""
import argparse
from pathlib import Path

import numpy as np
from recordlinkage.datasets import load_febrl4

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "febrl4"))
ap.add_argument("--unmatched", type=float, default=0.5, help="share of true partners removed from the right side")
ap.add_argument("--seed", type=int, default=23)
args = ap.parse_args()

a, b, links = load_febrl4(return_links=True)
truth = dict(links)
gone = set(np.random.default_rng(args.seed).choice(sorted(truth.values()), size=int(len(truth) * args.unmatched),
                                                  replace=False))
b = b.drop(index=list(gone))
truth = {x: y for x, y in truth.items() if y not in gone}

out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
a.reset_index().fillna("").astype(str).to_csv(out / "left.csv", index=False)
b.reset_index().fillna("").astype(str).to_csv(out / "right.csv", index=False)
with open(out / "truth.csv", "w") as fh:
    fh.write("l_id,r_id\n")
    for x, y in sorted(truth.items()):
        fh.write(f"{x},{y}\n")
print(f"left {len(a)} · right {len(b)} · true links {len(truth)} · unmatched left {len(a) - len(truth)} -> {out}")
