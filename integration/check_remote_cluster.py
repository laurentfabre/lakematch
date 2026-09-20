"""Separate job-task fixture for fit/reload, verified merge and Delta recovery.

This small synthetic test is capability evidence. It is not a replacement for
the full local FEBRL3/historical_50k comparisons or frozen FEBRL4 inference.
"""
from itertools import combinations
import json
from pathlib import Path
import time

from pyspark.sql import functions as F

from lakematch import clustering, entity, features, identity, matcher, tracking
from lakematch.cluster_job import pair_context
from lakematch.config import from_dict
from lakematch.delta_publication import DeltaPublisher, digest
from lakematch.runtime import Materializer, probe


def configuration(schema):
    return from_dict({'profile': 'databricks',
        'runtime': {'mode': 'serverless', 'cli_profile': 'fevm-gdpr2', 'materialize': 'table'},
        'storage': {'scratch_schema': schema},
        'entity': {'name': 'remote_cluster_fixture', 'fields': {
            'name': {'type': 'person_name'}, 'code': {'type': 'code'}}},
        'candidates': {'method': 'gram_topk'},
        'features': {'multi_token': [], 'embeddings': {'provider': 'none'}},
        'matcher': {'max_iter': 5, 'max_depth': 2},
        'decision': {'threshold': .5, 'cardinality': 'unrestricted'},
        'cluster': {'method': 'verified_merge', 'max_rounds': 30},
        'quality': {'engine': 'native'}, 'paid_features': {'app': False, 'genie': False},
        'mlflow': {'tracking_uri': 'databricks', 'registry': False, 'alias': None,
            'experiment': '/Users/laurent.fabre@databricks.com/lakematch/20260919/cluster_fixture'}})


