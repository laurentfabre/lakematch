"""Export selected MLlib state in a job; construct action-free SDP expressions.

The export consumes Spark's persisted model data, never refits. These adapters
are usable only after the caller checks equivalence on its frozen model/runtime.
All Spark reads/collects are confined to the explicit export_* job functions.
"""
import json
import math
from pathlib import Path

from pyspark.sql import Window, functions as F


def _metadata(path):
    files = [p for p in (Path(path) / 'metadata').glob('part-*') if p.is_file() and not p.name.endswith('.crc')]
    if len(files) != 1:
        raise ValueError('Expected one persisted Spark ML metadata part')
    return json.loads(files[0].read_text())


def export_gbt(spark, pipeline_path, feature_order):
    """Job action: export the saved VectorAssembler + binary GBT pipeline."""
    stages = sorted((Path(pipeline_path) / 'stages').iterdir())
    if len(stages) != 2:
        raise ValueError('Native SDP scoring requires a two-stage assembler/GBT pipeline')
    assembler, classifier = [_metadata(path) for path in stages]
    if (not assembler['class'].endswith('.VectorAssembler') or
            assembler['paramMap'].get('inputCols') != feature_order or
            not classifier['class'].endswith('.GBTClassificationModel')):
        raise ValueError('Unsupported Spark ML pipeline shape or feature order')
    weights = {row['_1']: row['_3'] for row in spark.read.parquet(str(stages[1] / 'treesMetadata')).collect()}
    trees = {}
    for row in spark.read.parquet(str(stages[1] / 'data')).collect():
        node = row.nodeData.asDict(recursive=True)
        tree = trees.setdefault(str(row.treeID), {})
        if str(node['id']) in tree:
            raise ValueError('Duplicate persisted tree node')
        tree[str(node['id'])] = {key: node[key] for key in ('prediction', 'leftChild', 'rightChild', 'split')}
    if set(map(int, trees)) != set(weights) or any(not math.isfinite(weight) for weight in weights.values()):
        raise ValueError('Tree/weight inventory differs')
    return {'schema_version': 1, 'kind': 'spark_binary_gbt', 'spark_version': classifier['sparkVersion'],
        'feature_order': feature_order, 'trees': trees, 'weights': {str(k): v for k, v in weights.items()}}


def score_gbt(frame, state):
    """Lazy SQL inference with Spark GBT's logistic loss probability mapping."""
    if state.get('kind') != 'spark_binary_gbt' or state.get('schema_version') != 1:
        raise ValueError('Unsupported native model state')
    names = state['feature_order']
    def expression(nodes, ident, visited):
        if ident in visited or ident not in nodes:
            raise ValueError('Malformed tree topology')
        node = nodes[ident]
        if node['leftChild'] == -1 and node['rightChild'] == -1:
            if not math.isfinite(node['prediction']):
                raise ValueError('Nonfinite leaf prediction')
            return F.lit(float(node['prediction']))
        split = node['split']
        index = split['featureIndex']
        if not 0 <= index < len(names):
            raise ValueError('Tree feature index outside frozen feature order')
        values = split['leftCategoriesOrThreshold']
        if not values or any(not math.isfinite(value) for value in values):
            raise ValueError('Invalid tree split values')
        value = F.col(names[index])
        if split['numCategories'] == -1:
            if len(values) != 1:
                raise ValueError('Continuous splits require one threshold')
            goes_left = value <= values[0]
        else:
            goes_left = value.isin(values)
        visited = visited | {ident}
        return F.when(goes_left, expression(nodes, str(node['leftChild']), visited)).otherwise(
            expression(nodes, str(node['rightChild']), visited))
    margin = F.lit(0.)
    for key in sorted(state['trees'], key=int):
        margin = margin + float(state['weights'][key]) * expression(state['trees'][key], '0', set())
    valid = F.lit(True)
    for name in names:
        valid = valid & F.col(name).isNotNull() & ~F.isnan(F.col(name))
    probability = F.lit(1.) / (F.lit(1.) + F.exp(-2. * margin))
    return frame.withColumn('p', F.when(valid, probability).otherwise(F.raise_error('Invalid frozen feature vector')))


