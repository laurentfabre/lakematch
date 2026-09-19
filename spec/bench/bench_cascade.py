#!/usr/bin/env python3
"""bench_cascade.py — what Jev adds to a Zingg-class matcher, measured on the cached judgments of bench_pairs.py.

A "Zingg-class" matcher = per-field string-similarity features + a classical classifier (the Magellan family; Zingg's
classifier is logistic regression over such features). It is trained on each benchmark's TRAIN split (gold labels,
free), so this file spends no tokens: every Jev number comes from bench/cache/.

Compared on the same TEST pairs (those Jev has judged), thresholds and bands always chosen on VALID:
    cheap      the classical matcher alone                                   (what Zingg alone can do)
    jev        Jev zero-shot alone
    cascade    cheap decides outside [lo, hi]; Jev decides inside            (cost = share of pairs sent to Jev)
    stack      a second classifier over the similarity features + Jev's probabilities, trained on VALID

    $ZINGG_VENV/bin/python bench_cascade.py [--variant v0]
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bench_pairs as bp  # noqa: E402

TOKEN = re.compile(r"[a-z0-9]+")


def toks(text: str) -> set[str]:
    return set(TOKEN.findall(text.lower()))


def num(text: str) -> float | None:
    m = re.search(r"\d+(?:\.\d+)?", text.replace(",", ""))
    return float(m.group()) if m else None


def features(rows: list[dict], tfidf: TfidfVectorizer) -> np.ndarray:
    cols = sorted({k for r in rows[:50] for k in list(r["a"]) + list(r["b"])})
    whole_a = [" ".join(r["a"].values()) for r in rows]
    whole_b = [" ".join(r["b"].values()) for r in rows]
    ma, mb = tfidf.transform(whole_a), tfidf.transform(whole_b)
    cosine = np.asarray(ma.multiply(mb).sum(axis=1)).ravel()
    out = []
    for i, r in enumerate(rows):
        f = [cosine[i]]
        ta, tb = toks(whole_a[i]), toks(whole_b[i])
        f.append(len(ta & tb) / max(len(ta | tb), 1))
        # model-number-like tokens (letters+digits) are the strongest product evidence
        ca, cb = {t for t in ta if re.search(r"\d", t) and len(t) > 3}, {t for t in tb if re.search(r"\d", t) and len(t) > 3}
        f += [len(ca & cb), float(bool(ca and cb and not ca & cb))]
        for c in cols:
            a, b = r["a"].get(c, ""), r["b"].get(c, "")
            if not a or not b:
                f += [-1.0, -1.0, -1.0, 1.0]
                continue
            sa, sb = toks(a), toks(b)
            na, nb = num(a), num(b)
            f += [len(sa & sb) / max(len(sa | sb), 1),
                  difflib.SequenceMatcher(None, a[:120].lower(), b[:120].lower()).ratio(),
                  (1 - min(abs(na - nb) / max(abs(na), abs(nb), 1e-9), 1.0)) if na is not None and nb is not None else -1.0,
                  0.0]
        out.append(f)
    return np.array(out)


def f1_at(p: np.ndarray, y: np.ndarray, tau: float) -> tuple[float, float, float]:
    pred = p >= tau
    tp, fp, fn = int((pred & (y == 1)).sum()), int((pred & (y == 0)).sum()), int((~pred & (y == 1)).sum())
    pr, rc = (tp / (tp + fp) if tp + fp else 0.0), (tp / (tp + fn) if tp + fn else 0.0)
    return pr, rc, (2 * pr * rc / (pr + rc) if pr + rc else 0.0)


def tune(p: np.ndarray, y: np.ndarray) -> float:
    grid = np.arange(5, 100, 5) / 100          # exact hundredths: np.arange(0.05, 1, 0.05) yields 0.30000000000000004
    return float(max(grid, key=lambda t: f1_at(p, y, t)[2]))


def jev_stats(rows, have) -> np.ndarray:
    out = []
    for r in rows:
        j = have[r["key"]]
        out.append(j["probs"] + [j["score"] / 2] if "probs" in j else [1 - j["noul"], 0.0, j["noul"], j["noul"]])
    return np.array(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="v0")
    args = ap.parse_args()
    print(f"{'dataset':<27}{'n':>5}{'pos':>5} | {'cheap':>6} {'jev':>6} {'cascade':>8} {'(to Jev)':>9} {'stack':>6} | "
          f"{'cascade P':>9} {'R':>6} | {'stack P':>8} {'R':>6}")
    for path in sorted(bp.CACHE.glob(f"*.{args.variant}.jsonl")):
        dataset = path.name[:-6].rsplit(".", 1)[0]
        have = bp.cached(path)
        train = bp.load(dataset, "train")
        valid = [r for r in bp.load(dataset, "valid") if r["key"] in have]
        test = [r for r in bp.load(dataset, "test") if r["key"] in have]
        if len(valid) < 50 or len(test) < 50:
            continue
        tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 3), sublinear_tf=True, min_df=2)
        tfidf.fit([" ".join(r[s].values()) for r in train for s in ("a", "b")])
        xtr, ytr = features(train, tfidf), np.array([r["y"] for r in train])
        xva, yva = features(valid, tfidf), np.array([r["y"] for r in valid])
        xte, yte = features(test, tfidf), np.array([r["y"] for r in test])

        cheap = GradientBoostingClassifier(n_estimators=200, max_depth=3, random_state=0).fit(xtr, ytr)
        pva, pte = cheap.predict_proba(xva)[:, 1], cheap.predict_proba(xte)[:, 1]
        f_cheap = f1_at(pte, yte, tune(pva, yva))[2]

        jva, jte = jev_stats(valid, have), jev_stats(test, have)
        t_jev = tune(jva[:, 3], yva)
        f_jev = f1_at(jte[:, 3], yte, t_jev)[2]

        # cascade: the band [lo, hi] of the cheap score that, on VALID, gives the best F1 when Jev decides inside it
        best = (-1.0, 0.0, 1.0)
        for lo in (0.01, 0.02, 0.05, 0.1, 0.2, 0.3):
            for hi in (0.5, 0.7, 0.8, 0.9, 0.95, 0.99):
                inside = (pva >= lo) & (pva <= hi)
                dec = np.where(inside, jva[:, 3] >= t_jev, pva > hi).astype(float)
                score = f1_at(dec, yva, 0.5)[2] - 0.02 * inside.mean()      # a mild price on Jev calls
                if score > best[0]:
                    best = (score, lo, hi)
        _, lo, hi = best
        inside = (pte >= lo) & (pte <= hi)
        dec = np.where(inside, jte[:, 3] >= t_jev, pte > hi).astype(float)
        cp, cr, f_casc = f1_at(dec, yte, 0.5)

        # stack: similarity features + Jev's distribution, learnt on VALID only (cross-validated to set its threshold)
        sva, ste = np.hstack([pva[:, None], jva]), np.hstack([pte[:, None], jte])
        stack = LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced")
        t_stack = tune(cross_val_predict(stack, sva, yva, cv=5, method="predict_proba")[:, 1], yva)
        sp, sr, f_stack = f1_at(stack.fit(sva, yva).predict_proba(ste)[:, 1], yte, t_stack)

        print(f"{dataset:<27}{len(test):>5}{int(yte.sum()):>5} | {f_cheap:>6.3f} {f_jev:>6.3f} {f_casc:>8.3f} "
              f"{100 * inside.mean():>8.0f}% {f_stack:>6.3f} | {cp:>9.3f} {cr:>6.3f} | {sp:>8.3f} {sr:>6.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
