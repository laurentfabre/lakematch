"""Provision SIM-3 inputs explicitly; development readers never open held-out labels.

Run this module once to create a new store. Public records contain all record text
and unlabelled pair IDs/splits; outcomes are separated into development and heldout
files. Only the explicit staging entry point invokes the eager legacy loaders.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
import shutil
import tempfile

import pandas as pd

import corpora

DEFAULT_INPUTS = corpora.DATA / "simbeat_inputs/v2"
CORPORA = ("febrl4_half_unmatched", "bpid", "abt_buy", "leipzig_affiliations")
KINDS = dict(zip(CORPORA, ("linkage", "pairs", "pairs", "dedupe")))
DATA_FILES = (
    "febrl4/left.csv", "febrl4/right.csv", "febrl4/truth.csv",
    "bpid/matching_dataset.jsonl", "abt_buy/train.txt", "abt_buy/valid.txt", "abt_buy/test.txt",
    "leipzig/affiliationstrings_ids.csv", "leipzig/affiliationstrings_mapping.csv",
)
PUBLIC_FILES = {"records.json", "development.json"}
RESERVED_FIELDS = {"id", "label", "labels", "truth", "cluster", "clusters", "notes", "split"}


class InputError(ValueError):
    """The provisioned input store is missing, malformed, or inconsistent."""


def require(condition, message):
    if not condition:
        raise InputError(message)


def file_hash(path):
    h = hashlib.sha256()
    try:
        with Path(path).open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(block)
    except OSError as exc:
        raise InputError(f"Cannot read input file {path}: {exc}") from exc
    return h.hexdigest()


def read(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise InputError(f"Cannot read input JSON {path}: {exc}") from exc


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _root(root):
    return Path(DEFAULT_INPUTS if root is None else root)


def public_manifest(root=None):
    """Validate metadata and public file bytes without reading raw or heldout files."""
    root = _root(root)
    manifest = read(root / "manifest.json")
    require(isinstance(manifest, dict), "Input manifest must be an object")
    require(set(manifest) == {"schema_version", "source_sha256", "corpora"}, "Invalid input manifest keys")
    require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 2,
            "Expected SIM-3 input schema version 2")
    sources = manifest["source_sha256"]
    require(isinstance(sources, dict) and set(sources) == set(DATA_FILES), "Invalid raw source provenance")
    require(all(_hash(value) for value in sources.values()), "Invalid raw source digest")
    entries = manifest["corpora"]
    require(isinstance(entries, dict) and set(entries) == set(CORPORA), "Input manifest must cover all four corpora")
    for name, entry in entries.items():
        require(isinstance(entry, dict) and set(entry) == {"name", "kind", "fields", "files", "heldout_sha256"},
                f"Invalid corpus metadata: {name}")
        require(entry["name"] == name and entry["kind"] == KINDS[name], f"Corpus identity mismatch: {name}")
        fields = entry["fields"]
        require(isinstance(fields, dict) and bool(fields), f"Missing record fields: {name}")
        require(all(isinstance(key, str) and key and key.lower() not in RESERVED_FIELDS
                    and isinstance(value, dict) and isinstance(value.get("type"), str)
                    for key, value in fields.items()), f"Invalid record field declaration: {name}")
        files = entry["files"]
        require(isinstance(files, dict) and set(files) == PUBLIC_FILES, f"Invalid public file inventory: {name}")
        require(_hash(entry["heldout_sha256"]), f"Invalid heldout digest: {name}")
        for filename, expected in files.items():
            require(_hash(expected), f"Invalid public file digest: {name}/{filename}")
            require(file_hash(root / name / filename) == expected, f"Public input hash mismatch: {name}/{filename}")
    return manifest


def _id(value):
    return isinstance(value, str) and bool(value)


def _pairs(rows, *, labelled, splits):
    require(isinstance(rows, list), "Pairs must be an array")
    keys = {"l_id", "r_id", "split"} | ({"label"} if labelled else set())
    seen = set()
    for row in rows:
        require(isinstance(row, dict) and set(row) == keys, "Invalid pair columns")
        require(_id(row["l_id"]) and _id(row["r_id"]), "Invalid pair IDs")
        require(row["split"] in splits, "Pair outcome belongs to the wrong split")
        if labelled:
            require(type(row["label"]) in (int, float) and row["label"] in (0, 1), "Invalid binary pair label")
        key = (row["l_id"], row["r_id"])
        require(key not in seen, "Duplicate input pair")
        seen.add(key)


def validate_payload(payload, kind, heldout=False):
    """Validate the outcome payload's shape and explicit pair split boundary."""
    require(kind in {"pairs", "linkage", "dedupe"}, "Invalid corpus kind")
    require(isinstance(payload, dict) and set(payload) == {"pairs", "truth", "units"}, "Invalid outcome payload keys")
    _pairs(payload["pairs"], labelled=True, splits={"test"} if heldout else {"train", "valid"})
    truth, units = payload["truth"], payload["units"]
    require(isinstance(truth, list) and isinstance(units, list), "Truth and units must be arrays")
    require(all(isinstance(row, list) and len(row) == 2 and all(_id(v) for v in row) for row in truth),
            "Invalid truth pair")
    require(len({tuple(row) for row in truth}) == len(truth), "Duplicate truth pair")
    require(all(_id(unit) for unit in units) and len(set(units)) == len(units), "Invalid or duplicate linkage unit")
    if kind == "pairs":
        require(not truth and not units, "Pair corpora must not carry separate truth or units")
    else:
        require(not payload["pairs"], "Non-pair corpora must not carry labelled pairs")
        if kind == "dedupe":
            require(not units and all(a < b for a, b in truth), "Dedupe truth must be canonical pairs without units")
        else:
            unit_set = set(units)
            require(all(a in unit_set for a, _ in truth), "Linkage truth references an absent left unit")
    return payload


