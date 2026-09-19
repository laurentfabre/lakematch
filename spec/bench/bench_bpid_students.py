#!/usr/bin/env python3
"""bench_bpid_students.py — can Jev be distilled into the feature-based matcher on ambiguous person data? (README, E)

Saved after the independent review noted these figures had no script. Students are gradient-boosted models over
bench_bpid.feats(); "Jev labels" come from the 600 TRAIN + 300 VALID pairs Jev judged zero-shot. Student thresholds
are tuned against JEV's own labels on VALID (no human label anywhere); the gold references use gold VALID labels.

    $ZINGG_VENV/bin/python bench_bpid_students.py
"""
import numpy as np
import bench_bpid as b, bench_cascade as bc
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor

sp, have = b.load(), b.cached()
X = lambda rows: np.array([b.feats(r) for r in rows]); Y = lambda rows: np.array([r["y"] for r in rows])
J = lambda rows: np.array([have[r["key"]]["probs"] + [have[r["key"]]["score"] / 2] for r in rows])
tr, va, te = ([r for r in sp[s] if r["key"] in have] for s in ("train", "valid", "test"))
jt, jv, yte = J(tr), J(va), Y(te)
print(f"Jev judged: train {len(tr)} valid {len(va)} test {len(te)}; Jev hard-label accuracy on train: {((jt[:, 2] >= 0.5).astype(int) == Y(tr)).mean():.3f}")
def show(name, p_te, p_va, yv):
    P, R, F = bc.f1_at(p_te, yte, bc.tune(p_va, yv)); print(f"  {name:<66} P {P:.3f} R {R:.3f} F1 {F:.3f}")
jv_hard = (jv[:, 2] >= 0.5).astype(int)
for tau in (0.9, 0.8, 0.7):
    k = (jt[:, 0] >= tau) | (jt[:, 2] >= tau); lab = (jt[:, 2] >= tau).astype(int)[k]
    g = GradientBoostingClassifier(n_estimators=200, max_depth=3, random_state=0).fit(X(tr)[k], lab)
    show(f"student on Jev-confident labels, tau {tau} ({k.sum()} labels, {(lab != Y(tr)[k]).sum()} wrong)", g.predict_proba(X(te))[:, 1], g.predict_proba(X(va))[:, 1], jv_hard)
g = GradientBoostingClassifier(n_estimators=200, max_depth=3, random_state=0).fit(np.vstack([X(tr), X(va)]), np.r_[(jt[:, 2] >= 0.5).astype(int), jv_hard])
show(f"student on ALL {len(tr) + len(va)} Jev hard labels (noisy)", g.predict_proba(X(te))[:, 1], g.predict_proba(X(va))[:, 1], jv_hard)
r = GradientBoostingRegressor(n_estimators=200, max_depth=3, random_state=0).fit(np.vstack([X(tr), X(va)]), np.r_[jt[:, 3], jv[:, 3]])
show("student distilled on Jev's soft score (regression)", r.predict(X(te)), r.predict(X(va)), jv_hard)
for n in (100, 300, 900):
    gg = GradientBoostingClassifier(n_estimators=200, max_depth=3, random_state=0).fit(X(sp["train"][:n]), Y(sp["train"][:n]))
    show(f"reference: student on {n} GOLD labels", gg.predict_proba(X(te))[:, 1], gg.predict_proba(X(va))[:, 1], Y(va))
