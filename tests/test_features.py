"""ZR-2: a feature family per field type, built-ins on the default path, UDF features optional and flagged."""
import pytest
from pyspark.sql import functions as F

from conftest import make_cfg
from lakematch import embeddings, entity, features
from lakematch.config import ConfigError, FAMILIES
from lakematch.features import udf

ALL_TYPES = {"name": {"type": "person_name"}, "addr": {"type": "address"}, "org": {"type": "organisation"},
             "title": {"type": "title"}, "code": {"type": "code"}, "mail": {"type": "code", "multi": True},
             "dob": {"type": "date"}, "price": {"type": "number"}}
SCHEMA = "rid string, name string, addr string, org string, title string, code string, mail string, dob string, price string"
LEFT = [("1", "Jean-Luc Picard", "12 rue du Bac", "Acme Widgets SARL", "Sony WH-1000XM4 headphones", "AB-123",
         "jl@starfleet.org | picard@ent.com", "1953 11 09", "1,299.00")]
RIGHT = [("2", "Picard Jean Luc", "12 r. du bac", "ACME Widgets", "sony wh1000xm4 wireless headphones", "ab123",
          "picard@ent.com", "09 nov 1953", "1299"),
         ("3", "J. Picard", "", "Globex Corp", "", "", "", "jul 18sat 1953", "")]
UDF_NODES = ("PythonUDF", "BatchEvalPython", "ArrowEvalPython")


def _pairs(rt, cfg):
    mk = lambda rows: entity.prepare(rt.spark.createDataFrame(rows, SCHEMA), cfg, "rid")
    left, right = features.prepare_sides(mk(LEFT), mk(RIGHT), cfg)
    left, right = rt.materialize(left, "l"), rt.materialize(right, "r")     # as the pipeline does
    pre = lambda df, p, i: df.select([F.col(c).alias(i if c == "id" else p + c) for c in df.columns])
    return pre(left, "l_", "l_id").crossJoin(pre(right, "r_", "r_id"))


def _plan(df, capsys):
    df.explain(True)
    return capsys.readouterr().out


def test_every_field_type_has_its_family(rt):
    cfg = make_cfg(entity={"fields": ALL_TYPES})
    out, cols = features.compare(_pairs(rt, cfg), cfg, candidates=False)
    by_field = {}
    for c in cols:
        by_field.setdefault(c.split("_", 1)[1], set()).add(features.family_of(c))
    assert {"edit", "exact", "phonetic", "monge_elkan", "token_idf", "structure", "rarity"} <= by_field["name"]
    assert {"token_idf", "gram", "monge_elkan", "structure"} <= by_field["addr"]
    assert {"token_idf", "gram", "structure", "rarity"} <= by_field["org"]
    assert {"token_idf", "gram", "structure"} <= by_field["title"]
    assert {"edit", "exact"} <= by_field["code"] and {"structure", "monge_elkan"} <= by_field["mail"]
    assert "structure" in by_field["dob"] and "structure" in by_field["price"]
    assert {features.family_of(c) for c in cols} <= set(FAMILIES)


def test_default_features_compile_without_python_udfs(rt, capsys):
    cfg = make_cfg(entity={"fields": ALL_TYPES})
    out, cols = features.compare(_pairs(rt, cfg), cfg, candidates=False)
    plan = _plan(out.select(*cols), capsys)
    assert plan and not any(n in plan for n in UDF_NODES)
    assert not {"jaro_winkler", "affine_gap"} & {features.family_of(c) for c in cols}


def test_structure_values(rt):
    cfg = make_cfg(entity={"fields": ALL_TYPES})
    out, _ = features.compare(_pairs(rt, cfg), cfg, candidates=False)
    rows = {r.r_id: r for r in out.collect()}
    two, three = rows["2"], rows["3"]
    assert two.swp_name == 1.0 and two.sdt_name == 1.0            # same tokens, other order
    assert three.ini_name == 1.0                                   # "j" initial matches "jean"
    assert two.num_addr == 1.0 and two.num_title < 1.0            # house number shared; model number split differently
    assert two.fpe_org == 1.0 and two.lgf_org == -1.0 and three.fpe_org == 0.0
    assert two.yr_dob == 1.0 and two.dpj_dob == 1.0 and three.yr_dob == 1.0 and three.dpj_dob < 1.0
    assert two.rel_price == 1.0 and three.rel_price == -1.0
    assert two.eq_mail == 1.0 and two.csj_mail == pytest.approx(0.5) and three.eq_mail == -1.0
    assert 0 < two.itc_addr <= 1 and two.rar_name > 0


