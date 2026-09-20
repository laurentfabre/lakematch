from pyspark import pipelines as dp
from context import load, spark
from lakematch import native_ml


def define(variant):
    _, state = load(variant)
    @dp.materialized_view(name=f'lm_scores_{variant}')
    def scores():
        return native_ml.score_gbt(spark.read.table(f'lm_features_{variant}'), state['gbt'])


for variant in ('all', 'no_ssn'):
    define(variant)
