"""ZR-6: the fitted classifier compiled to one Spark SQL expression gives the same p as model.transform."""
import random

import pytest
from pyspark.sql import functions as F

from conftest import make_cfg
from lakematch import matcher, scoring_sql


@pytest.mark.parametrize("estimator", ["gbt", "random_forest", "logistic_regression"])
def test_compiled_expression_matches_transform(spark, rt, tmp_path, estimator):
    rng = random.Random(5)
    rows = []
    for i in range(400):
        a, b, c = rng.random(), rng.random(), float(rng.randint(0, 3))
        rows.append((f"l{i}", f"r{i}", a, b, c, float(a + 0.5 * b + 0.1 * c + rng.gauss(0, 0.2) > 0.9)))
    df = spark.createDataFrame(rows, "l_id string, r_id string, f_a double, `f b` double, f_c double, label double")
    cols = ["f_a", "f b", "f_c"]
    model = matcher.train(df, cols, make_cfg(matcher={"estimator": estimator}))
    path = rt.save_ml(model, tmp_path / "spark_pipeline")
    expr = scoring_sql.compile_saved(path, cols)
    got = matcher.score(model, df).withColumn("q", F.expr(expr)).select("l_id", "p", "q")
    worst = got.select(F.max(F.abs(F.col("p") - F.col("q")))).first()[0]
    assert worst < 1e-12, worst
