#!/usr/bin/env python3
"""Prepare the public, synthetic FEBRL4 corpus before offline engine runs.

This is ZR-1 smoke data, deliberately DEVELOPMENT evidence, never a ZR-3 holdout.
"""
import csv
import hashlib
import json
from pathlib import Path

from recordlinkage.datasets import load_febrl4


def main():
    root = Path("data/febrl4")
    root.mkdir(parents=True, exist_ok=True)
    left, right, links = load_febrl4(return_links=True)
    left.to_csv(root / "left.csv")
    right.to_csv(root / "right.csv")
    truth = dict(links)
    # Closed-world truth for 80 development anchors. Label every partner so that
    # negative training candidates are covered without selecting labels by test score.
    anchors = sorted(left.index)[:80]
    partners = sorted(right.index)
    with (root / "labels.csv").open("w") as f:
        writer = csv.writer(f)
        writer.writerow(["a_id", "b_id", "label"])
        for anchor in anchors:
            for partner in partners:
                writer.writerow([anchor, partner, int(partner == truth[anchor])])
    manifest = {"corpus": "FEBRL4 original", "source": "recordlinkage.datasets.load_febrl4 (0.16)",
                "source_url": "https://recordlinkage.readthedocs.io/en/latest/ref-datasets.html#febrl-datasets",
                "license": "FEBRL synthetic example data distributed by recordlinkage (BSD-3-Clause)",
                "purpose": "ZR-1 development smoke, not holdout acceptance", "seed": 0,
                "labels": "all partners for the first 80 lexicographically sorted anchors; closed-world synthetic truth",
                "left_rows": len(left), "right_rows": len(right), "truth_pairs": len(links),
                "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob("*.csv")}}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
