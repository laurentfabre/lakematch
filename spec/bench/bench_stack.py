#!/usr/bin/env python3
"""bench_stack.py — the best system per dataset: a logistic regression over every signal already cached.

    classical   similarity features + gradient boosting, trained on the gold TRAIN split (the Zingg/Magellan family)
    zs          Jev zero-shot: the three Score probabilities
    dec         Jev attribute-level Nouls (decomposition)
    k10         Jev P(same) with 10 related demonstrations

The stacker is fitted on VALID (its threshold by 5-fold cross-validation on VALID) and frozen on TEST. Costs are the
Jev input tokens a production pair would need for the signals used (measured, cache/usage.jsonl), at $0.042 / Mtok.

    $ZINGG_VENV/bin/python bench_stack.py
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bench_bpid  # noqa: E402
import bench_cascade as bc  # noqa: E402
import bench_fewshot as fs  # noqa: E402

ZS_TOKENS = {"Structured_Amazon-Google": 552, "Structured_Walmart-Amazon": 597, "Textual_Abt-Buy": 637, "bpid": 660}  # measured, v1 / people runs


def main() -> int:
    led = fs.usage()
    print(f"{'dataset':<27}{'signals':<34}{'P':>7}{'R':>7}{'F1':>7}{'Jev tok/pair':>14}{'$ / 1 000 pairs':>17}")
    for name in ("Structured_Amazon-Google", "Structured_Walmart-Amazon", "Textual_Abt-Buy", "bpid"):
        ds = fs.dataset(name)
        va, te = ds["valid"], ds["test"]
        yv, yt = np.array([r["y"] for r in va]), np.array([r["y"] for r in te])
        if name == "bpid":
            X = lambda rows: np.array([bench_bpid.feats(r) for r in rows])  # noqa: E731
        else:
            tf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 3), sublinear_tf=True, min_df=2)
            tf.fit([" ".join(r[s].values()) for r in ds["train"] for s in ("a", "b")])
            X = lambda rows: bc.features(rows, tf)  # noqa: E731
        gb = GradientBoostingClassifier(n_estimators=200, max_depth=3, random_state=0).fit(X(ds["train"]), np.array([r["y"] for r in ds["train"]]))
        got = {v: {j["id"]: j["answers"] for j in map(json.loads, (fs.CACHE / f"fs.{name}.{v}.jsonl").read_text().splitlines())} for v in ("dec", "k10")}
        sig = {
            "classical": lambda rows: gb.predict_proba(X(rows))[:, 1][:, None],
            "zs": lambda rows: np.array([ds["zs"][r["key"]]["probs"] for r in rows]),
            "dec": lambda rows: np.array([[got["dec"][r["key"]][q]["noul"] for q in ds["nouls"]] for r in rows]),
            "k10": lambda rows: np.array([got["k10"][r["key"]]["relation"]["probs"] for r in rows]),
        }
        cache = {k: (f(va), f(te)) for k, f in sig.items()}
        tok = {"classical": 0, "zs": ZS_TOKENS[name], "k10": led[f"fs:{name}:k10"]["in"] / led[f"fs:{name}:k10"]["req"],
               "dec": led[f"fs:{name}:dec"]["in"] / led[f"fs:{name}:dec"]["req"]}
        rows_out = []
        for n in range(1, 5):
            for combo in itertools.combinations(sig, n):
                if "dec" in combo and "zs" in combo:
                    cost = tok["dec"] + sum(tok[c] for c in combo if c not in ("dec", "zs"))   # dec's request carries the zero-shot Score too
                else:
                    cost = sum(tok[c] for c in combo)
                fv, ft = np.hstack([cache[c][0] for c in combo]), np.hstack([cache[c][1] for c in combo])
                lr = LogisticRegression(max_iter=3000, C=1.0)
                cv = cross_val_predict(lr, fv, yv, cv=5, method="predict_proba")[:, 1]
                p, r, f = bc.f1_at(lr.fit(fv, yv).predict_proba(ft)[:, 1], yt, bc.tune(cv, yv))
                rows_out.append((f, p, r, " + ".join(combo), cost))
        keep = {"classical", "zs", "classical + zs", "zs + dec", "classical + zs + dec", "classical + k10", "classical + zs + dec + k10"}
        best = max(rows_out)[3]
        for f, p, r, combo, cost in sorted(rows_out, key=lambda t: t[4]):
            if combo in keep or combo == best:
                print(f"{name:<27}{combo:<34}{p:>7.3f}{r:>7.3f}{f:>7.3f}{cost:>14.0f}{1000 * cost * fs.PRICE:>17.4f}{'   <- best' if combo == best else ''}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
