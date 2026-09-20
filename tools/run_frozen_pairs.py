#!/usr/bin/env python3
"""Immutable-model confirmation on retrieval-filtered supplied-pair tasks."""
import argparse
import json
from pathlib import Path
import tarfile
import time

import mlflow
import pandas as pd

from lakematch import blocking, candidates, entity, feature_stats, features, matcher, tracking
from lakematch.benchmark.corpora import LOADERS
from lakematch.benchmark.metrics import bootstrap, evaluate, select
from lakematch.config import from_dict
from lakematch.runtime import Materializer, create_session, probe
from evidence import ROOT, sha256
from frozen import load_freeze
from offline_run import assert_offline
from run_candidate_pairs import CORPORA


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('corpus', choices=CORPORA)
    args = parser.parse_args()
    assert_offline()
    started = time.perf_counter()
    freeze_path = ROOT / 'bench/freeze.json'
    freeze = load_freeze(args.corpus)
    entry = freeze['models'][args.corpus]
    assert sha256(ROOT / entry['selection_report']) == entry['selection_report_sha256']
    config = from_dict(entry['config'])
    corpus = LOADERS[args.corpus]()
    manifest = corpus.freeze()
    split = 'test' if any(row['split'] == 'test' for row in corpus.pairs) else 'confirmation'
    truth_rows = [row for row in corpus.pairs if row['split'] == split]
    truth = {(row['a_id'], row['b_id']): row['label'] for row in truth_rows}
    groups = {(row['a_id'], row['b_id']): row['group'] for row in truth_rows}
    out = (ROOT / 'data/frozen_pairs' / corpus.name).resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = {'status': 'running', 'corpus': corpus.name, 'partition': split,
        'confirmation_scored': True, 'freeze_sha256': sha256(freeze_path),
        'frozen_model': entry['model'], 'config': config.data, 'manifest': json.loads(manifest.read_text()),
        'scope': 'retrieval-filtered supplied held-out pairs; unknown pairs excluded; missing positives remain false negatives',
        'cost': {'remote_spend': 0, 'live_label_spend': 0}}
    output = out / 'report.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    spark = create_session(config)
    try:
        capabilities = probe(spark)
        loaded = tracking.load_composite(entry['model']['model_uri'], config).unwrap_python_model()
        model = loaded.native_model(spark)
        state = blocking.load_state(loaded.artifacts['retriever']) if blocking.needs_state(config) else None
        with Materializer(spark, config, capabilities) as work:
            vocabulary = work.materialize(spark.read.parquet(loaded.artifacts['idf']), 'idf')
            schema = 'rec_id string, ' + ', '.join(f'{name} ' + ('array<string>' if spec.get('multiple') else 'string')
                                                 for name, spec in corpus.fields.items())
            frames = [spark.createDataFrame(rows, schema) for rows in (corpus.left, corpus.right)]
            left, right = [work.materialize(feature_stats.attach_idf(entity.prepare(frame, config), vocabulary, config), side)
                           for frame, side in zip(frames, ('left', 'right'))]
            plan = candidates.build(left, right, config, state=state)
            report['candidate_budget'] = plan.validate_budget()
            pairs = work.materialize(plan.pairs, 'candidates')
            held_out = spark.createDataFrame(truth_rows, 'a_id string, b_id string, label double, split string, group string')
            retrieved = pairs.join(held_out.select('a_id', 'b_id'), ['a_id', 'b_id'], 'semi')
            vectors = work.materialize(features.build(retrieved, left, right, config), 'features')
            scored = matcher.score(vectors, model).select('a_id', 'b_id', 'p', 'cos').collect()
            scores = [(row.a_id, row.b_id, row.p) for row in scored]
            decisions = select(scores, config['decision']['threshold'], config['decision']['cardinality'])
            metrics, grouped = evaluate(decisions, truth, groups)
            positives = {pair for pair, label in truth.items() if label}
            found = {(a, b) for a, b, _ in scores}
            report.update(metrics={**metrics, **bootstrap(grouped)}, candidate_recall=len(positives & found) / len(positives),
                candidate_missed_positives=len(positives - found), retrieved_but_not_linked_positives=len((positives & found) - decisions))
            simple = [(row.a_id, row.b_id, row.cos) for row in scored]
            selection_report = json.loads((ROOT / entry['selection_report']).read_text())
            report['baselines'] = {}
            for baseline in selection_report['baselines']:
                if baseline['method'] != freeze['method']:
                    continue
                selected = select(simple, baseline['threshold'], baseline['cardinality'])
                bm, bg = evaluate(selected, truth, groups)
                report['baselines'][baseline['name']] = {**bm, **bootstrap(bg, grouped),
                    'threshold': baseline['threshold'], 'cardinality': baseline['cardinality'],
                    'paired_delta_reference': 'baseline minus frozen classifier'}
            left_by_id, right_by_id = [{row['rec_id']: row for row in rows} for rows in (corpus.left, corpus.right)]
            slices = {'all_positive_links': positives,
                'any_field_missing': {pair for pair in positives if any(not records[pair[side]][field]
                    for side, records in enumerate((left_by_id, right_by_id)) for field in corpus.fields)},
                'unicode': {pair for pair in positives if any(not str(records[pair[side]][field]).isascii()
                    for side, records in enumerate((left_by_id, right_by_id)) for field in corpus.fields)},
                'multi_value': {pair for pair in positives if any(isinstance(records[pair[side]][field], list)
                    for side, records in enumerate((left_by_id, right_by_id)) for field in corpus.fields)}}
            report['error_slices'] = {name: {'true_links': len(items), 'candidate_misses': len(items - found),
                'retrieved_but_not_linked': len((items & found) - decisions), 'true_links_recovered': len(items & decisions)}
                for name, items in slices.items()}
            path = out / 'heldout.predictions.json'
            path.write_text(json.dumps({'scores': scores, 'cosine_scores': simple,
                'labels': [[a, b, y, groups[a, b]] for (a, b), y in truth.items()]}) + '\n')
            mlflow.set_experiment('zr3-frozen-evaluation')
            with mlflow.start_run(run_name=corpus.name) as run:
                mlflow.log_params({'frozen_model_uri': entry['model']['model_uri'], 'freeze_sha256': sha256(freeze_path), 'partition': split})
                evaluation = tracking.evaluate_pairs(pd.DataFrame([(a, b, (a, b) in decisions) for a, b, _ in scores],
                    columns=['a_id', 'b_id', 'is_link']), truth_rows, context='held_out')
                report['evaluation_run_id'] = run.info.run_id
            assert abs(evaluation['pairwise_f1'] - metrics['f1']) < 1e-12
        report.update(status='completed', cleanup='succeeded', evidence_files={path.name: sha256(path)})
    except Exception as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        try:
            spark.stop()
        finally:
            report['wall_seconds_including_spark'] = time.perf_counter() - started
            output.write_text(json.dumps(report, indent=2) + '\n')
            with tarfile.open(out / 'frozen-evidence.tar.gz', 'w:gz') as archive:
                archive.add(output, arcname='report.json')
                for name in report.get('evidence_files', {}):
                    archive.add(out / name, arcname=name)
    print(json.dumps({'corpus': corpus.name, 'f1': report['metrics']['f1'], 'candidate_recall': report['candidate_recall']}))


if __name__ == '__main__':
    main()
