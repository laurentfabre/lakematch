"""Lossless public corpus preparation and frozen split manifests.

No network calls. No confirmation scoring. SHA-256 namespaced ranking implements
the predeclared seed streams and is independent of Python RNG implementation.
"""
import csv
from dataclasses import dataclass
import hashlib
import itertools
import json
from pathlib import Path
import re

SEED = 2026091901


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def rank(namespace, key):
    return digest([SEED, namespace, key])


def pair_key(left, right):
    return digest(sorted([canonical(left), canonical(right)]))


def eligible_supervised_pair(a_id, b_id, left_splits, right_splits):
    """Training is record-disjoint; validation may use the transductive universe."""
    split = left_splits[a_id]
    return split == "valid" or (split == "train" and right_splits[b_id] == "train")


class Components:
    def __init__(self):
        self.parent = {}

    def find(self, key):
        self.parent.setdefault(key, key)
        if self.parent[key] != key:
            self.parent[key] = self.find(self.parent[key])
        return self.parent[key]

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        self.parent[max(a, b)] = min(a, b)


@dataclass
class Corpus:
    name: str
    fields: dict
    left: list
    right: list
    pairs: list
    manifest: dict
    retrieval: bool = False

    def freeze(self, root="data/bench"):
        directory = Path(root) / self.name
        directory.mkdir(parents=True, exist_ok=True)
        files = {}
        for name, rows in (("left", self.left), ("right", self.right), ("pairs", self.pairs)):
            path = directory / f"{name}.jsonl"
            content = "".join(canonical(row) + "\n" for row in rows)
            if path.exists() and path.read_text() != content:
                raise ValueError(f"Frozen corpus differs; never replace a split silently: {path}")
            path.write_text(content)
            files[name] = {"path": str(path), "sha256": hashlib.sha256(content.encode()).hexdigest(), "rows": len(rows)}
        manifest = {**self.manifest, "corpus": self.name, "seed": SEED, "fields": self.fields,
                    "retrieval": self.retrieval, "files": files, "confirmation_scored": False}
        path = directory / "manifest.json"
        if path.exists() and json.loads(path.read_text()) != manifest:
            raise ValueError(f"Frozen manifest differs: {path}")
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        return path


