from pyspark import pipelines as dp
from context import load, spark
from lakematch import native_ml


def define(variant):
    config, state = load(variant)
    @dp.materialized_view(name=f'lm_candidates_{variant}')
    def candidates():
        left, right = [spark.read.table(f'lm_prepared_{variant}_{side}') for side in ('left', 'right')]
        # The join budget is enforced inside the lazy plan, before pair expansion.
        return native_ml.minhash_candidates(left, right, config, state['minhash']).pairs


for variant in ('all', 'no_ssn'):
    define(variant)
