from lakematch.benchmark.corpora import pair_corpus
from lakematch.benchmark.retrieval import training_ids, validation_scope


def test_disjoint_retrieval_excludes_training_identity_on_either_side():
    a, b, c, d = ({"name": n} for n in ("a", "b", "c", "d"))
    corpus = pair_corpus("scope", [(a, b, 1, "train"), (b, c, 1, "valid"),
        (c, d, 1, "valid"), (a, d, 1, "confirmation")], {"name": {"type": "person_name"}}, {})
    ids, positives, report = validation_scope(corpus, "disjoint")
    assert len(positives) == 1
    assert report["original_validation_positives"] == 2
    assert report["training_overlapping_records_removed"] == [1, 0]
    assert report["left_records"] == 1 and report["right_records"] == 2
    assert len(validation_scope(corpus, "transductive")[1]) == 2
    trained = training_ids(corpus)
    assert all(not (a & b) for a, b in zip(ids, trained))
