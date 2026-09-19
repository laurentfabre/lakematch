#!/usr/bin/env python3
"""bench_stats.py — how solid are the headline comparisons? No tokens spent: everything comes from the caches.

1. Selection bias. bench_stack.py reports the best of 15 signal combinations BY TEST F1. Here the combination is
   chosen on VALID only (5-fold cross-validated F1), and that single choice is then scored on TEST.
2. Paired bootstrap (2 000 resamples of the test pairs) for the key comparisons: 95 % interval of the F1 difference
   and the share of resamples in which the second method wins.

    $ZINGG_VENV/bin/python bench_stats.py
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

RNG = np.random.default_rng(17)


def f1(pred: np.ndarray, y: np.ndarray) -> float:
    tp = int((pred & (y == 1)).sum()); fp = int((pred & (y == 0)).sum()); fn = int((~pred & (y == 1)).sum())
    return 2 * tp / (2 * tp + fp + fn) if tp else 0.0


def boot(pa: np.ndarray, pb: np.ndarray, y: np.ndarray, n: int = 2000) -> tuple[float, float, float, float, float]:
    idx = RNG.integers(0, len(y), size=(n, len(y)))
    fa = np.array([f1(pa[i], y[i]) for i in idx]); fb = np.array([f1(pb[i], y[i]) for i in idx])
    d = fb - fa
    return (*np.percentile(fa, [2.5, 97.5]), *np.percentile(d, [2.5, 97.5]), float((d > 0).mean()))  # type: ignore[return-value]


def main() -> int:
    print(f"{'dataset':<26}{'comparison':<44}{'F1 a':>7}{'F1 b':>7}{'diff':>8}{'95 % CI of diff':>20}{'P(b>a)':>8}")
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
        sig = {"classical": lambda rows: gb.predict_proba(X(rows))[:, 1][:, None],
               "zs": lambda rows: np.array([ds["zs"][r["key"]]["probs"] for r in rows]),
               "dec": lambda rows: np.array([[got["dec"][r["key"]][q]["noul"] for q in ds["nouls"]] for r in rows]),
               "k10": lambda rows: np.array([got["k10"][r["key"]]["relation"]["probs"] for r in rows])}
        cache = {k: (f(va), f(te)) for k, f in sig.items()}

        def single(v_scores, t_scores):
            return t_scores >= bc.tune(v_scores, yv)
        zs_pred = single(cache["zs"][0][:, 2], cache["zs"][1][:, 2])
        k10_pred = single(cache["k10"][0][:, 2], cache["k10"][1][:, 2])
        cl_pred = single(cache["classical"][0][:, 0], cache["classical"][1][:, 0])

        best_valid, chosen, test_best = -1.0, None, (-1.0, None)
        preds = {}
        for n in range(1, 5):
            for combo in itertools.combinations(sig, n):
                fv, ft = np.hstack([cache[c][0] for c in combo]), np.hstack([cache[c][1] for c in combo])
                lr = LogisticRegression(max_iter=3000, C=1.0)
                cv = cross_val_predict(lr, fv, yv, cv=5, method="predict_proba")[:, 1]
                tau = bc.tune(cv, yv)
                vf = bc.f1_at(cv, yv, tau)[2]
                preds[combo] = lr.fit(fv, yv).predict_proba(ft)[:, 1] >= tau
                if vf > best_valid:
                    best_valid, chosen = vf, combo
                tf1 = f1(preds[combo], yt)
                if tf1 > test_best[0]:
                    test_best = (tf1, combo)
        honest = preds[chosen]
        print(f"{name:<26}chosen on VALID: {' + '.join(chosen)} (valid CV F1 {best_valid:.3f}) -> TEST F1 {f1(honest, yt):.3f}   "
              f"| best-by-TEST was {' + '.join(test_best[1])} {test_best[0]:.3f}  => optimism {test_best[0] - f1(honest, yt):+.3f}")
        for label, a, b in (("zero-shot  ->  10 related demos", zs_pred, k10_pred),
                            ("zero-shot  ->  stack chosen on VALID", zs_pred, honest),
                            ("classifier ->  zero-shot", cl_pred, zs_pred),
                            ("classifier ->  stack chosen on VALID", cl_pred, honest)):
            la, ha, ld, hd, pw = boot(a, b, yt)
            print(f"{'':<26}{label:<44}{f1(a, yt):>7.3f}{f1(b, yt):>7.3f}{f1(b, yt) - f1(a, yt):>+8.3f}{f'[{ld:+.3f}, {hd:+.3f}]':>20}{pw:>8.2f}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
