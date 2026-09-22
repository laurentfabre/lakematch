"""Immutable provenance behavior without cloud or Spark."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from threading import Barrier

import pytest

from lakematch.mastering.contracts import ContractError, digest, DomainContract, SourceMapping
from lakematch.mastering.lineage import LineageConflict, build_snapshot, entity_detail, verify_snapshot, MAX_SNAPSHOT_BYTES
from lakematch.mastering.lineage_publication import LocalLineageStore
from lakematch.mastering.survivorship import calculate
from lakematch.mastering.survivorship_contract import SurvivorshipBinding, SurvivorshipPolicy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from lakefusion_lineage_fixture import dataset


def build(entries, context):
    return build_snapshot("first", entries, context, expected_previous=None)


def recalculate(entry, mutate):
    c = entry["calculation"]
    d = DomainContract.from_dict(c["binding"]["domain"])
    p = SurvivorshipPolicy.from_dict(c["binding"]["policy"])
    b = SurvivorshipBinding(p, d, tuple(SourceMapping.from_dict(m, d) for m in entry["mappings"]), tuple(c["binding"]["approvals"]))
    inputs = deepcopy(c["inputs"])
    mutate(inputs)
    entry["calculation"] = calculate(b, inputs["identity"], inputs["records"], as_of=inputs["as_of"],
                                     overrides=[o["decision"] for o in inputs["overrides"]])


def test_fields_link_to_immutable_sources_overrides_and_contracts():
    data = dataset()
    first = build(data["first"], data["context"])
    second = build_snapshot("second", data["second"], data["context"], expected_previous="first", previous=first)
    assert first["counts"] == {"golden_records": 6, "attribute_lineage": 48, "source_versions": 12, "memberships": 12, "contracts": 1}
    before, after = (entity_detail(s, data["cedar_id"]) for s in (first, second))
    assert before["revision"] == 1 and after["revision"] == 2
    assert before["identity_revision"] == after["identity_revision"] == 1
    assert before["values"]["address_line1"] == "10 Example Avenue"
    assert after["values"]["address_line1"] == "99 Updated Example Avenue"
    assert after["fields"]["legal_name"]["reason"] == "approved_override"
    assert after["overrides"][0]["decision"]["approved_by"] == "synthetic_approver"
    for detail in (before, after):
        sources = {(r["source_id"], r["source_key"], r["version"]): digest(r) for r in detail["sources"]}
        decisions = {r["decision"]["decision_id"]: digest(r["decision"]) for r in detail["overrides"]}
        assert detail["contract"]["matching_context"]["model"] is None
        assert len(detail["contract"]["mappings"]) == 2
        for name, field in detail["fields"].items():
            assert field["value_sha256"] == digest(detail["values"][name])
            winner = field["winner"]
            if winner and "source_id" in winner:
                assert sources[(winner["source_id"], winner["source_key"], winner["version"])] == winner["sha256"]
            elif winner:
                assert decisions[winner["decision_id"]] == winner["sha256"]
            else:
                assert detail["values"][name] is None and field["reason"] == "no_eligible_value"
    atlas = entity_detail(second, data["atlas_id"])
    assert any(s["deleted"] for s in atlas["sources"]) and atlas["revision"] == 2


def test_reordering_is_identical_and_inputs_detached():
    data = dataset()
    saved = deepcopy(data)
    expected = build(data["first"], data["context"])
    shuffled = deepcopy(data["first"])
    for entry in shuffled:
        entry["mappings"].reverse()
    assert build(list(reversed(shuffled)), data["context"]) == expected
    assert data == saved


def test_unchanged_master_keeps_revision_but_context_changes_advance_it():
    data = dataset()
    first = build(data["first"], data["context"])
    second = build_snapshot("second", data["first"], data["context"], expected_previous="first", previous=first)
    assert all(r["revision"] == 1 for r in second["tables"]["golden_records"])
    context = deepcopy(data["context"])
    context["configuration"].update(version=2, sha256="0" * 64)
    third = build_snapshot("third", data["first"], context, expected_previous="second", previous=second)
    assert all(r["revision"] == 2 for r in third["tables"]["golden_records"])


def test_historical_reads_do_not_invoke_current_survivorship(monkeypatch, tmp_path):
    data = dataset()
    store = LocalLineageStore(tmp_path / "published")
    store.publish("first", data["first"], data["context"], expected_previous=None)
    original = store.read("first")
    store.publish("second", data["second"], data["context"], expected_previous="first")
    def forbidden(*args, **kwargs):
        pytest.fail("Historical reads must not run a newer selection algorithm")
    monkeypatch.setattr("lakematch.mastering.lineage.calculate", forbidden)
    assert LocalLineageStore(store.root).read("first") == original
    assert LocalLineageStore(store.root).current()["publication_id"] == "second"


def test_reads_do_not_create_missing_catalog(tmp_path):
    store = LocalLineageStore(tmp_path / "absent")
    assert store.current() is None and store.read("missing") is None
    assert not store.root.exists()


def test_committed_retry_survives_unavailable_current_code_but_new_batch_does_not(monkeypatch, tmp_path):
    data = dataset()
    store = LocalLineageStore(tmp_path)
    first = store.publish("first", data["first"], data["context"], expected_previous=None)
    store.publish("second", data["second"], data["context"], expected_previous="first")
    def unavailable(*args, **kwargs):
        raise RuntimeError("current scalar implementation unavailable")
    monkeypatch.setattr("lakematch.mastering.lineage.calculate", unavailable)
    retry = store.publish("first", data["first"], data["context"], expected_previous=None)
    assert retry["reused"] and retry["attempt"] == first["attempt"]
    assert store.current()["publication_id"] == "second"
    with pytest.raises(RuntimeError, match="current scalar implementation"):
        store.publish("new", data["second"], data["context"], expected_previous="second")
    assert store.read("new") is None


def test_exact_historic_retry_does_not_rewind_and_changed_retry_conflicts(tmp_path):
    data = dataset()
    store = LocalLineageStore(tmp_path)
    original = store.publish("first", data["first"], data["context"], expected_previous=None)
    store.publish("second", data["second"], data["context"], expected_previous="first")
    retry = store.publish("first", list(reversed(data["first"])), data["context"], expected_previous=None)
    assert retry["reused"] and retry["attempt"] == original["attempt"]
    assert store.current()["publication_id"] == "second"
    with pytest.raises(ValueError, match="different inputs"):
        store.publish("first", data["second"], data["context"], expected_previous=None)


@pytest.mark.parametrize("case", ["checksum", "rehash_wrong_winner", "mapping_drift", "no_approval", "self_approval", "review_required"])
def test_invalid_calculation_or_approval_cannot_publish(case):
    data = dataset()
    entry = data["first"][0]
    c = entry["calculation"]
    if case in {"checksum", "rehash_wrong_winner"}:
        c["values"]["legal_name"] = "Invented name"
        if case == "rehash_wrong_winner":
            c["fields"]["legal_name"]["value_sha256"] = digest("Invented name")
            c["result_sha256"] = digest({k: v for k, v in c.items() if k != "result_sha256"})
    elif case == "mapping_drift":
        entry["mappings"][0]["version"] = 2
    else:
        if case == "no_approval":
            c["binding"]["approvals"] = []
        elif case == "self_approval":
            c["binding"]["approvals"][0]["approved_by"] = c["binding"]["approvals"][0]["created_by"]
        else:
            c["status"] = "needs_review"
        c["result_sha256"] = digest({k: v for k, v in c.items() if k != "result_sha256"})
    with pytest.raises((LineageConflict, ContractError)):
        build(data["first"], data["context"])


@pytest.mark.parametrize("case", ["stale_head", "remove_master", "source_same_version", "source_rollback", "identity_rollback", "evaluation_rollback", "membership_same_revision"])
def test_snapshot_history_cannot_silently_roll_back(case):
    data = dataset()
    first = build(data["first"], data["context"])
    entries = deepcopy(data["second"])
    expected = "first"
    if case == "stale_head":
        expected = "wrong"
    elif case == "remove_master":
        entries.pop()
    elif case == "source_same_version":
        recalculate(entries[0], lambda i: i["records"][1].update(version=1))
    elif case == "source_rollback":
        first = build_snapshot("second", entries, data["context"], expected_previous="first", previous=first)
        entries, expected = data["first"], "second"
    elif case == "identity_rollback":
        original = deepcopy(data["first"])
        recalculate(original[1], lambda i: i["identity"].update(revision=2))
        first = build(original, data["context"])
    elif case == "evaluation_rollback":
        recalculate(entries[1], lambda i: i.update(as_of="2026-09-22T11:00:00+00:00"))
    else:
        def move_key(i):
            i["identity"]["members"][0]["source_key"] = "A-new"
            i["records"][0]["source_key"] = "A-new"
        recalculate(entries[1], move_key)
    with pytest.raises(LineageConflict):
        build_snapshot("new", entries, data["context"], expected_previous=expected, previous=first)


def test_source_cannot_belong_to_two_masters():
    data = dataset()
    entries = [deepcopy(data["first"][0]), deepcopy(data["first"][0])]
    recalculate(entries[1], lambda i: i["identity"].update(master_id=data["first"][1]["calculation"]["master_id"]))
    with pytest.raises(LineageConflict, match="multiple masters"):
        build(entries, data["context"])


def test_projection_corruption_with_rehashed_outer_envelope_fails():
    data = dataset()
    s = build(data["first"], data["context"])
    s["tables"]["attribute_lineage"][0]["reason"] = "invented_reason"
    s["table_sha256"]["attribute_lineage"] = digest(s["tables"]["attribute_lineage"])
    s["snapshot_sha256"] = digest({k: v for k, v in s.items() if k != "snapshot_sha256"})
    with pytest.raises(LineageConflict, match="projections"):
        verify_snapshot(s)


def test_modified_committed_file_fails(tmp_path):
    data = dataset()
    store = LocalLineageStore(tmp_path)
    receipt = store.publish("first", data["first"], data["context"], expected_previous=None)
    (Path(receipt["root"]) / "attribute_lineage.json").write_text("[]")
    with pytest.raises(ValueError, match="files changed"):
        store.read("first")


def test_concurrent_new_heads_have_one_winner(tmp_path):
    data = dataset()
    store = LocalLineageStore(tmp_path)
    store.publish("first", data["first"], data["context"], expected_previous=None)
    barrier = Barrier(2)
    def publish(index):
        barrier.wait(timeout=5)
        try:
            return store.publish(f"next-{index}", data["second"], data["context"], expected_previous="first")
        except LineageConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(publish, (1, 2)))
    assert sum(r == "conflict" for r in receipts) == 1
    assert store.read("first")["publication_id"] == "first"


def test_process_death_during_projection_write_preserves_old_snapshot(tmp_path):
    data = dataset()
    store = LocalLineageStore(tmp_path / "published")
    store.publish("first", data["first"], data["context"], expected_previous=None)
    fixture = tmp_path / "input.json"
    fixture.write_text(json.dumps(data))
    script = '''
import json, os, sys
from pathlib import Path
from lakematch.mastering.lineage_publication import LocalLineageStore
original = Path.write_text
def interrupted(path, *args, **kwargs):
    result = original(path, *args, **kwargs)
    if path.name == 'golden_records.json': os._exit(73)
    return result
Path.write_text = interrupted
data = json.loads(Path(sys.argv[2]).read_text())
LocalLineageStore(sys.argv[1]).publish('second', data['second'], data['context'], expected_previous='first')
'''
    result = subprocess.run([sys.executable, "-c", script, str(store.root), str(fixture)], timeout=20)
    assert result.returncode == 73
    assert store.current()["publication_id"] == "first"
    receipt = store.publish("second", data["second"], data["context"], expected_previous="first")
    assert len(receipt["recovered_attempts"]) == 1
    assert store.read("first")["publication_id"] == "first"


def test_finite_master_and_byte_bounds():
    data = dataset()
    with pytest.raises(ContractError):
        build(data["first"] * 17, data["context"])
    huge = deepcopy(data["context"])
    huge["extra"] = "x" * MAX_SNAPSHOT_BYTES
    with pytest.raises(ContractError):
        build(data["first"], huge)