def load_records(name, root=None):
    """Return text records and unlabelled pair IDs/splits, with no outcomes or notes."""
    root = _root(root)
    manifest = public_manifest(root)
    require(name in manifest["corpora"], f"Unknown corpus: {name}")
    entry = manifest["corpora"][name]
    records = read(root / name / "records.json")
    require(isinstance(records, dict) and set(records) == {"left", "right", "pairs"}, "Invalid public record payload")
    columns = ["id", *entry["fields"]]
    tables = []
    ids = []
    for side in ("left", "right"):
        rows = records[side]
        require(isinstance(rows, list), f"Invalid {side} records")
        require(all(isinstance(row, dict) and set(row) == set(columns) and _id(row["id"]) for row in rows),
                f"Invalid public record columns or IDs: {side}")
        side_ids = {row["id"] for row in rows}
        require(len(side_ids) == len(rows), f"Duplicate public record ID: {side}")
        tables.append(pd.DataFrame(rows, columns=columns))
        ids.append(side_ids)
    _pairs(records["pairs"], labelled=False, splits={"train", "valid", "test"})
    require(all(row["l_id"] in ids[0] and row["r_id"] in ids[1] for row in records["pairs"]),
            "Unlabelled pairs reference absent records")
    require(entry["kind"] == "pairs" or not records["pairs"], "Unexpected public pairs in non-pair corpus")
    pairs = pd.DataFrame(records["pairs"], columns=["l_id", "r_id", "split"]) if entry["kind"] == "pairs" else None
    return corpora.Corpus(name, entry["kind"], entry["fields"], *tables, pairs=pairs, truth=None, notes=[])


def load_development(name, root=None):
    """Read only train/validation outcomes from the provisioned public store."""
    root = _root(root)
    manifest = public_manifest(root)
    require(name in manifest["corpora"], f"Unknown corpus: {name}")
    return validate_payload(read(root / name / "development.json"), manifest["corpora"][name]["kind"])