def test_idf_token_cosine_and_rarity(spark):
    cfg = make_cfg(entity={"fields": {"addr": {"type": "address"}}})
    mk = lambda rows: entity.prepare(spark.createDataFrame(rows, "rid string, addr string"), cfg, "rid")
    left, right = features.token_weights(mk([("1", "12 rue du bac")]), mk([("2", "rue du bac"), ("3", "12 avenue foch")]), "addr")
    pairs = left.select(F.col("ti_addr").alias("l")).crossJoin(right.select("id", F.col("ti_addr").alias("r")))
    got = {r.id: (r.c, r.k) for r in pairs.select("id", features._idf_cosine(F.col("l"), F.col("r")).alias("c"),
                                                  features._rarity(F.col("l"), F.col("r")).alias("k")).collect()}
    assert 0 < got["3"][0] < got["2"][0] < 1
    assert 0 < got["3"][1] <= 1 and 0 < got["2"][1] <= 1


def test_jaro_winkler_reference_values():
    # Winkler's published examples
    assert udf.jaro_winkler_score("martha", "marhta") == pytest.approx(0.9611, abs=1e-4)
    assert udf.jaro_winkler_score("dwayne", "duane") == pytest.approx(0.84, abs=1e-4)
    assert udf.jaro_winkler_score("dixon", "dicksonx") == pytest.approx(0.8133, abs=1e-4)
    assert udf.jaro("", "abc") == 0.0 and udf.jaro_winkler_score(None, "a") is None


def test_affine_gap_scores():
    assert udf.affine_gap_score("smith", "smith") == 1.0
    assert udf.affine_gap_score("al", "alexander smith") == 1.0            # containment scores 1 (documented)
    assert udf.affine_gap_score("dave", "tave") < 1.0 and udf.affine_gap_score("dave", "tave") > udf.affine_gap_score("dave", "xave")
    assert udf.affine_gap_score("abc", "xyz") == 0.0


def test_udf_features_are_gated_and_flagged(rt, capsys):
    cfg = make_cfg(entity={"fields": ALL_TYPES},
                   features={"string_similarity": "both", "multi_token": ["affine_gap_udf"], "udf_features": False})
    with pytest.raises(ConfigError, match="udf_features"):
        features.compare(_pairs(rt, cfg), cfg, candidates=False)
    cfg = make_cfg(entity={"fields": ALL_TYPES}, features={"string_similarity": "both", "udf_features": True,
                   "multi_token": ["idf_token_cosine", "gram_overlap", "monge_elkan_token", "affine_gap_udf"]})
    out, cols = features.compare(_pairs(rt, cfg), cfg, candidates=False)
    fams = {features.family_of(c) for c in cols}
    assert {"jaro_winkler", "affine_gap", "edit"} <= fams
    assert any(n in _plan(out.select(*cols), capsys) for n in UDF_NODES)      # visible in the plan: never Photon
    row = {r.r_id: r for r in out.collect()}["2"]
    assert 0 < row.jw_name <= 1 and 0 < row.agp_org <= 1


def test_exclude_drops_families(rt):
    cfg = make_cfg(entity={"fields": ALL_TYPES}, features={"exclude": ["structure", "phonetic"]})
    _, cols = features.compare(_pairs(rt, cfg), cfg, candidates=False)
    assert not {"structure", "phonetic"} & {features.family_of(c) for c in cols}
    with pytest.raises(ConfigError, match="feature family"):
        make_cfg(features={"exclude": ["vibes"]})


def test_embeddings_through_the_local_provider(rt, capsys):
    cfg = make_cfg(entity={"fields": ALL_TYPES}, features={"embeddings": {"provider": "local"}})
    provider = embeddings.resolve(cfg)
    vecs = provider.encode(["Acme Widgets", "ACME widgets ltd"])
    assert vecs.shape[0] == 2 and abs(float((vecs[0] ** 2).sum()) - 1) < 1e-5
    pairs = _pairs(rt, cfg)                                           # the UDF runs here, once per record, then pinned
    out, cols = features.compare(pairs, cfg, candidates=False)
    assert {"ebc_org", "ebc_title"} <= set(cols) and "ebc_name" not in cols
    rows = {r.r_id: r for r in out.collect()}
    assert rows["2"].ebc_org > rows["3"].ebc_org and rows["3"].ebc_title == -1.0
    assert not any(n in _plan(out.select(*cols), capsys) for n in UDF_NODES)   # pair plan: built-ins only


def test_auto_provider_skips_quietly_without_a_cached_model(spark):
    cfg = make_cfg(features={"embeddings": {"provider": "auto", "model": "minishlab/not-a-real-model-xyz"}})
    assert embeddings.resolve(cfg) is None
