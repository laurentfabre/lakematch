"""Leakage, reproducibility and corruption invariants using unrelated unit seeds."""
from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
import re

import pytest

from lakematch.benchmark.company_pilot import (
    FEATURES, STRATA, GeneratorSpec, build_partition, family_partitions,
    matching_projection, preparation_manifest, prepare, training_pairs,
)
from lakematch.mastering.contracts import DomainContract, SourceMapping

SPEC = GeneratorSpec(250, 41, 42, 43, 44, 45, 46)
FIXTURE = Path(__file__).resolve().parents[1] / "examples/mastering/company_pilot"


def test_family_partitions_are_disjoint_exact_and_source_independent():
    groups = family_partitions(SPEC)
    assert [len(groups[p]) for p in groups] == [150, 50, 50]
    assert len(set(sum(groups.values(), []))) == 250
    assert groups == family_partitions(replace(SPEC, generation_seed=49))
    assert groups != family_partitions(replace(SPEC, split_seed=49))


def test_approved_manifest_keeps_confirmation_unmaterialized():
    manifest = preparation_manifest(GeneratorSpec())
    assert [v["source_rows"] for v in manifest["partitions"].values()] == [24000, 8000, 8000]
    assert manifest["confirmation_materialized"] is False
    assert manifest["files"] == {}
    with pytest.raises(ValueError, match="withheld"):
        build_partition(GeneratorSpec(), "confirmation")


@pytest.mark.parametrize("partition", ["development", "validation", "confirmation"])
def test_all_sources_map_with_no_truth_or_parent_feature_leakage(partition):
    data = build_partition(SPEC, partition, release_confirmation=True)
    domain = DomainContract.from_dict(json.loads((FIXTURE / "domain.json").read_text()))
    keys = set()
    for source, rows in data["sources"].items():
        mapping = SourceMapping.from_dict(json.loads((FIXTURE / f"{source}_mapping.json").read_text()), domain)
        projected = matching_projection(mapping, rows)
        for row in projected:
            assert set(row) == {"record_id", "features"}
            assert set(row["features"]) == set(FEATURES)
            assert re.fullmatch(r"[0-9a-f]{32}", row["record_id"])
            assert row["record_id"] not in keys
            keys.add(row["record_id"])
    assert len(keys) == len(data["truth"]) * 2
    assert Counter(t["stratum"] for t in data["truth"]) == {
        s: len(data["truth"]) * pct // 100 for s, pct in STRATA.items()}
    assert all(Counter(t["family"] for t in data["truth"])[f] == 2 for f in family_partitions(SPEC)[partition])


def test_stream_reproducibility_and_row_order_do_not_reveal_pairs():
    data = build_partition(SPEC, "development")
    assert data == build_partition(SPEC, "development")
    rekeyed = build_partition(replace(SPEC, key_seed=49), "development")
    assert {t["erp_key"] for t in data["truth"]}.isdisjoint(t["erp_key"] for t in rekeyed["truth"])
    assert data != build_partition(replace(SPEC, perturbation_seed=49), "development")
    truth = {t["erp_key"]: t["crm_key"] for t in data["truth"]}
    aligned = sum(truth[a["vendor_id"]] == b["account_id"]
                  for a, b in zip(data["sources"]["erp_vendor"], data["sources"]["crm_account"]))
    assert aligned < 10


def test_corruptions_include_real_identifier_collision_and_declared_overlaps():
    data = build_partition(SPEC, "development")
    truth = {t["company"]: t for t in data["truth"]}
    erp = {r["vendor_id"]: r for r in data["sources"]["erp_vendor"]}
    crm = {r["account_id"]: r for r in data["sources"]["crm_account"]}
    for company, t in truth.items():
        a, b = erp[t["erp_key"]], crm[t["crm_key"]]
        sibling = erp[truth[company ^ 1]["erp_key"]]
        if t["stratum"] == "identifier_collision":
            assert b["company_registration"] == sibling["registration_number"] != a["registration_number"]
            assert b["country"] == sibling["country_code"] != a["country_code"]
        elif t["stratum"] == "cross_jurisdiction_name":
            assert b["account_name"] == sibling["vendor_name"]
            assert b["country"] != sibling["country_code"]
        elif t["stratum"] == "combined":
            assert b["company_registration"] is None
            assert b["account_name"] != a["vendor_name"]
            assert b["billing_street"] != a["street"]
        elif t["stratum"] == "multilingual":
            assert b["account_name"] != a["vendor_name"]


def test_negative_sampling_is_labelled_disjoint_and_development_only():
    data = build_partition(SPEC, "development")
    truth = data["truth"]
    pairs = training_pairs(SPEC, "development", truth)
    assert len(pairs) == len(truth) * 6
    assert len({(p["erp_key"], p["crm_key"]) for p in pairs}) == len(pairs)
    companies_a = {t["erp_key"]: t["company"] for t in truth}
    companies_b = {t["crm_key"]: t["company"] for t in truth}
    assert all(p["label"] == int(companies_a[p["erp_key"]] == companies_b[p["crm_key"]]) for p in pairs)
    for partition in ("validation", "confirmation"):
        with pytest.raises(ValueError, match="development-only"):
            training_pairs(SPEC, partition, truth)


def test_preparation_is_immutable_and_never_writes_confirmation(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    manifest = prepare(first, SPEC)
    assert manifest == prepare(second, SPEC)
    assert not list(first.glob("confirmation*"))
    assert len(manifest["files"]) == 7
    for name in manifest["files"]:
        assert (first / name).read_bytes() == (second / name).read_bytes()
    with pytest.raises(FileExistsError):
        prepare(first, SPEC)


@pytest.mark.parametrize("change", [{"families": 100}, {"families": 10001}, {"families": True},
                                     {"split_seed": 41}, {"key_seed": -1}])
def test_invalid_workload_or_seed_streams_fail(change):
    with pytest.raises(ValueError):
        replace(SPEC, **change)
