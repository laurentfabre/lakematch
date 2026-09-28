"""Input-store boundary tests using synthetic labels and records only."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bench"))
import corpora
import simbeat_inputs as inputs


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def revise_public(store, name, filename, value):
    """Rehash deliberate schema corruption, so readers must check more than bytes."""
    write(store / name / filename, value)
    manifest = json.loads((store / "manifest.json").read_text())
    manifest["corpora"][name]["files"][filename] = sha(store / name / filename)
    write(store / "manifest.json", manifest)


@pytest.fixture
def public_store(tmp_path):
    root = tmp_path / "inputs"
    manifest = {"schema_version": 2, "source_sha256": {name: "a" * 64 for name in inputs.DATA_FILES}, "corpora": {}}
    for name, kind in inputs.KINDS.items():
        records = {"left": [{"id": "a", "name": "Alice"}], "right": [{"id": "b", "name": "Alicia"}],
                   "pairs": [{"l_id": "a", "r_id": "b", "split": "test"}] if kind == "pairs" else []}
        development = {"pairs": [], "truth": [], "units": ["a"] if kind == "linkage" else []}
        heldout = {"pairs": [{"l_id": "a", "r_id": "b", "label": 1.0, "split": "test"}] if kind == "pairs" else [],
                   "truth": [], "units": []}
        for filename, value in (("records.json", records), ("development.json", development), ("heldout.json", heldout)):
            write(root / name / filename, value)
        manifest["corpora"][name] = {
            "name": name, "kind": kind, "fields": {"name": {"type": "title"}},
            "files": {filename: sha(root / name / filename) for filename in inputs.PUBLIC_FILES},
            "heldout_sha256": sha(root / name / "heldout.json"),
        }
    write(root / "manifest.json", manifest)
    return root


def test_public_readers_never_open_raw_or_heldout_or_call_eager_loaders(public_store, monkeypatch):
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        assert path.name != "heldout.json", "public reader accessed heldout outcomes"
        assert corpora.DATA not in path.parents, "public reader accessed legacy data"
        return original_open(path, *args, **kwargs)

    def forbidden_loader():
        raise AssertionError("public reader called an eager corpus loader")

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(corpora, "LOADERS", {name: forbidden_loader for name in inputs.CORPORA})
    monkeypatch.setattr(inputs, "DEFAULT_INPUTS", public_store)
    assert inputs.public_manifest()["schema_version"] == 2
    for name in inputs.CORPORA:
        corpus = inputs.load_records(name)
        assert corpus.truth is None and corpus.notes == []
        assert list(corpus.left) == ["id", "name"]
        assert list(corpus.right) == ["id", "name"]
        if corpus.kind == "pairs":
            assert list(corpus.pairs) == ["l_id", "r_id", "split"]
            assert corpus.pairs.iloc[0]["split"] == "test"
        else:
            assert corpus.pairs is None
        assert inputs.load_development(name)["pairs"] == []


def test_public_validation_works_even_when_heldout_is_unavailable(public_store):
    for name in inputs.CORPORA:
        (public_store / name / "heldout.json").unlink()
    assert inputs.public_manifest(public_store)
    assert inputs.load_records("bpid", public_store).truth is None
    assert inputs.load_development("bpid", public_store)["pairs"] == []


@pytest.mark.parametrize("filename", ["records.json", "development.json"])
def test_public_file_byte_corruption_is_rejected(public_store, filename):
    path = public_store / "bpid" / filename
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(inputs.InputError, match="hash mismatch"):
        inputs.public_manifest(public_store)
    with pytest.raises(inputs.InputError):
        inputs.load_records("bpid", public_store)
    with pytest.raises(inputs.InputError):
        inputs.load_development("bpid", public_store)


@pytest.mark.parametrize("location", ["left", "pairs"])
def test_public_record_outcome_columns_are_rejected_even_if_rehashed(public_store, location):
    records = json.loads((public_store / "bpid/records.json").read_text())
    records[location][0]["label"] = 1.0
    revise_public(public_store, "bpid", "records.json", records)
    with pytest.raises(inputs.InputError, match="columns"):
        inputs.load_records("bpid", public_store)


def test_development_reader_rejects_test_labels_even_if_rehashed(public_store):
    payload = {"pairs": [{"l_id": "a", "r_id": "b", "label": 1.0, "split": "test"}], "truth": [], "units": []}
    revise_public(public_store, "bpid", "development.json", payload)
    with pytest.raises(inputs.InputError, match="wrong split"):
        inputs.load_development("bpid", public_store)


@pytest.mark.parametrize("mutation", ["version", "missing_corpus", "private_file", "wrong_kind"])
def test_manifest_schema_rejects_invalid_public_boundary(public_store, mutation):
    manifest = json.loads((public_store / "manifest.json").read_text())
    if mutation == "version":
        manifest["schema_version"] = 1
    elif mutation == "missing_corpus":
        del manifest["corpora"]["bpid"]
    elif mutation == "private_file":
        manifest["corpora"]["bpid"]["files"]["heldout.json"] = manifest["corpora"]["bpid"]["heldout_sha256"]
    else:
        manifest["corpora"]["bpid"]["kind"] = "dedupe"
    write(public_store / "manifest.json", manifest)
    with pytest.raises(inputs.InputError):
        inputs.public_manifest(public_store)


@pytest.fixture
def synthetic_legacy(tmp_path, monkeypatch):
    raw = tmp_path / "legacy"
    for filename in inputs.DATA_FILES:
        path = raw / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic source " + filename + "\n")
    fields = {"name": {"type": "title"}}

    def records(prefix, count):
        # Extra source columns deliberately include outcome metadata; staging
        # must project only the declared record fields into the public store.
        return pd.DataFrame([{"id": f"{prefix}{i:02}", "name": f"record {i}", "cluster": "secret", "label": 1}
                             for i in range(count)])

    left, right = records("l", 24), records("r", 12)
    fixtures = {"febrl4_half_unmatched": corpora.Corpus(
        "febrl4_half_unmatched", "linkage", fields, left, right,
        truth=pd.DataFrame([{"l_id": f"l{i:02}", "r_id": f"r{i:02}"} for i in range(12)]),
        notes=["private truth-derived note"])}
    for name in ("bpid", "abt_buy"):
        pairs = pd.DataFrame([{"l_id": f"l{i:02}", "r_id": f"r{i:02}", "label": float(i != 1), "split": split}
                              for i, split in enumerate(("train", "valid", "test"))])
        fixtures[name] = corpora.Corpus(name, "pairs", fields, records("l", 3), records("r", 3), pairs=pairs)
    dedupe = records("d", 15)
    clusters = pd.DataFrame([{"id": f"d{i:02}", "cluster": "one" if i < 8 else "two"} for i in range(15)])
    fixtures["leipzig_affiliations"] = corpora.Corpus(
        "leipzig_affiliations", "dedupe", fields, dedupe, dedupe.copy(), truth=clusters)
    monkeypatch.setattr(corpora, "DATA", raw)
    monkeypatch.setattr(corpora, "LOADERS", {name: lambda corpus=corpus: copy.deepcopy(corpus) for name, corpus in fixtures.items()})
    return raw, fixtures


def test_explicit_staging_partitions_all_corpora_with_historical_rules(spark, synthetic_legacy, tmp_path):
    from methods import bucket
    from pyspark.sql import functions as F

    raw, source = synthetic_legacy
    destination = tmp_path / "store"
    manifest = inputs.stage_inputs(spark, destination)
    assert manifest == inputs.public_manifest(destination)
    assert manifest["source_sha256"] == {filename: sha(raw / filename) for filename in inputs.DATA_FILES}
    assert not list(tmp_path.glob(".store.stage-*"))
    for name, corpus in source.items():
        public = inputs.load_records(name, destination)
        assert set(public.left) == {"id", "name"} and public.truth is None and public.notes == []
        dev = inputs.load_development(name, destination)
        heldout_path = destination / name / "heldout.json"
        assert sha(heldout_path) == manifest["corpora"][name]["heldout_sha256"]
        heldout = json.loads(heldout_path.read_text())
        if corpus.kind == "pairs":
            assert [pair["split"] for pair in dev["pairs"]] == ["train", "valid"]
            assert [pair["split"] for pair in heldout["pairs"]] == ["test"]
            assert dev["pairs"] + heldout["pairs"] == corpus.pairs.to_dict("records")
            assert public.pairs.to_dict("records") == corpus.pairs.drop(columns="label").to_dict("records")
            assert not dev["truth"] and not heldout["truth"]
        elif corpus.kind == "linkage":
            expected = {row.id: row.split for row in spark.createDataFrame([(v,) for v in corpus.left.id], "id string")
                        .select("id", bucket("id").alias("split")).collect()}
            assert set(dev["units"]) == {key for key, split in expected.items() if split != "test"}
            assert set(heldout["units"]) == {key for key, split in expected.items() if split == "test"}
            assert heldout["units"] and dev["units"]
            all_truth = set(corpus.truth.itertuples(index=False, name=None))
            assert set(map(tuple, dev["truth"])) == {(a, b) for a, b in all_truth if expected[a] != "test"}
            assert set(map(tuple, heldout["truth"])) == {(a, b) for a, b in all_truth if expected[a] == "test"}
            assert set(dev["units"] + heldout["units"]) == set(corpus.left.id)
        else:
            expected_pairs = [(a.id, b.id) for a in corpus.truth.itertuples() for b in corpus.truth.itertuples()
                              if a.cluster == b.cluster and a.id < b.id]
            expected = {(row.a, row.b): row.split for row in spark.createDataFrame(expected_pairs, "a string, b string")
                        .select("a", "b", bucket(F.concat_ws("|", "a", "b")).alias("split")).collect()}
            assert set(map(tuple, dev["truth"])) == {pair for pair, split in expected.items() if split != "test"}
            assert set(map(tuple, heldout["truth"])) == {pair for pair, split in expected.items() if split == "test"}
            assert dev["truth"] and heldout["truth"]
            assert not dev["units"] and not heldout["units"]


def test_staging_rejects_existing_destination_before_loading(public_store, monkeypatch):
    def forbidden_loader():
        raise AssertionError("existing store must not invoke legacy loaders")
    monkeypatch.setattr(corpora, "LOADERS", {name: forbidden_loader for name in inputs.CORPORA})
    before = (public_store / "manifest.json").read_bytes()
    with pytest.raises(inputs.InputError, match="already exists"):
        inputs.stage_inputs(None, public_store)
    assert (public_store / "manifest.json").read_bytes() == before


def test_staging_failure_never_publishes_partial_store(synthetic_legacy, tmp_path, monkeypatch):
    def broken_loader():
        raise RuntimeError("synthetic failure")
    monkeypatch.setitem(corpora.LOADERS, inputs.CORPORA[0], broken_loader)
    destination = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="synthetic failure"):
        inputs.stage_inputs(None, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob(".failed.stage-*"))


def test_missing_raw_source_fails_before_any_eager_loader(synthetic_legacy, tmp_path, monkeypatch):
    raw, _ = synthetic_legacy
    (raw / inputs.DATA_FILES[-1]).unlink()

    def forbidden_loader():
        raise AssertionError("missing source must fail before any download-capable loader")

    monkeypatch.setattr(corpora, "LOADERS", {name: forbidden_loader for name in inputs.CORPORA})
    with pytest.raises(inputs.InputError, match="Cannot read input file"):
        inputs.stage_inputs(None, tmp_path / "unpublished")
    assert not (tmp_path / "unpublished").exists()
