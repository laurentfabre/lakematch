#!/usr/bin/env python3
"""Measured Splink references for BENCHMARKS.md -> bench/results/splink.json.

Splink (MIT, DuckDB backend) is run the way its own demos run it: unsupervised Fellegi-Sunter, u by random
sampling, m by expectation maximisation over a few blocking rules, then `predict` over the prediction blocking rules.
No label is used to fit it. Reported: pairwise precision / recall / F1 over the WHOLE corpus at match probability
>= 0.5 (the Bayes decision; Splink's demos pick a threshold by eye), and — marked as an oracle — the best F1 over
thresholds chosen with the truth, an upper bound for any threshold Splink could be given. Pairs the blocking rules
never proposed count as false negatives. lakematch's rows are on TEST units only: comparable in kind, not identical.
Splink is a benchmark-only tool here, never a lakematch dependency.

    python bench/splink_reference.py [--only febrl3,splink_historical_50k]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpora  # noqa: E402

OUT = HERE / "results" / "splink.json"


def febrl_settings(link_type: str, drop: tuple[str, ...] = ()):
    import splink.comparison_library as cl
    from splink import SettingsCreator, block_on
    comps = {"given_name": cl.NameComparison("given_name"), "surname": cl.NameComparison("surname"),
             "date_of_birth": cl.LevenshteinAtThresholds("date_of_birth", [1, 2]),
             "street_number": cl.ExactMatch("street_number"),
             "address_1": cl.JaroWinklerAtThresholds("address_1", [0.9, 0.8]),
             "suburb": cl.JaroWinklerAtThresholds("suburb", [0.9, 0.8]),
             "postcode": cl.LevenshteinAtThresholds("postcode", [1]), "state": cl.ExactMatch("state"),
             "soc_sec_id": cl.LevenshteinAtThresholds("soc_sec_id", [1, 2])}
    comps = [c for col, c in comps.items() if col not in drop]
    rules = {("given_name", "surname"), ("surname", "date_of_birth"), ("given_name", "date_of_birth"),
             ("postcode", "street_number"), ("soc_sec_id",), ("address_1", "suburb")}
    rules = [block_on(*r) for r in sorted(rules) if not set(r) & set(drop)]
    train = [block_on("date_of_birth"), block_on("surname"), block_on("given_name", "postcode")]
    return SettingsCreator(link_type=link_type, comparisons=comps, blocking_rules_to_generate_predictions=rules,
                           retain_intermediate_calculation_columns=False), train


def h50k_settings():
    import splink.comparison_library as cl
    from splink import SettingsCreator, block_on
    comps = [cl.NameComparison("first_name"), cl.NameComparison("surname"),
             cl.LevenshteinAtThresholds("dob", [1, 2]), cl.JaroWinklerAtThresholds("birth_place", [0.9]),
             cl.PostcodeComparison("postcode_fake"), cl.ExactMatch("occupation")]
    rules = [block_on("first_name", "surname"), block_on("surname", "dob"), block_on("first_name", "dob"),
             block_on("postcode_fake", "first_name"), block_on("postcode_fake", "surname"),
             block_on("dob", "birth_place"), block_on("occupation", "dob")]
    train = [block_on("first_name", "surname"), block_on("dob"), block_on("postcode_fake")]
    return SettingsCreator(link_type="dedupe_only", comparisons=comps, blocking_rules_to_generate_predictions=rules,
                           retain_intermediate_calculation_columns=False), train


def run_one(name: str) -> dict:
    from splink import DuckDBAPI, Linker
    import splink
    drop = ("soc_sec_id",) if name.endswith("_no_soc_sec_id") else ()
    c = corpora.febrl4_half_unmatched(drop=drop) if name.startswith("febrl4_half") else corpora.LOADERS[name]()
    t0 = time.time()
    db = DuckDBAPI()
    if c.kind == "dedupe":
        settings, train = h50k_settings() if name == "splink_historical_50k" else febrl_settings("dedupe_only")
        recs = c.left.rename(columns={"id": "unique_id"}).replace("", None)
        linker = Linker(db.register(recs), settings)
        t = c.truth.merge(c.truth, on="cluster")
        truth = set(map(tuple, t[t.id_x < t.id_y][["id_x", "id_y"]].to_numpy()))
    else:
        settings, train = febrl_settings("link_only", tuple({*drop, *(f for f in corpora.FEBRL_FIELDS if f not in c.fields)}))
        side = lambda df: df.rename(columns={"id": "unique_id"}).replace("", None)
        linker = Linker([db.register(side(c.left)), db.register(side(c.right))], settings)
        truth = set(map(tuple, c.truth[["l_id", "r_id"]].to_numpy()))
    linker.training.estimate_probability_two_random_records_match(train[:1], recall=0.7)
    linker.training.estimate_u_using_random_sampling(max_pairs=2e6)
    for rule in train:
        linker.training.estimate_parameters_using_expectation_maximisation(rule)
    pred = linker.inference.predict(threshold_match_probability=0.01).as_pandas_dataframe()
    wall = time.time() - t0
    a, b = pred["unique_id_l"].astype(str), pred["unique_id_r"].astype(str)
    if c.kind == "dedupe":
        a, b = np.minimum(a, b), np.maximum(a, b)
    pairs = pd.DataFrame({"l": a, "r": b, "p": pred["match_probability"]}).groupby(["l", "r"], as_index=False)["p"].max()
    hit = np.array([(x, y) in truth for x, y in zip(pairs.l, pairs.r)])

    def at(th):
        sel = pairs.p.to_numpy() >= th
        tp = int((sel & hit).sum())
        fp, fn = int(sel.sum()) - tp, len(truth) - tp
        return {"precision": round(tp / max(tp + fp, 1), 4), "recall": round(tp / max(len(truth), 1), 4),
                "f1": round(2 * tp / max(2 * tp + fp + fn, 1), 4), "threshold": th}
    bayes = at(0.5)
    oracle = max((at(th) for th in np.round(np.arange(0.05, 1.0, 0.05), 2)), key=lambda r: r["f1"])
    res = {**bayes, "oracle_best_threshold": oracle, "version": splink.__version__, "wall_s": round(wall, 1),
           "what": "unsupervised Fellegi-Sunter (DuckDB), pairwise over the whole corpus, p >= 0.5",
           "true_pairs": len(truth), "blocked_pairs_above_0.01": len(pairs)}
    logging.getLogger("bench").warning("%s: F1 %.4f (oracle %.4f) %.0f s", name, bayes["f1"], oracle["f1"], wall)
    return res


NAMES = ["febrl4_half_unmatched", "febrl4_half_unmatched_no_soc_sec_id", "febrl4_original", "febrl3",
         "splink_historical_50k", "synthetic_1e6"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)
    for noisy in ("splink", "splink.internals"):
        logging.getLogger(noisy).setLevel(logging.ERROR)
    res = json.loads(OUT.read_text()) if OUT.exists() else {}
    for n in (args.only.split(",") if args.only else NAMES):
        res[n] = run_one(n)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(res, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
