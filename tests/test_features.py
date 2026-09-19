from contextlib import redirect_stdout
from io import StringIO
import math

import pytest
from pyspark.sql import functions as F

from lakematch import embeddings, entity, features, feature_stats
from lakematch.config import ConfigError, from_dict
from lakematch.similarity import affine_gap, jaro_winkler, monge_elkan


def pairs(spark, rows=None):
    return spark.createDataFrame(rows or [("a", "b", 1.0, 1, 0.0)],
                                 "a_id string, b_id string, cos double, rank int, gap double")


def native(frame):
    output = StringIO()
    with redirect_stdout(output):
        frame.explain(mode="extended")
    assert not any(n in output.getvalue() for n in ("PythonUDF", "BatchEvalPython", "ArrowEvalPython"))


def test_all_field_families_native_and_typed_values(spark):
    kinds = {"name": "person_name", "addr": "address", "org": "organisation", "title": "title",
             "code": "code", "dob": "date", "amount": "number"}
    cfg = from_dict({"entity": {"fields": {n: {"type": t} for n, t in kinds.items()}},
                     "features": {"multi_token": ["gram_overlap", "monge_elkan_token"],
                                  "embeddings": {"provider": "none"}}})
    schema = "rec_id string, " + ", ".join(f"{n} string" for n in kinds)
    a = entity.prepare(spark.createDataFrame([("a", "Élise 王", "12 Main Street", "Acme ltd", "camera x100", "AB12",
                                              "2024-02-29", "-12.50")], schema), cfg)
    b = entity.prepare(spark.createDataFrame([("b", "elise 王", "Main Street 12", "Acme", "x100 camera", "AB13",
                                              "2024-03-01", "12.50")], schema), cfg)
    frame = features.build(pairs(spark), a, b, cfg)
    row = frame.first().asDict()
    assert row["accent_eq_name"] == 1.0 and row["eq_name"] == 0.0
    assert row["numeric_overlap_addr"] == 1.0 and row["monge_elkan_token_addr"] == 1.0
    assert row["legal_name_eq_org"] == 1.0 and row["token_overlap_title"] == 1.0
    assert row["prefix_eq_code"] == 1.0 and row["suffix_eq_code"] == 0.0
    assert row["year_eq_dob"] == 1.0 and row["month_eq_dob"] == 0.0 and row["date_proximity_dob"] == .5
    assert row["numeric_eq_amount"] == 0.0 and row["sign_eq_amount"] == 0.0 and row["relative_similarity_amount"] == 0.0
    assert frame.columns == ["a_id", "b_id", *features.feature_order(cfg)]
    assert all(math.isfinite(row[c]) for c in features.feature_order(cfg))
    native(frame)


def test_invalid_typed_values_do_not_throw_or_match(spark):
    cfg = from_dict({"entity": {"fields": {"dob": {"type": "date", "date_format": "yyyyMMdd"},
                                             "amount": {"type": "number"}}}})
    schema = "rec_id string, dob string, amount string"
    a = entity.prepare(spark.createDataFrame([("a", "20240230", "NaN"), ("x", "20240229", "1e309")], schema), cfg)
    b = entity.prepare(spark.createDataFrame([("b", "20240230", "NaN")], schema), cfg)
    out = features.build(pairs(spark, [("a", "b", 0., 1, 0.), ("x", "b", 0., 1, 0.)]), a, b, cfg).collect()
    assert all(r.invalid_dob == r.invalid_amount == 1.0 and r.date_proximity_dob == r.numeric_eq_amount == -1.0 for r in out)


def test_idf_training_only_unseen_terms_and_native_score(spark):
    cfg = from_dict({"entity": {"fields": {"text": {"type": "title"}}},
                     "features": {"multi_token": ["idf_token_cosine"], "embeddings": {"provider": "none"}}})
    training = spark.createDataFrame([("1", "common rare"), ("2", "common"), ("3", "")], "rec_id string, text string")
    vocab = feature_stats.fit_idf([training], cfg)
    weights = {r.token: r.idf for r in vocab.collect()}
    assert weights["common"] == pytest.approx(1 + math.log(4 / 3))
    assert weights["rare"] == pytest.approx(1 + math.log(2))
    assert weights[""] == pytest.approx(1 + math.log(4))
    a = feature_stats.attach_idf(spark.createDataFrame([("a", "new common"), ("empty", "")], training.schema), vocab, cfg)
    b = feature_stats.attach_idf(spark.createDataFrame([("b", "common")], training.schema), vocab, cfg)
    enriched = {r.rec_id: r.lm_weights_text for r in a.collect()}
    assert enriched["a"]["new"] == pytest.approx(weights[""])
    assert enriched["empty"] == {}
    frame = features.build(pairs(spark, [("a", "b", 0., 1, 0.), ("empty", "b", 0., 1, 0.)]), a, b, cfg)
    scores = {r.a_id: r.idf_token_cosine_text for r in frame.collect()}
    expected = weights["common"] / math.sqrt(weights[""] ** 2 + weights["common"] ** 2)
    assert scores["a"] == pytest.approx(expected) and scores["empty"] == -1.0
    native(frame)


def test_monge_elkan_is_symmetric_quadratic_mean(spark):
    result = spark.range(1).select(monge_elkan(F.array(F.lit("abc"), F.lit("xyz")), F.array(F.lit("abc"))).alias("ab"),
        monge_elkan(F.array(F.lit("abc")), F.array(F.lit("xyz"), F.lit("abc"))).alias("ba")).first()
    assert result.ab == pytest.approx((math.sqrt(.5) + 1) / 2)
    assert result.ab == result.ba


