from pyspark import pipelines as dp
from context import ROOT, load, spark
from lakematch import entity, feature_stats
from lakematch.quality import apply_and_split


def define(variant, side):
    config, _ = load(variant)
    @dp.materialized_view(name=f'lm_quarantine_{variant}_{side}')
    def quarantine():
        return apply_and_split(spark.read.table(f'lm_input_{variant}_{side}'), config).quarantined
    @dp.materialized_view(name=f'lm_prepared_{variant}_{side}')
    def prepared():
        valid = apply_and_split(spark.read.table(f'lm_input_{variant}_{side}'), config).valid
        vocabulary = spark.read.parquet(str(ROOT / variant / 'idf'))
        return feature_stats.attach_idf(entity.prepare(valid, config), vocabulary, config)


for variant in ('all', 'no_ssn'):
    for side in ('left', 'right'):
        define(variant, side)
