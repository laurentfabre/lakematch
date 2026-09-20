#!/usr/bin/env python3
"""Retrieval-filtered supplied-pair validation, with unknown pairs left unknown."""
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
from lakematch.benchmark.corpora import LOADERS
from lakematch.benchmark.metrics import bootstrap, evaluate, select, tune
from lakematch.config import from_dict
from lakematch.runtime import Materializer, create_session, probe
from evidence import sha256
from offline_run import assert_offline
from run_methods import policies

CORPORA = ['bpid', 'abt_buy', 'amazon_google', 'walmart_amazon', 'dblp_acm', 'affiliations']
METHODS = ['gram_topk', 'learned_blocker', 'minhash_lsh', 'field_blocks', 'union']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('corpus', choices=CORPORA)
    args = parser.parse_args()
    assert_offline()
    started = time.perf_counter()
    corpus = LOADERS[args.corpus]()
    manifest = corpus.freeze()
    out = (Path('data/candidate_pairs') / corpus.name).resolve()
    out.mkdir(parents=True, exist_ok=True)
    raw = {'entity': {'name': corpus.name, 'fields': corpus.fields},
        'candidates': {'k': 5, 'max_pairs': 100000, 'max_join_rows': 50000000, 'union_of': ['gram_topk', 'field_blocks']},
        'features': {'multi_token': ['idf_token_cosine'], 'embeddings': {'provider': 'none'}},
        'matcher': {'estimator': 'gbt', 'max_iter': 20, 'max_depth': 3, 'seed': 0},
        'decision': {'threshold': .5, 'cardinality': 'unrestricted'},
        'mlflow': {'tracking_uri': f'sqlite:///{out}/mlflow.db', 'experiment': 'zr3-candidate-pairs'}}
    raw['candidates']['field_blocks'] = blocking.proposed_rules(from_dict(raw))
    config = from_dict(raw)
    report = {'status': 'running', 'iteration': 6, 'corpus': corpus.name,
        'manifest': json.loads(manifest.read_text()), 'config': config.data,
        'plan': 'bench/CANDIDATE_PAIRS_PLAN.md', 'confirmation_scored': False,
        'evaluation_scope': 'retrieval-filtered supplied validation pairs; unknown pairs excluded, missing positives are false negatives',
        'unlabelled_pairs_are_negatives': False, 'rows': [], 'outcomes': [], 'baselines': [],
        'cost': {'remote_spend': 0, 'live_label_spend': 0}}
    output = out / 'report.json'
    archive = out / 'candidate-pairs-evidence.tar.gz'
    archive.unlink(missing_ok=True)
    files = set()
    def save():
        report['evidence_files'] = {str(path.relative_to(out)): sha256(path) for path in sorted(files)}
        output.write_text(json.dumps(report, indent=2) + '\n')
    save()
    spark = create_session(config)
    try:
        capabilities = probe(spark)
        with Materializer(spark, config, capabilities) as shared:
            schema = 'rec_id string, ' + ', '.join(f'{name} ' + ('array<string>' if spec.get('multiple') else 'string') for name, spec in corpus.fields.items())
            raw_frames = [spark.createDataFrame(records, schema) for records in (corpus.left, corpus.right)]
            records = [shared.materialize(entity.prepare(frame, config), name) for frame, name in zip(raw_frames, ('left', 'right'))]
            pairs = [row for row in corpus.pairs if row['split'] in {'train', 'valid'}]
            assert len(pairs) <= config['candidates']['max_pairs']
            labels = spark.createDataFrame(pairs, 'a_id string, b_id string, label double, split string, group string')
            train, valid = labels.filter("split = 'train'"), labels.filter("split = 'valid'")
            training_records = [shared.materialize(frame.join(train.select(F.col(key).alias('rec_id')).distinct(), 'rec_id', 'semi'), name)
                for frame, key, name in zip(records, ('a_id', 'b_id'), ('train_left', 'train_right'))]
            vocab = shared.materialize(feature_stats.fit_idf(training_records, config), 'idf')
            idf_path = out / 'idf'
            vocab.write.mode('overwrite').parquet(str(idf_path))
            left, right = [shared.materialize(feature_stats.attach_idf(frame, vocab, config), name, truncate=True)
                           for frame, name in zip(records, ('weighted_left', 'weighted_right'))]
            truth = {(row['a_id'], row['b_id']): row['label'] for row in pairs if row['split'] == 'valid'}
            groups = {(row['a_id'], row['b_id']): row['group'] for row in pairs if row['split'] == 'valid'}
            positives = {pair for pair, label in truth.items() if label}
            reference = None
            for method in METHODS:
                t0 = time.perf_counter()
                print(json.dumps({'corpus': corpus.name, 'method': method, 'status': 'started'}), flush=True)
                cfg = blocking.child_config(config, method)
                state = blocking.prepare_state(*training_records, train, cfg)
                state_path = out / (method + '_state')
                blocking.save_state(state, state_path)
                files.update(path for path in state_path.rglob('*') if path.is_file())
                with Materializer(spark, cfg, capabilities) as work:
                    retrieval_start = time.perf_counter()
                    plan = candidates.build(left, right, cfg, state=state)
                    try:
                        budget = plan.validate_budget()
                    except candidates.CandidateBudgetExceeded as exc:
                        report['outcomes'].append({'method': method, 'status': 'budget_rejected', 'reason': str(exc)})
                        save()
                        continue
                    found = work.materialize(plan.pairs, 'candidates', truncate=True)
                    keys = {(row.a_id, row.b_id) for row in found.select('a_id', 'b_id').collect()}
                    recall = len(keys & positives) / len(positives)
                    retrieval_seconds = time.perf_counter() - retrieval_start
                    consumed = train.join(found.select('a_id', 'b_id'), ['a_id', 'b_id'], 'semi')
                    if {row.label for row in consumed.select('label').distinct().collect()} != {0., 1.}:
                        report['outcomes'].append({'method': method, 'status': 'training_unavailable',
                            'reason': 'Retrieved labelled training pairs do not contain both classes',
                            'candidate_recall': recall, 'budget': budget})
                        save()
                        continue
                    eligible = found.join(labels.select('a_id', 'b_id'), ['a_id', 'b_id'], 'semi')
                    fit_start = time.perf_counter()
                    vectors = work.materialize(features.build(eligible, left, right, cfg), 'vectors', truncate=True)
                    model = matcher.train(vectors, consumed, cfg)
                    fit_seconds = time.perf_counter() - fit_start
                    validation = vectors.join(valid.select('a_id', 'b_id'), ['a_id', 'b_id'], 'semi')
                    scores = [(row.a_id, row.b_id, row.p) for row in matcher.score(validation, model).select('a_id', 'b_id', 'p').collect()]
                    assert all((a, b) in truth for a, b, _ in scores)
                    options = []
                    for policy in policies(pairs, False):
                        threshold = tune(scores, truth, groups, policy)
                        metric, grouped = evaluate(select(scores, threshold, policy), truth, groups)
                        reference = grouped if reference is None else reference
                        options.append({'method': method, 'cardinality': policy, 'threshold': threshold,
                            **metric, **bootstrap(grouped, reference)})
                    selected = max(options, key=lambda row: row['f1'])
                    frozen_raw = deepcopy(cfg.data)
                    frozen_raw['decision'] = {'threshold': selected['threshold'], 'cardinality': selected['cardinality']}
                    frozen = from_dict(frozen_raw)
                    example = tracking.pair_snapshot(eligible.orderBy('a_id', 'b_id').limit(5), *raw_frames, cfg)
                    logged = tracking.log_composite(model, frozen, labels=consumed.select('a_id', 'b_id', 'label').collect(),
                        input_example=example, experiment='zr3-candidate-pairs', staging_root=out / 'staging',
                        idf_path=str(idf_path), candidate_state_path=str(state_path) if blocking.needs_state(cfg) else None,
                        metrics={'validation_f1': selected['f1']})
                    decisions = select(scores, selected['threshold'], selected['cardinality'])
                    prediction = pd.DataFrame([(a, b, (a, b) in decisions) for a, b, _ in scores], columns=['a_id', 'b_id', 'is_link'])
                    with mlflow.start_run(run_id=logged['run_id']):
                        evaluation = tracking.evaluate_pairs(prediction, [{'a_id': a, 'b_id': b, 'label': label} for (a, b), label in truth.items()])
                    assert abs(evaluation['pairwise_f1'] - selected['f1']) < 1e-12
                    for row in options:
                        row.update(candidate_recall=recall, budget=budget, retrieval_seconds=retrieval_seconds,
                                   feature_fit_seconds=fit_seconds, model=logged, frozen_config=frozen.data)
                    path = out / (method + '.predictions.json')
                    path.write_text(json.dumps({'scores': scores, 'labels': [[a, b, y, groups[a, b]] for (a, b), y in truth.items()]}) + '\n')
                    files.add(path)
                    simple = [(row.a_id, row.b_id, row.cos) for row in found.join(valid.select('a_id', 'b_id'), ['a_id', 'b_id'], 'semi').collect()]
                    for name, threshold, policy in [('nearest_neighbour', 0., 'many_to_one'),
                        ('cosine_threshold', tune(simple, truth, groups, selected['cardinality']), selected['cardinality'])]:
                        metric, grouped = evaluate(select(simple, threshold, policy), truth, groups)
                        report['baselines'].append({'method': method, 'name': name, 'threshold': threshold,
                            'cardinality': policy, **metric, **bootstrap(grouped)})
                elapsed = time.perf_counter() - t0
                for row in options:
                    row['method_seconds_including_log_cleanup'] = elapsed
                report['rows'].extend(options)
                report['outcomes'].append({'method': method, 'status': 'completed', 'seconds': elapsed})
                save()
                print(json.dumps({'method': method, 'f1': selected['f1'], 'candidate_recall': recall}), flush=True)
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
