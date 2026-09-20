from pyspark import pipelines as dp
from context import load, spark
from lakematch import features as engine_features


def define(variant):
    config, _ = load(variant)
    @dp.materialized_view(name=f'lm_features_{variant}')
    def features():
        left, right = [spark.read.table(f'lm_prepared_{variant}_{side}') for side in ('left', 'right')]
        return engine_features.build(spark.read.table(f'lm_candidates_{variant}'), left, right, config)


for variant in ('all', 'no_ssn'):
    define(variant)
