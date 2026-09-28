"""Benchmark corpora: fetched on first use into data/<name>/ (gitignored), then read offline.

Every loader returns a Corpus: two record tables (pandas) with an `id` column, the entity fields and their types,
and either labelled pairs with a fixed split (pair corpora) or a truth set of links (linkage corpora).

| name                    | kind     | source                                                                         | licence            |
|-------------------------|----------|--------------------------------------------------------------------------------|--------------------|
| febrl4_half_unmatched   | linkage  | FEBRL4 inside `recordlinkage`, half the partners removed (bench/prepare_febrl4.py) | FEBRL (ANU), BSD-3 package |
| bpid                    | pairs    | Amazon BPID, EMNLP 2024 Industry — zenodo.org/records/13932202                 | Apache-2.0         |
| abt_buy                 | pairs    | Magellan Abt-Buy, Ditto's fixed splits — github.com/megagonlabs/ditto          | research benchmark |
| leipzig_affiliations    | dedupe   | Leipzig ER benchmark "Affiliations" — dbs.uni-leipzig.de benchmark datasets    | research benchmark |
| febrl4_original         | linkage  | FEBRL4 inside `recordlinkage`, every partner kept                              | FEBRL (ANU), BSD-3 package |
| febrl3                  | dedupe   | FEBRL3 inside `recordlinkage`: 5 000 records, clusters up to 6                 | FEBRL (ANU), BSD-3 package |
| amazon_google           | pairs    | Magellan Amazon-Google (structured), Ditto's fixed splits                      | research benchmark |
| walmart_amazon          | pairs    | Magellan Walmart-Amazon (structured), Ditto's fixed splits                     | research benchmark |
| dblp_acm                | pairs    | Magellan DBLP-ACM (structured), Ditto's fixed splits                           | research benchmark |
| splink_historical_50k   | dedupe   | Splink demo data, github.com/moj-analytical-services/splink_datasets           | Wikidata-derived demo data (licence: see that repo) |
| synthetic_1e6           | linkage  | bench/synthetic.py: 10^6 generated person records (500 000 per side), seeded   | generated here     |

BPID ships without a split: pairs are assigned by a hash of the raw line (70 % train / 10 % valid / 20 % test), the
same rule as the 2026-09-19 measurements. Leipzig pairs come from the candidate step (dedupe mode) and are split by a
hash of the pair (60 / 20 / 20); labels come from the gold clusters.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
DITTO = "https://raw.githubusercontent.com/megagonlabs/ditto/master/data/er_magellan/Textual/Abt-Buy/{split}.txt"
BPID_URL = "https://zenodo.org/records/13932202/files/BPID.zip?download=1"
LEIPZIG_URL = "https://dbs.uni-leipzig.de/files/datasets/affiliationstrings.zip"


@dataclass
class Corpus:
    name: str
    kind: str                                   # pairs | linkage | dedupe
    fields: dict[str, dict]
    left: pd.DataFrame
    right: pd.DataFrame
    pairs: pd.DataFrame | None = None           # l_id, r_id, label, split   (pair corpora)
    truth: pd.DataFrame | None = None           # l_id, r_id                 (linkage / dedupe)
    notes: list[str] = field(default_factory=list)


def _fetch(url: str, dest: Path) -> Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=120) as r:
            dest.write_bytes(r.read())
    return dest


def _bucket(key: str, mod: int) -> int:
    return int(hashlib.sha1(key.encode()).hexdigest()[:8], 16) % mod


# --- FEBRL4 --------------------------------------------------------------------------------------------------------
FEBRL_FIELDS = {"given_name": {"type": "person_name"}, "surname": {"type": "person_name"},
                "street_number": {"type": "code"}, "address_1": {"type": "address"}, "address_2": {"type": "address"},
                "suburb": {"type": "address"}, "postcode": {"type": "code"}, "state": {"type": "code"},
                "date_of_birth": {"type": "date"}, "soc_sec_id": {"type": "code"}}


def febrl4_half_unmatched(drop: tuple[str, ...] = ()) -> Corpus:
    d = DATA / "febrl4"
    if not (d / "left.csv").exists():
        raise FileNotFoundError("data/febrl4 missing — run: python bench/prepare_febrl4.py")
    read = lambda n: pd.read_csv(d / f"{n}.csv", dtype=str, keep_default_na=False).rename(columns={"rec_id": "id"})
    fields = {k: v for k, v in FEBRL_FIELDS.items() if k not in drop}
    name = "febrl4_half_unmatched" + ("_" + "_".join(f"no_{x}" for x in drop) if drop else "")
    truth = pd.read_csv(d / "truth.csv", dtype=str)
    return Corpus(name, "linkage", fields, read("left")[["id", *fields]], read("right")[["id", *fields]], truth=truth)


# --- BPID ----------------------------------------------------------------------------------------------------------
BPID_FIELDS = {"fullname": {"type": "person_name"}, "email": {"type": "code", "multi": True},
               "phone": {"type": "code", "multi": True}, "addr": {"type": "address"}, "dob": {"type": "date"}}


def bpid() -> Corpus:
    d = DATA / "bpid"
    jsonl = d / "matching_dataset.jsonl"
    if not jsonl.exists():
        z = _fetch(BPID_URL, d / "BPID.zip")
        with zipfile.ZipFile(z) as zf:
            member = next(n for n in zf.namelist() if n.endswith("matching_dataset.jsonl"))
            jsonl.write_bytes(zf.read(member))
    flat = lambda p, i: {"id": i, "fullname": p["fullname"], "email": " | ".join(p["email"]),
                         "phone": " | ".join(p["phone"]), "addr": " , ".join(p["addr"]), "dob": p["dob"]}
    left, right, pairs = [], [], []
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        j = json.loads(line)
        key = hashlib.sha1(line.encode()).hexdigest()[:16]
        b = int(key[:4], 16) % 10
        split = "train" if b < 7 else "valid" if b == 7 else "test"
        left.append(flat(j["profile1"], key + "a"))
        right.append(flat(j["profile2"], key + "b"))
        pairs.append({"l_id": key + "a", "r_id": key + "b", "label": float(j["match"] == "True"), "split": split})
    dedup = lambda rows: pd.DataFrame(rows).drop_duplicates("id")
    return Corpus("bpid", "pairs", BPID_FIELDS, dedup(left), dedup(right),
                  pairs=pd.DataFrame(pairs).drop_duplicates(["l_id", "r_id"]))


# --- Abt-Buy (Ditto splits) ----------------------------------------------------------------------------------------
ABT_FIELDS = {"name": {"type": "title"}, "description": {"type": "title"}, "price": {"type": "number"}}


def _ditto_record(text: str) -> dict:
    out = {}
    for part in re.split(r"\bCOL ", text):
        if " VAL" in part:
            key, _, val = part.partition(" VAL")
            out[key.strip()] = re.sub(r"\s+", " ", val.replace("`", "").strip(" '")).strip()
    return out


def abt_buy() -> Corpus:
    d = DATA / "abt_buy"
    left, right, pairs = {}, {}, []
    for split in ("train", "valid", "test"):
        path = _fetch(DITTO.format(split=split), d / f"{split}.txt")
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            a, b, y = line.rstrip("\n").split("\t")
            ra, rb = _ditto_record(a), _ditto_record(b)
            ka = "a" + hashlib.sha1(json.dumps(ra, sort_keys=True).encode()).hexdigest()[:12]
            kb = "b" + hashlib.sha1(json.dumps(rb, sort_keys=True).encode()).hexdigest()[:12]
            left[ka] = {"id": ka, **{f: ra.get(f, "") for f in ABT_FIELDS}}
            right[kb] = {"id": kb, **{f: rb.get(f, "") for f in ABT_FIELDS}}
            pairs.append({"l_id": ka, "r_id": kb, "label": float(y), "split": split})
    pairs = pd.DataFrame(pairs)
    # the same pair in two splits would leak: keep its first split (train < valid < test in file order)
    dup = pairs.duplicated(["l_id", "r_id"])
    notes = [f"{int(dup.sum())} pair(s) repeated across Ditto splits, kept once"] if dup.any() else []
    return Corpus("abt_buy", "pairs", ABT_FIELDS, pd.DataFrame(left.values()), pd.DataFrame(right.values()),
                  pairs=pairs[~dup].reset_index(drop=True), notes=notes)


# --- Leipzig Affiliations ------------------------------------------------------------------------------------------
LEIPZIG_FIELDS = {"affiliation": {"type": "organisation"}}


def leipzig_affiliations() -> Corpus:
    d = DATA / "leipzig"
    ids, mapping = d / "affiliationstrings_ids.csv", d / "affiliationstrings_mapping.csv"
    if not ids.exists():
        with zipfile.ZipFile(_fetch(LEIPZIG_URL, d / "affiliationstrings.zip")) as zf:
            zf.extractall(d)
    recs = pd.read_csv(ids, dtype=str, keep_default_na=False).rename(columns={"id1": "id", "affil1": "affiliation"})
    # gold clusters: union-find over the match pairs
    parent: dict[str, str] = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    with open(mapping, newline="") as fh:
        for a, b in csv.reader(fh):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    recs["cluster"] = recs["id"].map(find)
    truth = recs[["id", "cluster"]]
    return Corpus("leipzig_affiliations", "dedupe", LEIPZIG_FIELDS, recs[["id", "affiliation"]],
                  recs[["id", "affiliation"]], truth=truth,
                  notes=[f"{recs['cluster'].nunique()} gold clusters over {len(recs)} strings"])


# --- FEBRL4 original, FEBRL3 (recordlinkage ships both inside the package: offline) --------------------------------
def febrl4_original() -> Corpus:
    from recordlinkage.datasets import load_febrl4
    a, b, links = load_febrl4(return_links=True)
    side = lambda df: df.reset_index().rename(columns={"rec_id": "id"}).fillna("").astype(str)[["id", *FEBRL_FIELDS]]
    truth = pd.DataFrame(list(links), columns=["l_id", "r_id"])
    return Corpus("febrl4_original", "linkage", dict(FEBRL_FIELDS), side(a), side(b), truth=truth,
                  notes=["every left record has exactly one partner: the nearest neighbour is a strong baseline"])


def febrl3() -> Corpus:
    from recordlinkage.datasets import load_febrl3
    a = load_febrl3().reset_index().rename(columns={"rec_id": "id"}).fillna("").astype(str)
    a["cluster"] = a["id"].str.extract(r"^(rec-\d+)-")[0]
    recs = a[["id", *FEBRL_FIELDS]]
    sizes = a.groupby("cluster").size()
    return Corpus("febrl3", "dedupe", dict(FEBRL_FIELDS), recs, recs, truth=a[["id", "cluster"]],
                  notes=[f"{len(sizes)} gold clusters over {len(a)} records, largest {int(sizes.max())}"])


# --- Magellan structured product and citation sets (Ditto's fixed splits) ------------------------------------------
DITTO_STRUCTURED = "https://raw.githubusercontent.com/megagonlabs/ditto/master/data/er_magellan/Structured/{name}/{split}.txt"
AMAZON_GOOGLE_FIELDS = {"title": {"type": "title"}, "manufacturer": {"type": "organisation"},
                        "price": {"type": "number"}}
WALMART_AMAZON_FIELDS = {"title": {"type": "title"}, "category": {"type": "title"}, "brand": {"type": "organisation"},
                         "modelno": {"type": "code"}, "price": {"type": "number"}}
DBLP_ACM_FIELDS = {"title": {"type": "title"}, "authors": {"type": "title"}, "venue": {"type": "organisation"},
                   "year": {"type": "code"}}


def _ditto(name: str, url: str, local: str, fields: dict) -> Corpus:
    """Ditto's serialised pair files -> two record tables + labelled pairs. A pair repeated in a later split would
    leak into evaluation: it is kept in its first split only (train < valid < test), and the count is noted."""
    d = DATA / local
    left, right, pairs = {}, {}, []
    for split in ("train", "valid", "test"):
        path = _fetch(url.format(split=split), d / f"{split}.txt")
        for line in path.read_text(encoding="utf-8").splitlines():
            a, b, y = line.rstrip("\n").split("\t")
            ra, rb = _ditto_record(a), _ditto_record(b)
            ka = "a" + hashlib.sha1(json.dumps(ra, sort_keys=True).encode()).hexdigest()[:12]
            kb = "b" + hashlib.sha1(json.dumps(rb, sort_keys=True).encode()).hexdigest()[:12]
            left[ka] = {"id": ka, **{f: ra.get(f, "") for f in fields}}
            right[kb] = {"id": kb, **{f: rb.get(f, "") for f in fields}}
            pairs.append({"l_id": ka, "r_id": kb, "label": float(y), "split": split})
    pairs = pd.DataFrame(pairs)
    dup = pairs.duplicated(["l_id", "r_id"])
    notes = [f"{int(dup.sum())} pair(s) repeated across Ditto splits, kept once"] if dup.any() else []
    return Corpus(name, "pairs", fields, pd.DataFrame(left.values()), pd.DataFrame(right.values()),
                  pairs=pairs[~dup].reset_index(drop=True), notes=notes)


def amazon_google() -> Corpus:
    return _ditto("amazon_google", DITTO_STRUCTURED.replace("{name}", "Amazon-Google"), "amazon_google",
                  AMAZON_GOOGLE_FIELDS)


def walmart_amazon() -> Corpus:
    return _ditto("walmart_amazon", DITTO_STRUCTURED.replace("{name}", "Walmart-Amazon"), "walmart_amazon",
                  WALMART_AMAZON_FIELDS)


def dblp_acm() -> Corpus:
    return _ditto("dblp_acm", DITTO_STRUCTURED.replace("{name}", "DBLP-ACM"), "dblp_acm", DBLP_ACM_FIELDS)


# --- Splink historical_50k -----------------------------------------------------------------------------------------
SPLINK_50K_URL = ("https://raw.githubusercontent.com/moj-analytical-services/splink_datasets/master/data/"
                  "historical_figures_with_errors_50k.parquet")
SPLINK_50K_FIELDS = {"first_name": {"type": "person_name"}, "surname": {"type": "person_name"},
                     "dob": {"type": "date"}, "birth_place": {"type": "address"},
                     "postcode_fake": {"type": "code"}, "occupation": {"type": "title"}}


def splink_historical_50k() -> Corpus:
    p = _fetch(SPLINK_50K_URL, DATA / "splink" / "historical_50k.parquet")
    a = pd.read_parquet(p).rename(columns={"unique_id": "id"})
    a = a[["id", "cluster", *SPLINK_50K_FIELDS]].fillna("").astype(str)
    sizes = a.groupby("cluster").size()
    recs = a[["id", *SPLINK_50K_FIELDS]]
    return Corpus("splink_historical_50k", "dedupe", SPLINK_50K_FIELDS, recs, recs, truth=a[["id", "cluster"]],
                  notes=[f"{len(sizes)} gold clusters over {len(a)} records, largest {int(sizes.max())}"])


def synthetic_1e6() -> Corpus:
    import synthetic
    return synthetic.load()


LOADERS = {"febrl4_half_unmatched": febrl4_half_unmatched, "febrl4_original": febrl4_original, "febrl3": febrl3,
           "bpid": bpid, "abt_buy": abt_buy, "amazon_google": amazon_google, "walmart_amazon": walmart_amazon,
           "dblp_acm": dblp_acm, "splink_historical_50k": splink_historical_50k,
           "leipzig_affiliations": leipzig_affiliations, "synthetic_1e6": synthetic_1e6}