def train(spark, root, schema):
    started = time.perf_counter()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    config = configuration(schema)
    rows = [(f'train-{i}', ['Alice Martin', 'Bob Dupont', 'Carol Smith', 'David Brown'][i // 2],
             f'training-code-{i // 2}') for i in range(8)]
    raw = spark.createDataFrame(rows, 'rec_id string, name string, code string')
    labels = [(f'train-{i}', f'train-{j}', float(i // 2 == j // 2)) for i, j in combinations(range(8), 2)]
    truth = spark.createDataFrame(labels, 'a_id string, b_id string, label double')
    with Materializer(spark, config, probe(spark)) as work:
        prepared = work.materialize(entity.prepare(raw, config), 'train_records')
        pairs = pair_context(truth, prepared, config)
        vectors = work.materialize(features.build(pairs, prepared, prepared, config), 'train_features')
        model = matcher.train(vectors, truth, config)
        result = tracking.log_composite(model, config, labels=truth.collect(),
            input_example=tracking.pair_snapshot(pairs.limit(3), raw, raw, config),
            experiment=config['mlflow']['experiment'], staging_root=root / 'staging')
    report = {'status': 'completed', 'model': result, 'config': config.data,
        'pair_metadata': 'gram_cosine', 'scope': '8 synthetic training records; all 28 pairs; no confirmation labels',
        'seconds': time.perf_counter() - started, 'training_ids': [row[0] for row in rows]}
    (root / 'train-report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def check(spark, root, schema, namespace):
    started = time.perf_counter()
    root = Path(root)
    training = json.loads((root / 'train-report.json').read_text())
    config = from_dict(training['config'])
    loaded = tracking.load_composite(training['model']['model_uri'], config, root / 'loaded').unwrap_python_model()
    model = loaded.native_model(spark)
    original = [('a1', 'Emma Ward', 'group-a'), ('a2', 'Emma Ward', 'group-a'),
                ('a3', 'Emma Ward', 'group-a'), ('b1', 'Fred Jones', 'group-b'), ('b2', 'Fred Jones', 'group-b')]
    changed = [row for row in original if row[0] != 'a3'] + [('b3', 'Fred Jones', 'group-b')]
    changed = [(ident, 'Emma W Ward' if ident == 'a2' else name, code) for ident, name, code in changed]
    assert not set(training['training_ids']) & {row[0] for row in original + changed}
    publisher = DeltaPublisher(spark, schema, namespace)
    capabilities = probe(spark)

    def publish(rows, batch):
        with Materializer(spark, config, capabilities) as work:
            def build(previous):
                raw = spark.createDataFrame(rows, 'rec_id string, name string, code string')
                prepared = work.materialize(entity.prepare(raw, config), 'records')
                pairs = spark.createDataFrame([(a[0], b[0]) for a, b in combinations(sorted(rows), 2)], 'a_id string, b_id string')
                def score(requests):
                    return matcher.score(features.build(pair_context(requests, prepared, config), prepared, prepared, config), model).select('a_id', 'b_id', 'p')
                edges = work.materialize(score(pairs), 'edges')
                resolved = clustering.resolve(prepared, edges, config, work, pair_scorer=score)
                fingerprints = raw.select('rec_id', F.sha2(F.to_json(F.struct('name', 'code')), 256).alias('record_digest'))
                crosswalk = work.materialize(identity.assign(resolved.membership.join(fingerprints, 'rec_id'),
                    config['entity']['name']), 'crosswalk', truncate=True)
                identity.validate_snapshot(crosswalk)
                old = publisher.read(previous, 'crosswalk') if previous else spark.createDataFrame([], crosswalk.schema)
                journal = identity.reconcile(old, crosswalk)
                replayed = identity.replay(journal.changes).select(*crosswalk.columns)
                assert not replayed.exceptAll(crosswalk).limit(1).count()
                assert not crosswalk.exceptAll(replayed).limit(1).count()
                expected = {row[0]: row[2] for row in rows}
                actual = {row.rec_id: row.mdm_id for row in crosswalk.collect()}
                assert all((actual[a] == actual[b]) == (expected[a] == expected[b]) for a, b in combinations(actual, 2))
                return {'crosswalk': crosswalk, 'changes': journal.changes, 'cluster_events': journal.cluster_events,
                    'links': edges.filter(F.col('p') >= .5)}, {'rounds': resolved.rounds, 'exact_journal_replay': True,
                    'model_uri': training['model']['model_uri'], 'pair_metadata': 'gram_cosine'}
            return publisher.publish(batch, digest({'records': rows, 'config': config.data,
                'model': training['model']['model_uri']}), build)

    first = publish(original, 'original')
    # Fail after one immutable output table is written. The head must not move.
    failure_observed = False
    def broken(previous):
        return {'partial': spark.range(1), 'failure': spark.range(1).select(F.raise_error('seeded interrupted publication').cast('long').alias('bad'))}, {}
    try:
        publisher.publish('interrupted', digest({'fixture': 'interrupted'}), broken)
    except Exception as exc:
        if 'seeded interrupted publication' not in str(exc):
            raise
        failure_observed = True
    assert failure_observed and publisher.current()['batch_id'] == 'original'
    second = publish(changed, 'incremental')
    assert second['recovered_tables'], 'The abandoned attempt was not removed on retry'
    retry = publish(changed, 'incremental')
    assert retry['reused'] and retry['attempt'] == second['attempt']
    unchanged = publish(changed, 'unchanged')
    assert publisher.read(unchanged, 'cluster_events').count() == 0
    assert {row.change for row in publisher.read(unchanged, 'changes').collect()} == {'unchanged'}
    historical = publish(original, 'original')
    assert historical['reused'] and historical['attempt'] == first['attempt']
    fresh = DeltaPublisher(spark, schema, namespace)
    assert fresh.current()['batch_id'] == 'unchanged'
    assert fresh.spark.table(fresh.catalog).filter("key != 'head'").count() == 3
    a, b = [fresh.read(body, 'crosswalk') for body in (second, unchanged)]
    assert not a.exceptAll(b).limit(1).count() and not b.exceptAll(a).limit(1).count()
    report = {'status': 'completed', 'model': training['model'], 'namespace': namespace,
        'scope': 'synthetic remote fit/reload, verified merge, Delta publication; not corpus quality evidence',
        'exact_journal_replay': True, 'unchanged_input_stable': True, 'historical_retry_does_not_rewind': True,
        'interrupted_write_kept_previous_head': failure_observed, 'commits': 3, 'seconds': time.perf_counter() - started,
        'publications': {'original': first, 'incremental': second, 'unchanged': unchanged}}
    (root / 'cluster-report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
