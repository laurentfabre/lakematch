#!/usr/bin/env python3
"""Seeded native scale ladder with bounded joins, fitting and durable outputs."""
import argparse
import json
import os
from pathlib import Path
import shlex
import tarfile
import time
from uuid import uuid4

from pyspark.sql import functions as F

from lakematch import blocking, candidates, decision, entity, feature_stats, features, matcher, tracking
from lakematch.config import from_dict
from lakematch.runtime import Materializer, create_session, probe
from evidence import sha256
from frozen import load_freeze, tree_hashes
from offline_run import assert_offline
from spark_event_metrics import summarize as summarize_events


def records(spark, size, side, namespace, *, hot=False):
    frame = spark.range(size).withColumn('digest', F.sha2(F.concat(F.lit('2026091901/' + namespace + '/'), F.col('id')), 256))
    return frame.select(F.concat(F.lit(namespace + '-' + side + '-'), F.format_string('%09d', 'id')).alias('rec_id'),
        (F.lit('common person') if hot else F.concat(F.lit('person '), F.substring('digest', 1, 12))).alias('name'),
        (F.lit('common address') if hot else F.concat(F.lit('block '), F.substring('digest', 13, 12))).alias('address'),
        (F.lit('COMMON') if hot else F.col('digest')).alias('code'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--records', type=int, choices=[1000, 10000, 100000, 1000000], required=True)
    args = parser.parse_args()
    assert_offline()
    started = time.perf_counter()
    freeze = load_freeze()
    method = freeze['method']
    half = args.records // 2
    out = (Path('data/scale') / str(args.records)).resolve()
    out.mkdir(parents=True, exist_ok=True)
    event_root = out / 'spark-events' / uuid4().hex
    event_root.mkdir(parents=True)
    os.environ['PYSPARK_SUBMIT_ARGS'] = shlex.join(['--conf', 'spark.eventLog.enabled=true',
        '--conf', 'spark.eventLog.compress=false', '--conf', 'spark.eventLog.dir=' + event_root.as_uri(), 'pyspark-shell'])
    raw = {'entity': {'name': 'synthetic_scale', 'fields': {'name': {'type': 'person_name'},
        'address': {'type': 'address'}, 'code': {'type': 'code'}}},
        'runtime': {'materialize': 'table'},
        'candidates': {'method': method, 'k': 5, 'max_pairs': half * 5, 'max_join_rows': 50000000,
                       'union_of': ['gram_topk', 'field_blocks']},
        'features': {'multi_token': ['idf_token_cosine'], 'embeddings': {'provider': 'none'}},
        'matcher': {'estimator': 'gbt', 'max_iter': 20, 'max_depth': 3, 'seed': 0},
        'decision': {'threshold': .5, 'cardinality': 'one_to_one'},
        'mlflow': {'tracking_uri': f'sqlite:///{out}/mlflow.db', 'experiment': 'zr3-scale'}}
    raw['candidates']['field_blocks'] = blocking.proposed_rules(from_dict(raw))
    config = from_dict(raw)
    report = {'status': 'running', 'records': args.records, 'left_records': half, 'right_records': half,
        'seed': 2026091901, 'config': config.data, 'confirmation_scored': False,
        'freeze_sha256': sha256('bench/freeze.json'), 'spark_event_root': str(event_root),
        'source': 'tools/run_scale.py, namespaced SHA-256 generation', 'license': 'Apache-2.0 synthetic fixture',
        'population': 'synthetic exact duplicates with unique SHA-256 codes; separate 400-record training namespace',
        'limits': 'This measures bounded native work, not realistic corruption accuracy or throughput certification',
        'cost': {'remote_spend': 0, 'live_label_spend': 0}}
    output = out / 'report.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    spark = create_session(config)
    try:
        capabilities = probe(spark)
        with Materializer(spark, config, capabilities) as work:
            training_raw = [records(spark, 200, side, 'train') for side in ('a', 'b')]
            training = [work.materialize(entity.prepare(frame, config), 'train_' + side) for frame, side in zip(training_raw, ('a', 'b'))]
            vocabulary = work.materialize(feature_stats.fit_idf(training, config), 'idf')
            idf_path = out / 'idf'
            vocabulary.write.mode('overwrite').parquet(str(idf_path))
            training = [work.materialize(feature_stats.attach_idf(frame, vocabulary, config), 'weighted_train_' + side)
                        for frame, side in zip(training, ('a', 'b'))]
            label_rows = [(f'train-a-{i:09d}', f'train-b-{j:09d}', label) for i in range(200)
                          for j, label in [(i, 1.), ((i + 1) % 200, 0.)]]
            labels = spark.createDataFrame(label_rows, 'a_id string, b_id string, label double')
            training_pairs = blocking.rerank(labels.select('a_id', 'b_id'), *training, config)
            training_features = work.materialize(features.build(training_pairs, *training, config), 'training_vectors')
            model = matcher.train(training_features, labels, config)
            state = blocking.prepare_state(*training, labels, config)
            state_path = out / 'state'
            blocking.save_state(state, state_path)
            example = tracking.pair_snapshot(training_pairs.limit(5), *training_raw, config)
            report['model'] = tracking.log_composite(model, config, labels=labels.collect(), input_example=example,
                experiment='zr3-scale', staging_root=out / 'staging', idf_path=str(idf_path),
                candidate_state_path=str(state_path) if blocking.needs_state(config) else None)
            t0 = time.perf_counter()
            prepared = [work.materialize(feature_stats.attach_idf(entity.prepare(records(spark, half, side, 'scale'), config),
                         vocabulary, config), 'records_' + side) for side in ('a', 'b')]
            report['preparation_seconds'] = time.perf_counter() - t0
            t0 = time.perf_counter()
            plan = candidates.build(*prepared, config, state=state)
            report['candidate_budget'] = plan.validate_budget()
            pairs = work.materialize(plan.pairs, 'candidates')
            same_key = F.regexp_extract('a_id', r'([0-9]+)$', 1) == F.regexp_extract('b_id', r'([0-9]+)$', 1)
            found = pairs.filter(same_key).count()
            report['candidate_recall'] = found / half
            report['retrieval_seconds'] = time.perf_counter() - t0
            t0 = time.perf_counter()
            vectors = work.materialize(features.build(pairs, *prepared, config), 'features')
            scored = matcher.score(vectors, model)
            links = decision.links(scored, config)
            links.write.mode('overwrite').parquet(str(out / 'links'))
            published = spark.read.parquet(str(out / 'links'))
            counts = published.agg(F.count('*').alias('links'), F.sum(F.when(same_key, 1).otherwise(0)).alias('tp')).first()
            from lakematch.benchmark.metrics import counts as pair_counts
            tp = counts.tp or 0
            report['metrics'] = pair_counts(tp, counts.links - tp, half - tp)
            report['feature_score_publish_seconds'] = time.perf_counter() - t0
            if args.records == 1000:
                # The hot-key stress fixture deliberately has no distinguishing
                # fields. All keys/buckets exceed the unchanged cap of 400.
                hot = [work.materialize(entity.prepare(records(spark, 1000, side, 'hot', hot=True), config), 'hot_' + side)
                       for side in ('a', 'b')]
                hot_plan = candidates.build(*hot, config, state=state)
                hot_budget = hot_plan.validate_budget()
                report['hot_key_case'] = {'records': 2000, 'candidate_budget': hot_budget,
                    'candidate_recall': hot_plan.pairs.filter(same_key).count() / 1000,
                    'expected': 'nonselective keys are dropped before joining; no recall guarantee on indistinguishable records'}
                assert hot_budget['join_rows_before_cap'] > hot_budget['join_rows_after_cap']
            report['materialization'] = work.events
        report.update(status='completed', cleanup='succeeded')
    except Exception as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        try:
            spark.stop()
        finally:
            report['wall_seconds_including_spark'] = time.perf_counter() - started
            report['records_per_second_including_fit_log_startup_cleanup'] = args.records / report['wall_seconds_including_spark']
            try:
                report['spark_events'] = summarize_events(event_root)
            except ValueError as exc:
                report['spark_events_error'] = str(exc)
            report['output_files'] = tree_hashes(out / 'links')
            event_metrics = out / 'spark-events.json'
            event_metrics.write_text(json.dumps(report.get('spark_events', {}), indent=2) + '\n')
            report['evidence_files'] = {'spark-events.json': sha256(event_metrics)}
            output.write_text(json.dumps(report, indent=2) + '\n')
            with tarfile.open(out / 'scale-evidence.tar.gz', 'w:gz') as archive:
                archive.add(output, arcname='report.json')
                archive.add(event_metrics, arcname=event_metrics.name)
                for path in sorted(event_root.rglob('*')):
                    if path.is_file():
                        archive.add(path, arcname='events/' + str(path.relative_to(event_root)))
    print(json.dumps({'records': args.records, 'candidate_recall': report['candidate_recall'],
                     'f1': report['metrics']['f1'], 'seconds': report['wall_seconds_including_spark']}))


if __name__ == '__main__':
    main()
