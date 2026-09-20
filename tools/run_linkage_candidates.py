#!/usr/bin/env python3
"""Compare candidate methods with the selected classifier on closed FEBRL tasks."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import tarfile
import time

import mlflow
import pandas as pd
from pyspark.sql import functions as F

from lakematch import blocking, candidates, entity, feature_stats, features, matcher, tracking
from lakematch.benchmark.corpora import eligible_supervised_pair, febrl4
from lakematch.benchmark.metrics import bootstrap, evaluate, select, tune
from lakematch.config import from_dict
from lakematch.runtime import Materializer, create_session, probe
from evidence import sha256
from offline_run import assert_offline

METHODS = ['gram_topk', 'learned_blocker', 'minhash_lsh', 'field_blocks', 'union']
TOKENS = {'native_all': ['idf_token_cosine', 'gram_overlap', 'monge_elkan_token'],
          'idf_only': ['idf_token_cosine'], 'scalar_fields': []}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('variant', choices=['all', 'no_ssn', 'no_ssn_dob'])
    parser.add_argument('--features', choices=TOKENS, required=True)
    parser.add_argument('--estimator', choices=['gbt', 'logistic_regression', 'random_forest'], required=True)
    args = parser.parse_args()
    assert_offline()
    started = time.perf_counter()
    corpus = febrl4(args.variant)
    manifest = corpus.freeze()
    out = (Path('data/linkage_candidates') / corpus.name).resolve()
    out.mkdir(parents=True, exist_ok=True)
    raw = {'entity': {'name': corpus.name, 'fields': corpus.fields},
        'candidates': {'k': 5, 'max_pairs': 100000, 'max_join_rows': 50000000, 'union_of': ['gram_topk', 'field_blocks']},
        'features': {'multi_token': TOKENS[args.features], 'embeddings': {'provider': 'none'}},
        'matcher': {'estimator': args.estimator, 'max_iter': 20, 'max_depth': 3, 'seed': 0},
        'decision': {'threshold': .5, 'cardinality': 'one_to_one'},
        'mlflow': {'tracking_uri': f'sqlite:///{out}/mlflow.db', 'experiment': 'zr3-linkage-candidates'}}
    raw['candidates']['field_blocks'] = blocking.proposed_rules(from_dict(raw))
    config = from_dict(raw)
    report = {'status': 'running', 'iteration': 5, 'corpus': corpus.name,
        'manifest': json.loads(manifest.read_text()), 'config': config.data,
        'plan': 'bench/LINKAGE_PLAN.md', 'confirmation_scored': False,
        'scope': 'full-universe retrieval, both training endpoints in train, validation anchors only for scoring',
        'feature_choice': args.features, 'rows': [], 'baselines': [],
        'cost': {'remote_spend': 0, 'live_label_spend': 0}}
    output = out / 'report.json'
    archive = out / 'linkage-evidence.tar.gz'
    archive.unlink(missing_ok=True)
    files = set()
    def save():
        report['evidence_files'] = {str(path.relative_to(out)): sha256(path) for path in sorted(files)}
        output.write_text(json.dumps(report, indent=2) + '\n')
    save()
    spark = create_session(config)
    try:
        capabilities = probe(spark)
        with Materializer(spark, config, capabilities) as m:
            schema = 'rec_id string, ' + ', '.join(f'{field} string' for field in corpus.fields)
            raw_left, raw_right = [spark.createDataFrame(records, schema) for records in (corpus.left, corpus.right)]
            left, right = [m.materialize(entity.prepare(frame, config), side)
                for frame, side in ((raw_left, 'left'), (raw_right, 'right'))]
            partitions = [{r['rec_id']: r['split'] for r in records} for records in (corpus.left, corpus.right)]
            training_records = []
            for frame, records, name in zip((left, right), (corpus.left, corpus.right), ('train_left', 'train_right')):
                ids = spark.createDataFrame([(r['rec_id'],) for r in records if r['split'] == 'train'], 'rec_id string')
                training_records.append(m.materialize(frame.join(ids, 'rec_id', 'semi'), name))
            idf_path = None
            if 'idf_token_cosine' in TOKENS[args.features]:
                vocab = m.materialize(feature_stats.fit_idf(training_records, config), 'idf')
                idf_path = str(out / 'idf')
                vocab.write.mode('overwrite').parquet(idf_path)
                left, right = [m.materialize(feature_stats.attach_idf(frame, vocab, config), side, truncate=True)
                    for frame, side in ((left, 'weighted_left'), (right, 'weighted_right'))]
            positive_labels = spark.createDataFrame([p for p in corpus.pairs if p['split'] == 'train'],
                'a_id string, b_id string, label double')
            known = {(p['a_id'], p['b_id']) for p in corpus.pairs if p['split'] in {'train', 'valid'}}
            positive_valid = {(p['a_id'], p['b_id']) for p in corpus.pairs if p['split'] == 'valid'}
            valid_anchors = {r['rec_id'] for r in corpus.left if r['split'] == 'valid'}
            reference = None
            for method in METHODS:
                print(json.dumps({'method': method, 'status': 'started'}), flush=True)
                method_start = time.perf_counter()
                cfg = blocking.child_config(config, method)
                state = blocking.prepare_state(*training_records, positive_labels, cfg)
                state_path = out / (method + '_state')
                blocking.save_state(state, state_path)
                files.update(p for p in state_path.rglob('*') if p.is_file())
                with Materializer(spark, cfg, capabilities) as cm:
                    t0 = time.perf_counter()
                    plan = candidates.build(left, right, cfg, state=state)
                    budget = plan.validate_budget()
                    candidate_frame = cm.materialize(plan.pairs, 'candidates', truncate=True)
                    retrieved = candidate_frame.collect()
                    retrieval_seconds = time.perf_counter() - t0
                    pairs = [{'a_id': r.a_id, 'b_id': r.b_id, 'label': float((r.a_id, r.b_id) in known),
                        'split': partitions[0][r.a_id]} for r in retrieved
                        if eligible_supervised_pair(r.a_id, r.b_id, *partitions)]
                    assert all(partitions[0][p['a_id']] == partitions[1][p['b_id']] == 'train'
                               for p in pairs if p['split'] == 'train')
                    labels = spark.createDataFrame(pairs, 'a_id string, b_id string, label double, split string')
                    train, valid = labels.filter("split = 'train'"), labels.filter("split = 'valid'")
                    valid_truth = {pair: 1. for pair in positive_valid}
                    valid_truth.update({(p['a_id'], p['b_id']): p['label'] for p in pairs if p['split'] == 'valid'})
                    groups = {pair: pair[0] for pair in valid_truth}
                    eligible = candidate_frame.join(labels.select('a_id', 'b_id'), ['a_id', 'b_id'], 'semi')
                    t0 = time.perf_counter()
                    vectors = cm.materialize(features.build(eligible, left, right, cfg), 'vectors', truncate=True)
                    model = matcher.train(vectors, train, cfg)
                    fit_seconds = time.perf_counter() - t0
                    t0 = time.perf_counter()
                    validation = vectors.join(valid.select('a_id', 'b_id'), ['a_id', 'b_id'], 'semi')
                    scores = [(r.a_id, r.b_id, r.p) for r in matcher.score(validation, model).select('a_id', 'b_id', 'p').collect()]
                    score_seconds = time.perf_counter() - t0
                    options = []
                    for policy in ('one_to_one', 'many_to_one', 'unrestricted'):
                        threshold = tune(scores, valid_truth, groups, policy)
                        metrics, grouped = evaluate(select(scores, threshold, policy), valid_truth, groups)
                        # Anchors with no retrieved pairs must remain in bootstrap draws.
                        grouped.update({key: [0, 0, 0, 0] for key in valid_anchors - grouped.keys()})
                        reference = grouped if reference is None else reference
                        options.append({'method': method, 'cardinality': policy, 'threshold': threshold,
                            **metrics, **bootstrap(grouped, reference)})
                    chosen = max(options, key=lambda row: row['f1'])
                    frozen_raw = deepcopy(cfg.data)
                    frozen_raw['decision'] = {'threshold': chosen['threshold'], 'cardinality': chosen['cardinality']}
                    frozen = from_dict(frozen_raw)
                    consumed = train.select('a_id', 'b_id', 'label').collect()
                    example = tracking.pair_snapshot(eligible.orderBy('a_id', 'b_id').limit(5), raw_left, raw_right, cfg)
                    model_record = tracking.log_composite(model, frozen, labels=consumed, input_example=example,
                        experiment='zr3-linkage-candidates', staging_root=out / 'staging', idf_path=idf_path,
                        candidate_state_path=str(state_path) if blocking.needs_state(frozen) else None,
                        metrics={'validation_f1': chosen['f1']})
                    decisions = select(scores, chosen['threshold'], chosen['cardinality'])
                    prediction_frame = pd.DataFrame([(a, b, (a, b) in decisions) for a, b, _ in scores],
                        columns=['a_id', 'b_id', 'is_link'])
                    with mlflow.start_run(run_id=model_record['run_id']):
                        evaluation = tracking.evaluate_pairs(prediction_frame,
                            [{'a_id': a, 'b_id': b, 'label': y} for (a, b), y in valid_truth.items()])
                    assert abs(evaluation['pairwise_f1'] - chosen['f1']) < 1e-12
                    found = {(r.a_id, r.b_id) for r in retrieved}
                    for row in options:
                        row.update(candidate_recall=len(positive_valid & found) / len(positive_valid),
                            budget=budget, retrieval_seconds=retrieval_seconds,
                            feature_fit_seconds=fit_seconds, score_seconds=score_seconds,
                            model=model_record, frozen_config=frozen.data)
                    report['rows'].extend(options)
                    path = out / (method + '.predictions.json')
                    path.write_text(json.dumps({'scores': scores,
                        'labels': [[a, b, y, a] for (a, b), y in valid_truth.items()],
                        'validation_anchors': sorted(valid_anchors)}) + '\n')
                    files.add(path)
                    simple = [(r.a_id, r.b_id, r.cos) for r in retrieved if r.a_id in valid_anchors]
                    for name, threshold, policy in (('nearest_neighbour', 0., 'many_to_one'),
                        ('cosine_threshold', tune(simple, valid_truth, groups, 'one_to_one'), 'one_to_one')):
                        metrics, grouped = evaluate(select(simple, threshold, policy), valid_truth, groups)
                        grouped.update({key: [0, 0, 0, 0] for key in valid_anchors - grouped.keys()})
                        report['baselines'].append({'method': method, 'name': name, 'threshold': threshold,
                            'cardinality': policy, **metrics, **bootstrap(grouped)})
                for row in options:
                    row['method_seconds_including_log_cleanup'] = time.perf_counter() - method_start
                save()
                print(json.dumps({'method': method, 'validation_f1': chosen['f1'], 'threshold': chosen['threshold']}), flush=True)
        report.update(status='completed', cleanup='succeeded')
    except Exception as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        try:
            spark.stop()
        finally:
            report['wall_seconds_including_spark'] = time.perf_counter() - started
            save()
            with tarfile.open(archive, 'w:gz') as bundle:
                for path in sorted(files | {output}):
                    bundle.add(path, arcname=str(path.relative_to(out)))


if __name__ == '__main__':
    main()