def _write(path, payload):
    path.write_text(json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n")


def _partition(spark, keys):
    """The exact methods.bucket rule; hashing stays in Spark, including UTF-8 IDs."""
    if not keys:
        return {}
    from pyspark.sql import functions as F
    rows = spark.createDataFrame([(key,) for key in sorted(set(keys))], "key string")
    bucket = F.pmod(F.xxhash64("key"), F.lit(10))
    split = F.when(bucket < 6, "train").when(bucket < 8, "valid").otherwise("test")
    return {row.key: row.split for row in rows.select("key", split.alias("split")).collect()}


def _split_corpus(spark, corpus):
    records = {side: getattr(corpus, side)[["id", *corpus.fields]].sort_values("id").to_dict("records")
               for side in ("left", "right")}
    records["pairs"] = []
    development = {"pairs": [], "truth": [], "units": []}
    heldout = {"pairs": [], "truth": [], "units": []}
    if corpus.kind == "pairs":
        require(corpus.pairs is not None, f"Missing source pairs: {corpus.name}")
        rows = corpus.pairs[["l_id", "r_id", "label", "split"]].sort_values(["l_id", "r_id"]).to_dict("records")
        _pairs(rows, labelled=True, splits={"train", "valid", "test"})
        records["pairs"] = [{key: row[key] for key in ("l_id", "r_id", "split")} for row in rows]
        for row in rows:
            (heldout if row["split"] == "test" else development)["pairs"].append(row)
    elif corpus.kind == "dedupe":
        require(corpus.truth is not None, f"Missing source clusters: {corpus.name}")
        truth = sorted(pair for _, group in corpus.truth.groupby("cluster")
                       for pair in itertools.combinations(sorted(group["id"].tolist()), 2))
        partitions = _partition(spark, [a + "|" + b for a, b in truth])
        for a, b in truth:
            (heldout if partitions[a + "|" + b] == "test" else development)["truth"].append([a, b])
    else:
        require(corpus.kind == "linkage" and corpus.truth is not None, f"Missing source linkage truth: {corpus.name}")
        units = sorted(corpus.left["id"].tolist())
        partitions = _partition(spark, units)
        for unit in units:
            (heldout if partitions[unit] == "test" else development)["units"].append(unit)
        truth = sorted(corpus.truth[["l_id", "r_id"]].itertuples(index=False, name=None))
        for a, b in truth:
            require(a in partitions, "Source linkage truth references an absent left unit")
            (heldout if partitions[a] == "test" else development)["truth"].append([a, b])
    validate_payload(development, corpus.kind)
    validate_payload(heldout, corpus.kind, heldout=True)
    return records, development, heldout


def stage_inputs(spark, dest=None):
    """Explicitly provision a fresh store using legacy labels; never overwrite one."""
    dest = _root(dest)
    require(not dest.exists() and not dest.is_symlink(), f"Input store already exists: {dest}")
    # Preflight every source before loaders can attempt their download fallback.
    sources = {name: file_hash(corpora.DATA / name) for name in DATA_FILES}
    dest.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{dest.name}.stage-", dir=dest.parent))
    try:
        manifest = {"schema_version": 2, "source_sha256": sources, "corpora": {}}
        for name in CORPORA:
            corpus = corpora.LOADERS[name]()
            require(corpus.name == name and corpus.kind == KINDS[name], f"Source corpus identity mismatch: {name}")
            records, development, heldout = _split_corpus(spark, corpus)
            directory = staged / name
            directory.mkdir()
            for filename, payload in (("records.json", records), ("development.json", development), ("heldout.json", heldout)):
                _write(directory / filename, payload)
            manifest["corpora"][name] = {
                "name": name, "kind": corpus.kind, "fields": corpus.fields,
                "files": {filename: file_hash(directory / filename) for filename in sorted(PUBLIC_FILES)},
                "heldout_sha256": file_hash(directory / "heldout.json"),
            }
        require(sources == {name: file_hash(corpora.DATA / name) for name in DATA_FILES},
                "Raw sources changed while staging inputs")
        _write(staged / "manifest.json", manifest)
        public_manifest(staged)
        for name in CORPORA:
            load_records(name, staged)
        require(not dest.exists() and not dest.is_symlink(), f"Input store already exists: {dest}")
        staged.rename(dest)
        return manifest
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=DEFAULT_INPUTS)
    args = parser.parse_args()
    from lakematch import config
    from lakematch.runtime import session
    spark = session(config.build({"runtime": {"cores": 2, "shuffle_partitions": 2}}))
    try:
        stage_inputs(spark, args.dest)
        print(f"Provisioned SIM-3 inputs: {args.dest}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
