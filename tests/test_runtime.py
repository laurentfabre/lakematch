from pyspark.sql import functions as F

from conftest import CONNECT, make_cfg
from lakematch.runtime import Runtime, is_remote


def test_session_kind_matches_the_pass(spark):
    assert is_remote(spark) is CONNECT


def test_probe_reports_capabilities(rt):
    assert rt.remote is CONNECT
    assert rt.caps.can_cache and rt.caps.can_checkpoint and rt.caps.local_filesystem
    assert rt.strategy() == "checkpoint"


def test_every_materialize_strategy_gives_the_same_rows(spark, tmp_path):
    df = spark.range(50).withColumn("sq", F.col("id") * F.col("id"))
    expected = sorted(tuple(r) for r in df.collect())
    for how in ("checkpoint", "cache", "table"):
        r = Runtime(make_cfg(tmp_path / how, runtime={"materialize": how}), spark)
        out = r.materialize(df, "squares")
        assert sorted(tuple(x) for x in out.collect()) == expected
        if how == "table":
            assert r.scratch_path("squares").exists()
        r.close()
        assert not (tmp_path / how / "data" / "_scratch" / r.run_id).exists()


def test_temp_views_get_unique_names(rt, spark):
    a = rt.temp_view(spark.range(1), "pairs")
    b = rt.temp_view(spark.range(2), "pairs")
    assert a != b and spark.table(b).count() == 2
