"""Model-backed self-deduplication and atomic local identity publication."""
from pathlib import Path
import time

from pyspark.sql import Window, functions as F

from . import blocking, candidates, clustering, entity, feature_stats, features, identity, matcher, publication, tracking
from .config import from_dict
from .engine import read_records
from .quality import apply_and_split
from .runtime import Materializer, create_session, probe


def pair_context(pairs, records, config):
    """Explicit self-dedupe contract: unweighted cosine, rank one, zero gap.

    Training and arbitrary representative verification must use this same
    metadata. A model trained with directional retrieval ranks is incompatible.
    """
    left = blocking.text_grams(records, config, 'a_id', 'lm_a')
    right = blocking.text_grams(records, config, 'b_id', 'lm_b')
    joined = pairs.select('a_id', 'b_id').join(left, 'a_id').join(right, 'b_id')
    denominator = F.sqrt(F.size('lm_a').cast('double') * F.size('lm_b'))
    return joined.select('a_id', 'b_id', F.when(denominator > 0,
        F.size(F.array_intersect('lm_a', 'lm_b')) / denominator).otherwise(0.).alias('cos'),
        F.lit(1).alias('rank'), F.lit(0.).alias('gap'))


def execute(config, *, model_uri, batch_id, pair_metadata):
    """Publish a full snapshot; deleted records disappear from input.left.

    pair_metadata is an explicit caller declaration for legacy composite models
    whose pair-input signature did not encode how cos/rank/gap were calculated.
    The declaration is recorded in the immutable publication request.
    """
    config.require_implemented()
    if config['runtime']['mode'] != 'local':
        raise NotImplementedError('Remote identity publication requires the Delta job adapter')
    if pair_metadata != 'gram_cosine':
        raise ValueError('Self-dedupe requires a model trained with gram_cosine pair metadata')
    if config['decision']['threshold'] == 'from_validation':
        raise ValueError('Freeze a model and threshold before clustering')
    if not model_uri or not (model_uri.startswith('runs:/') or model_uri.startswith('models:/')) or '@' in model_uri:
        raise ValueError('Clustering requires an immutable runs:/ or versioned models:/ URI')
    source = config['input']['left']
    if not source:
        raise ValueError('Set input.left to the complete current record snapshot')
    started = time.perf_counter()
    digest = publication.request_digest({'records': source},
        {'config': config.data, 'model_uri': model_uri, 'pair_metadata': pair_metadata})
    def build(path, previous):
        spark = create_session(config)
        try:
            capabilities = probe(spark)
            loaded = tracking.load_composite(model_uri, config, Path(config['model']['path']) / 'loaded').unwrap_python_model()
            frozen = from_dict(loaded.contract['config'])
            if any(frozen[key] != config[key] for key in ('entity', 'candidates', 'features', 'decision')):
                raise ValueError('Model contract differs from clustering config')
            if loaded.contract.get('pair_metadata', pair_metadata) != pair_metadata:
                raise ValueError('Model pair metadata differs from the explicit cluster declaration')
            model = loaded.native_model(spark)
            with Materializer(spark, config, capabilities) as work:
                quality = apply_and_split(read_records(spark, source, config), config)
                fingerprints = quality.valid.select(F.col(config['entity']['id_column']).alias('rec_id'),
                    F.sha2(F.to_json(F.struct(*[F.col(field) for field in sorted(config.fields)])), 256).alias('record_digest'))
                prepared = entity.prepare(quality.valid, config)
                if 'idf_token_cosine' in config['features']['multi_token']:
                    vocab = work.materialize(spark.read.parquet(loaded.artifacts['idf']), 'idf')
                    prepared = feature_stats.attach_idf(prepared, vocab, config)
                if config['features']['embeddings']['fields_of_type'] and config['features']['embeddings']['provider'] != 'none':
                    from .embeddings import prepare
                    prepared, _ = prepare(prepared, loaded.config, path / 'embeddings.jsonl')
                prepared = work.materialize(prepared, 'records')
                state = blocking.load_state(loaded.artifacts['retriever']) if blocking.needs_state(config) else None
                plan = candidates.build(prepared, prepared, config, state=state)
                budget = plan.validate_budget()
                retrieved = work.materialize(plan.pairs, 'retrieved')
                nonself = retrieved.filter('a_id != b_id').withColumn('nonself_rank', F.row_number().over(
                    Window.partitionBy('a_id').orderBy(F.desc('cos'), 'b_id'))).filter(
                        F.col('nonself_rank') <= max(1, config['candidates']['k'] - 1))
                pairs = nonself.select(F.least('a_id', 'b_id').alias('a_id'), F.greatest('a_id', 'b_id').alias('b_id')).distinct()
                def score(requests):
                    frame = features.build(pair_context(requests, prepared, config), prepared, prepared, config)
                    return matcher.score(frame, model).select('a_id', 'b_id', 'p')
                edges = work.materialize(score(pairs), 'scores')
                result = clustering.resolve(prepared, edges, config, work, pair_scorer=score)
                crosswalk = work.materialize(identity.assign(result.membership.join(fingerprints, 'rec_id'),
                    config['entity']['name']), 'crosswalk', truncate=True)
                identity.validate_snapshot(crosswalk)
                old = spark.read.parquet(str(Path(previous['root']) / 'crosswalk')) if previous else spark.createDataFrame([], crosswalk.schema)
                journal = identity.reconcile(old, crosswalk)
                frames = {'crosswalk': crosswalk, 'changes': journal.changes, 'cluster_events': journal.cluster_events,
                    'links': edges.filter(F.col('p') >= config['decision']['threshold']), 'quarantine': quality.quarantined}
                counts = {}
                for name, frame in frames.items():
                    frame.write.mode('error').parquet(str(path / name))
                    counts[name] = spark.read.parquet(str(path / name)).count()
                columns = ['rec_id', 'mdm_id', 'record_digest', 'canonical_key']
                replayed = identity.replay(spark.read.parquet(str(path / 'changes'))).select(*columns)
                current = spark.read.parquet(str(path / 'crosswalk')).select(*columns)
                if replayed.exceptAll(current).limit(1).count() or current.exceptAll(replayed).limit(1).count():
                    raise AssertionError('Publication journal does not replay to the current crosswalk')
                report = {'model_uri': model_uri, 'pair_metadata': pair_metadata, 'method': result.method,
                    'rounds': result.rounds, 'candidate_budget': budget, 'counts': counts,
                    'exact_journal_replay': True, 'capabilities': capabilities.to_dict()}
            report['cleanup'] = 'succeeded'
        finally:
            spark.stop()
        report['wall_seconds_including_spark'] = time.perf_counter() - started
        return report
    result = publication.publish(config['output']['root'], batch_id, digest, build)
    return {'status': 'completed', 'publication': result, 'wall_seconds': time.perf_counter() - started}
