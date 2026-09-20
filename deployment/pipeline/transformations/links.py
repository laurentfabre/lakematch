from pyspark import pipelines as dp
from context import load, spark
from lakematch import decision


def define(variant):
    config, _ = load(variant)
    @dp.materialized_view(name=f'lm_links_{variant}')
    def links():
        return decision.links(spark.read.table(f'lm_scores_{variant}'), config)


for variant in ('all', 'no_ssn'):
    define(variant)