def export_minhash(spark, model_path, config):
    """Job action: preserve MLlib's random coefficients and hashing settings."""
    metadata = _metadata(model_path)
    if not metadata['class'].endswith('.MinHashLSHModel'):
        raise ValueError('Expected a saved MinHashLSH model')
    rows = spark.read.parquet(str(Path(model_path) / 'data')).collect()
    if len(rows) != 1:
        raise ValueError('Expected one MinHash coefficient row')
    flat = rows[0].randCoefficients
    if len(flat) != 2 * config['candidates']['num_hash_tables']:
        raise ValueError('MinHash coefficient count differs from frozen config')
    return {'schema_version': 1, 'kind': 'spark_minhash', 'spark_version': metadata['sparkVersion'],
        'num_features': config['candidates']['num_hash_features'], 'q': config['candidates']['q'],
        'fields': config.fields, 'coefficients': [flat[index:index + 2] for index in range(0, len(flat), 2)],
        'prime': 2038074743, 'hashing': 'standard Murmur3 x86_32 UTF-8, seed 42; Spark ML hashUnsafeBytes2; nonnegative modulo'}


def minhash_keys(frame, state, ident):
    """Lazy SQL equivalent of HashingTF(binary=True) and MinHashLSH.transform."""
    from .entity import grams
    from .murmur3 import hash_utf8
    if state.get('kind') != 'spark_minhash' or state.get('schema_version') != 1:
        raise ValueError('Unsupported native retriever state')
    tokens = grams(F.trim(F.concat_ws(' ', *state['fields'])), state['q'])
    hashed = F.array_distinct(F.transform(tokens, lambda token: F.pmod(hash_utf8(token), F.lit(state['num_features'])).cast('long')))
    buckets = []
    for a, b in state['coefficients']:
        buckets.append(F.array_min(F.transform(hashed, lambda index: F.pmod((index + 1) * F.lit(a) + F.lit(b), F.lit(state['prime'])))))
    keyed = frame.filter(F.size(tokens) > 0).select(F.col('rec_id').alias(ident), F.array(*buckets).alias('lm_buckets'))
    return keyed.select(ident, F.posexplode('lm_buckets').alias('rule', 'value')).select(
        ident, 'rule', F.col('value').cast('long').cast('string').alias('key'))


def minhash_candidates(left, right, config, state):
    """Lazy candidate plan with the same cap, budget and deterministic rerank."""
    from .blocking import guarded, key_statistics, rerank
    from .candidates import CandidatePlan
    spec = config['candidates']
    if (spec['method'] != 'minhash_lsh' or state['fields'] != config.fields or state['q'] != spec['q'] or
            state['num_features'] != spec['num_hash_features'] or len(state['coefficients']) != spec['num_hash_tables']):
        raise ValueError('Native retrieval state differs from frozen configuration')
    a, b = minhash_keys(left, state, 'a_id'), minhash_keys(right, state, 'b_id')
    _, retained, diagnostic = key_statistics(a, b, spec['gram_cap'])
    pairs = guarded(a.join(retained, ['rule', 'key']), diagnostic, spec['max_join_rows']).join(b, ['rule', 'key'])
    ranked = rerank(pairs, left, right, config)
    # SDP cannot call the job-only validate_budget action. Enforce the final
    # budget in its lazy plan as well as guarding the much larger pre-top-k join.
    bounded = ranked.withColumn('lm_pair_count', F.count(F.lit(1)).over(Window.partitionBy(F.lit(1))))
    bounded = bounded.filter(F.when(F.col('lm_pair_count') <= spec['max_pairs'], True)
        .otherwise(F.raise_error('Candidate final pair budget exceeded'))).drop('lm_pair_count')
    return CandidatePlan(bounded, diagnostic, spec['max_join_rows'], spec['max_pairs'],
        {'method': 'minhash_lsh', 'implementation': 'native SQL from frozen MLlib state'})
