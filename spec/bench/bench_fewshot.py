#!/usr/bin/env python3
"""bench_fewshot.py — prompt-side ways to lift Jev, measured on the pairs already judged zero-shot.

Same test/valid pairs as bench_pairs.py (v0/v1 caches) and bench_bpid.py, so every number is comparable with the
zero-shot baseline. Demonstrations come from the TRAIN split only. Thresholds: VALID, frozen on TEST.

    zs      zero-shot baseline (read from the existing caches, never re-asked)
    r6/r20  6 / 20 random demonstrations, balanced, the same for every pair of a dataset
    k6/k10  6 / 10 RELATED demonstrations per pair: nearest train pairs by char-3-gram TF-IDF, half matches half not
            (Peeters et al., EDBT 2025: related demonstrations are the best choice for strong models)
    dec     decomposition (TypeSafe "composite scoring"): the holistic Score + attribute-level Nouls in ONE request;
            reported alone and stacked (logistic regression over every answer, fitted on VALID)

    $ZINGG_VENV/bin/python bench_fewshot.py run Structured_Amazon-Google r6 r20 k6 k10 dec
    $ZINGG_VENV/bin/python bench_fewshot.py run bpid r6 r20 k6 k10 dec
    $ZINGG_VENV/bin/python bench_fewshot.py report
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bench_bpid  # noqa: E402
import bench_cascade as bc  # noqa: E402
import bench_pairs as bp  # noqa: E402

CACHE = HERE / "cache"
SYSTEM_PY = "/opt/homebrew/bin/python3"
PRICE = 0.042 / 1_000_000          # USD per input token, jev-1.13.0 (docs.typesafe.ai/models, 2026-09-19); output is free


def clip(rec: dict) -> dict:
    return {k: ([x[:200] for x in v] if isinstance(v, list) else str(v)[:300]) for k, v in rec.items()}


def text(row: dict) -> str:
    flat = lambda r: " ".join(" ".join(v) if isinstance(v, list) else str(v) for v in r.values())  # noqa: E731
    return flat(row["a"]) + " || " + flat(row["b"])


def dataset(name: str) -> dict:
    """train rows, the valid/test rows already judged zero-shot, the base question and the attribute Nouls."""
    if name == "bpid":
        sp, have = bench_bpid.load(), bench_bpid.cached()
        noun = "person"
        instr = ["`record_a` and `record_b` are customer profiles of people, each with a full name, e-mail addresses, "
                 "phone numbers, postal addresses and a date of birth. How do they relate?",
                 "The same person often appears with the name in a different order, a nickname, initials or typos, with "
                 "dates written in different formats, and with different e-mail addresses, phones and postal addresses "
                 "over time. Members of one household share a family name, an address and sometimes a phone without "
                 "being the same person. An empty field is missing information, not a disagreement."]
        crit = ["They are two different people: the names or the dates of birth positively disagree.",
                "They could be the same person, but the fields shown do not settle it.", "They are one and the same person."]
        nouls = {"same_name": "Allowing for word order, nicknames, initials and typos, do the two `fullname` values name the same person?",
                 "same_dob": "Allowing for different date formats, do the two `dob` values give the same date of birth?",
                 "dob_conflict": "Do both records give a date of birth, and are the two dates clearly different dates?",
                 "shared_contact": "Do the two records share an e-mail address or a phone number, allowing for formatting?",
                 "same_address": "Do the two records share a postal address, allowing for abbreviations and word order?",
                 "given_conflict": "Do the two records show clearly different given names (not a nickname or initial of one another)?"}
        zs = {k: {"probs": v["probs"], "score": v["score"]} for k, v in have.items()}
    else:
        short = name.split("_", 1)[1]
        noun, what = bp.DOMAIN[short]
        sp = {s: bp.load(name, s) for s in ("train", "valid", "test")}
        have = bp.cached(CACHE / f"{name}.v1.jsonl")
        instr = [f"How do `record_a` and `record_b` relate? They are {what}.", {"identity_rule": bp.RULES[short]},
                 "An empty field is missing information, not a disagreement. Wording, formatting and price differences "
                 "between the two sources are expected and are not disagreements."]
        crit = [f"They describe two different {noun}s: some identifying attribute positively disagrees.",
                f"They could be the same {noun}, but the fields shown do not settle it.",
                f"They describe one and the same {noun}: the identifying attributes agree."]
        nouls = {"same_brand": "Do the two records come from the same brand, manufacturer or publisher (a missing brand on one side does not count against)?",
                 "same_model": "Do the two records carry the same model number, part number or exact product title?",
                 "model_conflict": "Do both records show a model number, version or edition, and are those clearly different?",
                 "variant_conflict": "Do the two records differ in a variant that makes them different products: version or year, edition, licence type or number of users, platform, capacity, size, colour or pack count?",
                 "same_line": "Do the two records belong to the same product line or family?"}
        zs = {k: v for k, v in have.items()}
    keep = lambda rows: [r for r in rows if r["key"] in zs]  # noqa: E731
    return {"train": sp["train"], "valid": keep(sp["valid"]), "test": keep(sp["test"]), "zs": zs, "noun": noun,
            "instr": instr, "crit": crit, "nouls": nouls}


def demos(ds: dict, variant: str, rows: list[dict]) -> dict[str, list[dict]]:
    n = int(variant[1:])
    verdict = lambda r: {"record_a": clip(r["a"]), "record_b": clip(r["b"]), "expert_verdict": "same" if r["y"] else "different"}  # noqa: E731
    pos, neg = [r for r in ds["train"] if r["y"]], [r for r in ds["train"] if not r["y"]]
    if variant[0] == "r":
        rng = random.Random(5)
        fixed = rng.sample(pos, n // 2) + rng.sample(neg, n - n // 2)
        rng.shuffle(fixed)
        fixed = [verdict(r) for r in fixed]
        return {r["key"]: fixed for r in rows}
    tf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 3), sublinear_tf=True, min_df=2)
    tf.fit([text(r) for r in ds["train"]])
    mq = tf.transform([text(r) for r in rows])
    out = {r["key"]: [] for r in rows}
    for group, k in ((pos, n // 2), (neg, n - n // 2)):
        sims = (mq @ tf.transform([text(r) for r in group]).T).toarray()
        for i, r in enumerate(rows):
            out[r["key"]] += [verdict(group[j]) for j in np.argsort(-sims[i])[:k]]
    for key in out:                                   # interleave so the classes do not arrive in two blocks
        random.Random(key).shuffle(out[key])
    return out


def run(name: str, variants: list[str]) -> None:
    ds = dataset(name)
    rows = ds["valid"] + ds["test"]
    print(f"{name}: {len(ds['train'])} train pairs for demonstrations, {len(ds['valid'])} valid + {len(ds['test'])} test to judge")
    for variant in variants:
        path = CACHE / f"fs.{name}.{variant}.jsonl"
        have = {j["id"] for j in map(json.loads, path.read_text().splitlines())} if path.exists() else set()
        todo = [r for r in rows if r["key"] not in have]
        if not todo:
            continue
        score = {"type": "score", "instructions": list(ds["instr"]), "criteria": ds["crit"]}
        if variant == "dec":
            qs = {"relation": score, **{k: {"type": "noul", "instructions": v} for k, v in ds["nouls"].items()}}
            jobs = [{"id": r["key"], "state": {"record_a": r["a"], "record_b": r["b"]}, "questions": qs} for r in todo]
        else:
            ex = demos(ds, variant, todo)
            score["instructions"] = score["instructions"] + [
                f"`examples` are pairs from the same sources with an expert's verdict. Use them to calibrate where the "
                f"line between the same {ds['noun']} and a different one lies, then judge `record_a` against `record_b`."]
            jobs = [{"id": r["key"], "state": {"examples": ex[r["key"]], "record_a": r["a"], "record_b": r["b"]},
                     "questions": {"relation": score}} for r in todo]
        tmp = CACHE / f".jobs.{name}.{variant}.jsonl"
        tmp.write_text("\n".join(json.dumps(j) for j in jobs), encoding="utf-8")
        res = subprocess.run([SYSTEM_PY, str(HERE / "jev_worker.py"), str(tmp), str(path), f"fs:{name}:{variant}"],
                             capture_output=True, text=True)
        tmp.unlink()
        print(f"  {variant:<4} {res.stdout.strip() or res.stderr[-400:]}")


def usage() -> dict[str, dict]:
    led: dict[str, dict] = {}
    path = CACHE / "usage.jsonl"
    for j in map(json.loads, path.read_text().splitlines()) if path.exists() else []:
        u = led.setdefault(j["tag"], {"in": 0, "req": 0})
        u["in"] += j["in"]; u["req"] += j["req"]
    return led


def report() -> None:
    led = usage()
    names = sorted({p.name.split(".")[1] for p in CACHE.glob("fs.*.jsonl")})
    for name in names:
        ds = dataset(name)
        yv, yt = np.array([r["y"] for r in ds["valid"]]), np.array([r["y"] for r in ds["test"]])
        print(f"\n{name}: {len(ds['test'])} test pairs ({int(yt.sum())} matches), thresholds from {len(ds['valid'])} valid pairs")
        print(f"  {'variant':<34}{'P':>7}{'R':>7}{'F1':>7}{'tokens/pair':>13}{'$ / 1 000 pairs':>17}")
        def line(label, pv, pt, tok):
            p, r, f = bc.f1_at(pt, yt, bc.tune(pv, yv))
            print(f"  {label:<34}{p:>7.3f}{r:>7.3f}{f:>7.3f}{tok:>13.0f}{1000 * tok * PRICE:>17.4f}")
        zs = ds["zs"]
        zv, zt = np.array([zs[r["key"]]["probs"][2] for r in ds["valid"]]), np.array([zs[r["key"]]["probs"][2] for r in ds["test"]])
        line("zs   zero-shot baseline", zv, zt, float("nan"))
        for path in sorted(CACHE.glob(f"fs.{name}.*.jsonl")):
            variant = path.name.split(".")[2]
            got = {j["id"]: j["answers"] for j in map(json.loads, path.read_text().splitlines())}
            if any(r["key"] not in got for r in ds["valid"] + ds["test"]):
                print(f"  {variant:<34} incomplete"); continue
            u = led.get(f"fs:{name}:{variant}", {"in": 0, "req": 1})
            tok = u["in"] / max(u["req"], 1)
            ps = lambda rows: np.array([got[r["key"]]["relation"]["probs"][2] for r in rows])  # noqa: E731
            label = {"r": "random demonstrations", "k": "related demonstrations"}.get(variant[0], "decomposed, holistic Score only")
            line(f"{variant:<4} {label}", ps(ds["valid"]), ps(ds["test"]), tok)
            if variant == "dec":
                feats = lambda rows: np.array([got[r["key"]]["relation"]["probs"] + [got[r["key"]][q]["noul"] for q in ds["nouls"]] for r in rows])  # noqa: E731
                lr = LogisticRegression(max_iter=2000, C=1.0)
                cv = cross_val_predict(lr, feats(ds["valid"]), yv, cv=5, method="predict_proba")[:, 1]
                pt = lr.fit(feats(ds["valid"]), yv).predict_proba(feats(ds["test"]))[:, 1]
                p, r, f = bc.f1_at(pt, yt, bc.tune(cv, yv))
                print(f"  {'dec  + attribute Nouls, stacked':<34}{p:>7.3f}{r:>7.3f}{f:>7.3f}{tok:>13.0f}{1000 * tok * PRICE:>17.4f}")
                w = dict(zip(["p_diff", "p_unsure", "p_same"] + list(ds["nouls"]), lr.coef_[0].round(2)))
                print(f"       weights: {w}")


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2], sys.argv[3:])
    else:
        report()
