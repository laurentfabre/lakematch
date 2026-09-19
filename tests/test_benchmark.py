import pytest

from lakematch import decision
from lakematch.benchmark.corpora import canonical, eligible_supervised_pair, pair_corpus, pair_key, parse_ditto
from lakematch.benchmark.metrics import bootstrap, evaluate, select, tune
from lakematch.config import from_dict


def test_canonical_records_preserve_apostrophes_and_array_boundaries():
    a = {"name": "O'Neil", "addr": ["1 A", "2 B"]}
    b = {"addr": ["1 A", "2 B"], "name": "O'Neil"}
    assert canonical(a) == canonical(b)
    assert canonical(a) != canonical({"name": "ONeil", "addr": ["1 A 2 B"]})
    assert pair_key(a, {"name": "x"}) == pair_key({"name": "x"}, b)
    left, right, label = parse_ditto("COL name VAL O'Neil COL title VAL \tCOL name VAL O'Neil COL title VAL book\t1")
    assert left == {"name": "O'Neil", "title": ""} and right["title"] == "book" and label == 1


def test_conflicts_reversed_duplicates_and_shared_records_are_accounted():
    a, b, c = {"name": "a"}, {"name": "b"}, {"name": "c"}
    corpus = pair_corpus("test", [(a, b, 1, "train"), (b, a, 1, "valid"),
        (a, c, 1, "train"), (c, a, 0, "test"), (b, c, 0, "valid")], {"name": {"type": "person_name"}}, {})
    assert len(corpus.pairs) == 2
    assert corpus.manifest["duplicate_or_reversed_pairs_removed"] == 1
    assert corpus.manifest["conflicting_pair_keys_excluded"] == 1
    assert corpus.manifest["shared_records_between_splits"]["train/valid"] == 1


def test_record_components_cannot_leak_either_endpoint():
    rows = [({"name": f"a{i}"}, {"name": f"b{i}"}, i % 2, "train") for i in range(100)]
    rows.append(({"name": "b0"}, {"name": "c"}, 0, "train"))
    corpus = pair_corpus("test", rows, {"name": {"type": "person_name"}}, {}, "record_components")
    assert not any(corpus.manifest["shared_records_between_splits"].values())
    assert set(corpus.manifest["split_counts"]) == {"train", "valid", "confirmation"}


def test_frozen_manifest_refuses_changed_split(tmp_path):
    corpus = pair_corpus("test", [({"name": "a"}, {"name": "b"}, 1, "train")], {"name": {"type": "person_name"}}, {})
    corpus.freeze(tmp_path)
    corpus.pairs[0]["split"] = "valid"
    with pytest.raises(ValueError, match="Frozen corpus differs"):
        corpus.freeze(tmp_path)


def test_training_negatives_cannot_import_heldout_partner_records():
    left = {"train_a": "train", "valid_a": "valid", "test_a": "confirmation"}
    right = {"train_b": "train", "valid_b": "valid", "test_b": "confirmation"}
    assert eligible_supervised_pair("train_a", "train_b", left, right)
    assert not eligible_supervised_pair("train_a", "valid_b", left, right)
    assert not eligible_supervised_pair("train_a", "test_b", left, right)
    assert not eligible_supervised_pair("test_a", "train_b", left, right)
    assert eligible_supervised_pair("valid_a", "test_b", left, right)


@pytest.mark.parametrize("cardinality", ["one_to_one", "many_to_one", "unrestricted"])
def test_validation_decisions_match_engine_exactly(spark, cardinality):
    rows = [("a", "b", .9), ("a", "c", .9), ("d", "b", .8), ("e", "f", .1), ("a", "b", .7)]
    cfg = from_dict({"entity": {"fields": {"name": {"type": "person_name"}}},
                     "decision": {"threshold": .5, "cardinality": cardinality}})
    observed = {(r.a_id, r.b_id) for r in decision.links(spark.createDataFrame(rows, "a_id string, b_id string, p double"), cfg).collect()}
    assert observed == select(rows, .5, cardinality)


def test_missing_candidates_remain_false_negatives_and_bootstrap_is_paired():
    labels = {("a", "b"): 1, ("c", "d"): 1, ("a", "z"): 0}
    groups = {pair: pair[0] for pair in labels}
    result, grouped = evaluate({("a", "b")}, labels, groups)
    assert result["fn"] == 1 and result["f1"] == pytest.approx(2 / 3)
    interval = bootstrap(grouped, grouped, resamples=50)
    assert interval["paired_delta_95ci"] == [0., 0.]
    assert interval == bootstrap(grouped, grouped, resamples=50)
    with pytest.raises(ValueError, match="unlabeled"):
        evaluate({("x", "y")}, labels, groups)
    assert tune([("a", "b", .9), ("a", "z", .1)], labels, groups, "unrestricted") == .9
