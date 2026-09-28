#!/usr/bin/env python3
"""synthetic_1e6: 10^6 generated person records for the scale row of BENCHMARKS.md (500 000 left, 500 000 right).

Half the left records have a corrupted partner on the right (250 000 true links); the other 250 000 right records are
fresh people, so the matcher must reject as often as it links, like FEBRL4-half-unmatched. Values are drawn with
their real frequencies from the FEBRL3/FEBRL4 and Splink historical_50k vocabularies, so frequent names and suburbs
are skewed the way real data is (the candidate step's gram cap and budget are what this row tests).

Corruptions per duplicate (each independently): a typo in a name or the street (insert, delete, substitute,
transpose), a missing field, given name and surname swapped, one digit of the date of birth or postcode changed.
Seeded: the same files every time. Written once to data/synthetic/ (Parquet, gitignored).

    python bench/synthetic.py [--n 500000]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data" / "synthetic"
FIELDS = {"given_name": {"type": "person_name"}, "surname": {"type": "person_name"},
          "street_number": {"type": "code"}, "address_1": {"type": "address"}, "suburb": {"type": "address"},
          "postcode": {"type": "code"}, "state": {"type": "code"}, "date_of_birth": {"type": "date"}}
SEED = 1_000_000
LETTERS = np.array(list("abcdefghijklmnopqrstuvwxyz"))


def _vocab() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """value -> probability, per field, from the public corpora (their empirical frequencies)."""
    from recordlinkage.datasets import load_febrl3, load_febrl4
    a, b = load_febrl4()
    frames = [load_febrl3(), a, b]
    try:
        h = pd.read_parquet(Path(__file__).resolve().parent.parent / "data" / "splink" / "historical_50k.parquet")
        frames.append(h.rename(columns={"first_name": "given_name", "birth_place": "suburb"})[["given_name", "surname", "suburb"]])
    except FileNotFoundError:
        pass
    df = pd.concat(frames, ignore_index=True)
    out = {}
    for f in ("given_name", "surname", "address_1", "suburb", "state"):
        vc = df[f].dropna().astype(str).str.strip()
        vc = vc[vc.str.len() > 1].value_counts()
        out[f] = (vc.index.to_numpy(), (vc / vc.sum()).to_numpy())
    return out


def _typo(rng: np.random.Generator, s: str) -> str:
    if len(s) < 2:
        return s
    i = int(rng.integers(0, len(s) - 1))
    k = int(rng.integers(0, 4))
    c = str(LETTERS[rng.integers(0, 26)])
    if k == 0:
        return s[:i] + c + s[i:]
    if k == 1:
        return s[:i] + s[i + 1:]
    if k == 2:
        return s[:i] + c + s[i + 1:]
    return s[:i] + s[i + 1] + s[i] + s[i + 2:]


def _digit(rng: np.random.Generator, s: str) -> str:
    if not s:
        return s
    i = int(rng.integers(0, len(s)))
    return s[:i] + str(int(rng.integers(0, 10))) + s[i + 1:]


def people(rng: np.random.Generator, vocab, n: int, prefix: str) -> pd.DataFrame:
    draw = lambda f: rng.choice(vocab[f][0], size=n, p=vocab[f][1])
    dob = pd.to_datetime("1920-01-01") + pd.to_timedelta(rng.integers(0, 80 * 365, size=n), unit="D")
    return pd.DataFrame({
        "id": [f"{prefix}{i:07d}" for i in range(n)],
        "given_name": draw("given_name"), "surname": draw("surname"),
        "street_number": rng.integers(1, 400, size=n).astype(str),
        "address_1": draw("address_1"), "suburb": draw("suburb"),
        "postcode": rng.integers(2000, 7999, size=n).astype(str), "state": draw("state"),
        "date_of_birth": dob.strftime("%Y%m%d")})


def corrupt(rng: np.random.Generator, rows: pd.DataFrame) -> pd.DataFrame:
    out = rows.copy()
    recs = out.to_dict("records")
    for r in recs:
        for f in ("given_name", "surname", "address_1"):
            if rng.random() < 0.35:
                r[f] = _typo(rng, r[f])
        if rng.random() < 0.10:
            r["given_name"], r["surname"] = r["surname"], r["given_name"]
        if rng.random() < 0.15:
            r["date_of_birth"] = _digit(rng, r["date_of_birth"])
        if rng.random() < 0.10:
            r["postcode"] = _digit(rng, r["postcode"])
        for f in ("given_name", "street_number", "address_1", "suburb", "date_of_birth"):
            if rng.random() < 0.05:
                r[f] = ""
    return pd.DataFrame(recs, columns=out.columns)


def generate(n: int) -> None:
    rng = np.random.default_rng(SEED)
    vocab = _vocab()
    left = people(rng, vocab, n, "L")
    partnered = left.iloc[: n // 2]
    dup = corrupt(rng, partnered)
    dup["id"] = partnered["id"].to_numpy()          # temporary: the left id it copies
    fresh = people(rng, vocab, n - len(dup), "N")
    fresh["id"] = ""
    right = pd.concat([dup, fresh], ignore_index=True).sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    source = right["id"].to_numpy()
    right["id"] = [f"R{i:07d}" for i in range(len(right))]   # ids carry no hint of which rows are duplicates
    keep = source != ""
    truth = pd.DataFrame({"l_id": source[keep], "r_id": right["id"].to_numpy()[keep]})
    DATA.mkdir(parents=True, exist_ok=True)
    left.to_parquet(DATA / "left.parquet", index=False)
    right.to_parquet(DATA / "right.parquet", index=False)
    truth.to_parquet(DATA / "truth.parquet", index=False)
    print(f"left {len(left)} · right {len(right)} · true links {len(truth)} -> {DATA}")


def load():
    import corpora
    if not (DATA / "truth.parquet").exists():
        generate(500_000)
    read = lambda n: pd.read_parquet(DATA / f"{n}.parquet")
    return corpora.Corpus("synthetic_1e6", "linkage", dict(FIELDS), read("left"), read("right"), truth=read("truth"),
                          notes=["10^6 generated records (500 000 per side), 250 000 true links, seed 1000000"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500_000, help="records per side")
    generate(ap.parse_args().n)