def febrl4(variant="all"):
    from recordlinkage.datasets import load_febrl4
    a, b, truth = load_febrl4(return_links=True)
    entities = sorted(list(truth), key=lambda p: rank("febrl4/entities", list(p)))
    partition = {pair: "train" if i < 3000 else "valid" if i < 4000 else "confirmation"
                 for i, pair in enumerate(entities)}
    retained = set()
    for split in ("train", "valid", "confirmation"):
        group = sorted([p for p in entities if partition[p] == split], key=lambda p: rank("febrl4/removal", list(p)))
        retained.update(p[1] for p in group[:len(group) // 2])
    kinds = {"given_name": "person_name", "surname": "person_name", "street_number": "code", "address_1": "address",
             "address_2": "address", "suburb": "address", "postcode": "code", "state": "code",
             "date_of_birth": "date", "soc_sec_id": "code"}
    hidden = {"all": [], "no_ssn": ["soc_sec_id"], "no_ssn_dob": ["soc_sec_id", "date_of_birth"]}[variant]
    fields = {n: {"type": kind, **({"date_format": "yyyyMMdd"} if kind == "date" else {})} for n, kind in kinds.items() if n not in hidden}
    splits_a = {p[0]: s for p, s in partition.items()}
    splits_b = {p[1]: s for p, s in partition.items()}
    def records(frame, splits, keep=None):
        return [{"rec_id": str(index), "split": splits[index], **{n: str(row[n]) if str(row[n]) != "nan" else "" for n in fields}}
                for index, row in frame.iterrows() if keep is None or index in keep]
    positives = [{"a_id": x, "b_id": y, "label": 1., "split": partition[(x, y)], "group": x} for x, y in truth if y in retained]
    return Corpus(f"febrl4_half_{variant}", fields, records(a, splits_a), records(b, splits_b, retained), positives,
        {"source": "recordlinkage 0.16 FEBRL4", "license": "BSD-3-Clause distribution, synthetic FEBRL data",
         "split_method": "SHA-256 ranked whole truth entities 3000/1000/1000; independent namespaced partner-removal ranking",
         "exposure": "Historical corpus and 80 smoke anchors exposed; new split/removal outcomes, not independent population",
         "universe": "5000 left / 2500 right; full-universe transductive candidates; supervised IDF fits train only",
         "hidden_fields": hidden, "closed_world_truth": True}, retrieval=True)


def parse_ditto(line):
    left, right, label = line.rstrip("\r\n").split("\t")
    def record(text):
        values = {}
        # Preserve apostrophes, punctuation and field values; only trim format delimiters.
        for part in re.split(r"(?:^| )COL ", text):
            if " VAL " in part:
                key, value = part.split(" VAL ", 1)
                values[key.strip()] = value.strip()
            elif part.endswith(" VAL"):
                values[part[:-4].strip()] = ""
        if not values:
            raise ValueError("Missing COL/VAL fields in Ditto record")
        return values
    return record(left), record(right), int(label)


def pair_corpus(name, rows, fields, source, split_method="official"):
    """Canonicalize orientation, exclude every conflict, dedupe train > valid > test."""
    order = {"train": 0, "valid": 1, "test": 2, "confirmation": 2}
    labels = {}
    for a, b, y, split in rows:
        labels.setdefault(pair_key(a, b), set()).add(y)
    conflicts = {key for key, ys in labels.items() if len(ys) != 1}
    left, right, pairs, seen = {}, {}, [], set()
    duplicates = 0
    graph = Components()
    if split_method == "record_components":
        for a, b, y, split in rows:
            graph.union(digest(a), digest(b))
    for a, b, y, split in sorted(rows, key=lambda r: order.get(r[3], 0)):
        key = pair_key(a, b)
        if key in conflicts:
            continue
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        aid, bid = "a_" + digest(a), "b_" + digest(b)
        group = graph.find(digest(a)) if split_method == "record_components" else digest(a)
        if split_method == "record_components":
            bucket = int(rank(name + "/components", group), 16) % 10
            split = "train" if bucket < 6 else "valid" if bucket < 8 else "confirmation"
        left[aid], right[bid] = {"rec_id": aid, **a}, {"rec_id": bid, **b}
        pairs.append({"a_id": aid, "b_id": bid, "label": float(y), "split": split, "group": group})
    by_split = {s: {p[side] [2:] for p in pairs if p["split"] == s for side in ("a_id", "b_id")}
                for s in sorted({p["split"] for p in pairs})}
    overlaps = {f"{s1}/{s2}": len(by_split[s1] & by_split[s2]) for s1, s2 in itertools.combinations(by_split, 2)}
    if split_method == "record_components" and any(overlaps.values()):
        raise AssertionError("Record-disjoint split leaked a record")
    return Corpus(name, fields, list(left.values()), list(right.values()), pairs,
        {**source, "split_method": split_method, "duplicate_or_reversed_pairs_removed": duplicates,
         "conflicting_pair_keys_excluded": len(conflicts), "shared_records_between_splits": overlaps,
         "evaluation": "supplied labeled pairs, not all-pairs retrieval; unlabeled pairs are not negatives",
         "split_counts": {s: sum(p["split"] == s for p in pairs) for s in by_split}})


def bpid():
    path = Path("data/sources/bpid/matching_dataset.jsonl")
    rows = [(r["profile1"], r["profile2"], int(r["match"] == "True"), "train")
            for r in map(json.loads, path.read_text().splitlines())]
    fields = {"fullname": {"type": "person_name"}, "email": {"type": "code", "multiple": True},
              "phone": {"type": "code", "multiple": True}, "addr": {"type": "address", "multiple": True},
              "dob": {"type": "date", "date_format": "yyyy-MM-dd"}}
    return pair_corpus("bpid", rows, fields, {"source": "Zenodo 13932202", "license": "Apache-2.0",
        "raw_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "date_note": "ISO dates parsed; other/ambiguous formats remain missing typed features, raw text comparisons retained"}, "record_components")


def ditto(name):
    rows, hashes = [], {}
    for split in ("train", "valid", "test"):
        path = Path("data/sources/ditto") / name / f"{split}.txt"
        hashes[split] = hashlib.sha256(path.read_bytes()).hexdigest()
        rows += [(*parse_ditto(line), split) for line in path.read_text().splitlines()]
    names = sorted({n for a, b, _, _ in rows for record in (a, b) for n in record})
    fields = {n: {"type": "number" if n in {"price", "year"} else "person_name" if n in {"authors", "author"}
                  else "organisation" if n in {"manufacturer", "brand"} else "title"} for n in names}
    return pair_corpus(name.lower().replace("-", "_"), rows, fields,
        {"source": "megagonlabs/ditto@52985564a93fb11308439516d3e17a033d43ec8f",
         "license": "mirror Apache-2.0; upstream unspecified", "raw_sha256": hashes})


def affiliations():
    root = Path("data/sources/affiliations")
    with (root / "affiliationstrings_ids.csv").open() as f:
        records = {r["id1"]: {"name": r["affil1"]} for r in csv.DictReader(f)}
    graph = Components()
    with (root / "affiliationstrings_mapping.csv").open() as f:
        edges = list(csv.reader(f))
    for a, b in edges:
        graph.union(a, b)
    # The released mappings define identity components; assign whole components.
    groups = {}
    for key in records:
        groups.setdefault(graph.find(key), []).append(key)
    splits = {}
    ordered = sorted(groups, key=lambda k: rank("affiliations/entities", k))
    for i, group in enumerate(ordered):
        split = "train" if i < len(ordered) * .6 else "valid" if i < len(ordered) * .8 else "confirmation"
        splits[group] = split
    rows = []
    for group, ids in groups.items():
        for a, b in itertools.combinations(sorted(ids), 2):
            rows.append((records[a], records[b], 1, splits[group]))
    # Five deterministic same-partition negatives per anchor. This is a declared
    # sampled-pair task; it is not an estimate of full-universe rejection accuracy.
    for a in sorted(records):
        eligible = [b for b in records if graph.find(a) != graph.find(b) and splits[graph.find(a)] == splits[graph.find(b)]]
        for b in sorted(eligible, key=lambda b: rank("affiliations/negatives", [a, b]))[:5]:
            rows.append((records[a], records[b], 0, splits[graph.find(a)]))
    corpus = pair_corpus("affiliations", rows, {"name": {"type": "organisation"}},
        {"source": "Leipzig affiliationstrings.zip", "license": "CC BY 4.0",
         "identity_components": len(groups), "negative_sampling": "5 per anchor, same split, different released component",
         "raw_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob("*.csv")}})
    corpus.manifest["split_method"] = "released identity components 60/20/20, SHA-256 ranking"
    return corpus


LOADERS = {"febrl4": febrl4, "bpid": bpid, "abt_buy": lambda: ditto("Abt-Buy"), "affiliations": affiliations,
           "amazon_google": lambda: ditto("Amazon-Google"), "walmart_amazon": lambda: ditto("Walmart-Amazon"),
           "dblp_acm": lambda: ditto("DBLP-ACM")}