def test_multivalued_fields_preserve_boundaries_and_empty_arrays(spark):
    cfg = from_dict({"entity": {"fields": {"addr": {"type": "address", "multiple": True}}}})
    schema = "rec_id string, addr array<string>"
    a = entity.prepare(spark.createDataFrame([("a", ["12 King Road", "99 Main Street"]), ("x", [None, ""])], schema), cfg)
    b = entity.prepare(spark.createDataFrame([("b", ["99 Main Street"])], schema), cfg)
    frame = features.build(pairs(spark, [("a", "b", 0., 1, 0.), ("x", "b", 0., 1, 0.)]), a, b, cfg)
    rows = {r.a_id: r for r in frame.collect()}
    assert rows["a"].best_value_lev_addr == 1 and rows["a"].value_overlap_addr == .5
    assert rows["x"].best_value_lev_addr == -1 and rows["x"].missing_addr == 1
    native(frame)


@pytest.mark.parametrize("a,b,expected", [("MARTHA", "MARHTA", .9611111111111111),
    ("DIXON", "DICKSONX", .8133333333333332), ("a", "z", 0.), ("", "x", -1.), ("王", "王", 1.)])
def test_jaro_winkler_reference_values(a, b, expected):
    assert jaro_winkler(a, b) == pytest.approx(expected)
    assert jaro_winkler(b, a) == pytest.approx(expected)


def test_affine_global_alignment_properties():
    assert affine_gap("same", "same") == 1.
    assert affine_gap("", "same") == -1.
    assert affine_gap("abc", "abcdef") == pytest.approx(.75)
    assert affine_gap("abcdef", "abc") == pytest.approx(.75)
    assert affine_gap("abc", "xyz") == 0.


def test_optional_udfs_are_explicit_and_execute(spark):
    raw = {"entity": {"fields": {"name": {"type": "person_name"}}},
           "features": {"string_similarity": "both", "multi_token": ["affine_gap_udf"]}}
    with pytest.raises(ConfigError, match="udf_features"):
        from_dict(raw)
    raw["features"]["udf_features"] = True
    cfg = from_dict(raw)
    a = spark.createDataFrame([("a", "martha")], "rec_id string, name string")
    b = spark.createDataFrame([("b", "marhta")], a.schema)
    row = features.build(pairs(spark), a, b, cfg).first()
    assert row.jw_name == pytest.approx(.9611111111111111)
    assert row.affine_gap_udf_name == pytest.approx(2 / 3)


def test_embedding_precompute_batching_and_native_comparison(spark, tmp_path):
    class Provider:
        calls = []
        def encode(self, texts, **kwargs):
            self.calls.append(texts)
            return [[1., 0.] if text == "camera" else [0., 1.] for text in texts]
    cfg = from_dict({"entity": {"fields": {"title": {"type": "title"}}},
                     "features": {"embeddings": {"fields_of_type": ["title"], "provider": "local", "model": None}}})
    frame = spark.createDataFrame([("a", "camera"), ("b", "camera"), ("c", "")], "rec_id string, title string")
    provider = Provider()
    prepared, report = embeddings.prepare(frame, cfg, tmp_path / "vectors.jsonl", provider=provider, batch_size=1)
    assert report["records"] == 3 and report["dimension"] == 2 and len(provider.calls) == 2
    comparison = features.build(pairs(spark), prepared, prepared, cfg)
    assert comparison.first().embedding_cosine_title == 1.
    native(comparison)
    with pytest.raises(ValueError, match="prepared local"):
        embeddings.prepare(frame, cfg, tmp_path / "unavailable.jsonl")


def test_embedding_auto_missing_is_visible_and_schema_stable(spark, tmp_path):
    cfg = from_dict({"entity": {"fields": {"title": {"type": "title"}}},
                     "features": {"embeddings": {"fields_of_type": ["title"], "model": None}}})
    frame = spark.createDataFrame([("a", "camera"), ("b", "camera")], "rec_id string, title string")
    with pytest.warns(RuntimeWarning, match="No prepared"):
        prepared, report = embeddings.prepare(frame, cfg, tmp_path / "none.jsonl")
    row = features.build(pairs(spark), prepared, prepared, cfg).first()
    assert report["status"] == "unavailable"
    assert row.embedding_cosine_title == -1 and row.embedding_missing_title == 1


def test_field_family_ablation_preserves_candidates_and_other_fields(spark):
    raw = {"entity": {"fields": {"name": {"type": "person_name"}, "code": {"type": "code"}}},
           "features": {"exclude_field_types": ["person_name"]}}
    cfg = from_dict(raw)
    a = entity.prepare(spark.createDataFrame([("a", "alice", "123")], "rec_id string, name string, code string"), cfg)
    b = entity.prepare(spark.createDataFrame([("b", "bob", "123")], a.select("rec_id", "name", "code").schema), cfg)
    row = features.build(pairs(spark), a, b, cfg).first().asDict()
    assert not any(n.endswith("_name") for n in row)
    assert row["cos"] == row["lev_code"] == row["eq_code"] == 1.
    raw["features"]["exclude_field_types"] = ["unknown"]
    with pytest.raises(ConfigError, match="unique field types"):
        from_dict(raw)
