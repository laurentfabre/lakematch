#!/usr/bin/env python3
"""Fresh normal-CLI full-universe FEBRL scoring after the model freeze."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import time

import pyarrow.parquet as pq
import yaml

from lakematch.benchmark.corpora import febrl4
from lakematch.benchmark.metrics import bootstrap, evaluate, select
from evidence import ROOT, sha256
from offline_run import assert_offline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('variant', choices=['all', 'no_ssn'])
    args = parser.parse_args()
    assert_offline()
    freeze_path = ROOT / 'bench/freeze.json'
    frozen = json.loads(freeze_path.read_text())
    assert frozen['status'] == 'frozen_before_confirmation' and frozen['seed'] == 2026091901
    corpus = febrl4(args.variant)
    corpus_manifest = corpus.freeze()
    entry = frozen['models'][corpus.name]
    assert sha256(ROOT / entry['selection_report']) == entry['selection_report_sha256']
    out = (ROOT / 'data/frozen_linkage' / corpus.name).resolve()
    out.mkdir(parents=True, exist_ok=True)
    config = deepcopy(entry['config'])
    config['input'].update(format='json', labels=None, validation_labels=None)
    for side, rows in [('left', corpus.left), ('right', corpus.right)]:
        path = out / (side + '.jsonl')
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        config['input'][side] = str(path)
    config['output']['root'] = str(out / 'output')
    config['model']['path'] = str(out / 'model')
    pointer = out / 'frozen-model.json'
    pointer.write_text(json.dumps({**entry['model'], 'tracking_uri': config['mlflow']['tracking_uri'],
                                  'benchmark_only': True, 'accepted': False}) + '\n')
    config['model']['pointer'] = str(pointer)
    config_path = out / 'config.yaml'
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    t0 = time.perf_counter()
    result = subprocess.run([sys.executable, '-m', 'lakematch.cli', 'run', '--config', str(config_path), '--save-scores'],
                            text=True, capture_output=True, timeout=150)
    process_seconds = time.perf_counter() - t0
    (out / 'cli.stdout.txt').write_text(result.stdout)
    (out / 'cli.stderr.txt').write_text(result.stderr)
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f'Frozen linkage CLI failed with exit {result.returncode}')
    metrics = json.loads((out / 'output/metrics.json').read_text())
    assert metrics['cleanup'] == 'succeeded' and not metrics['enabled_paid_features']
    links = pq.ParquetDataset(out / 'output/links').read().to_pylist()
    scores = pq.ParquetDataset(out / 'output/scores').read().to_pylist()
    candidate_keys = {(row['a_id'], row['b_id']) for row in scores}
    found = {(row['a_id'], row['b_id']) for row in links}
    assert len(found) == len(links)
    report = {'status': 'completed', 'cleanup': 'succeeded', 'corpus': corpus.name,
        'freeze_sha256': sha256(freeze_path), 'frozen_model': entry['model'], 'config': config,
        'manifest': json.loads(corpus_manifest.read_text()), 'confirmation_scored': True,
        'process_wall_seconds': process_seconds, 'engine_metrics': metrics,
        'latency_limit_seconds': 60, 'latency_passed': process_seconds < 60,
        'scope': 'complete 5000-left / 2500-right universe; cardinality applied globally before metric partitioning',
        'cost': {'remote_spend': 0, 'live_label_spend': 0}, 'partitions': {}}
    score_path = out / 'all.predictions.json'
    score_path.write_text(json.dumps(scores) + '\n')
    payloads = [score_path]
    selected_report = json.loads((ROOT / entry['selection_report']).read_text())
    baseline_threshold = next(row['threshold'] for row in selected_report['baselines']
        if row['method'] == frozen['method'] and row['name'] == 'cosine_threshold')
    simple_scores = [(row['a_id'], row['b_id'], row['cos']) for row in scores]
    baselines = {'nearest_neighbour': select(simple_scores, 0., 'many_to_one'),
        'cosine_threshold': select(simple_scores, baseline_threshold, 'one_to_one')}
    left_by_id, right_by_id = [{row['rec_id']: row for row in rows} for rows in (corpus.left, corpus.right)]
    for split in ('valid', 'confirmation'):
        anchors = {row['rec_id'] for row in corpus.left if row['split'] == split}
        chosen = {(a, b) for a, b in found if a in anchors}
        positives = {(row['a_id'], row['b_id']) for row in corpus.pairs if row['split'] == split}
        truth = {pair: 1. for pair in positives}
        for pair in chosen:
            truth.setdefault(pair, 0.)
        metric, grouped = evaluate(chosen, truth, {pair: pair[0] for pair in truth})
        grouped.update({key: [0, 0, 0, 0] for key in anchors - grouped.keys()})
        error_slices = {}
        for name, pairs in {
            'given_name_differs': {pair for pair in positives if left_by_id[pair[0]]['given_name'] != right_by_id[pair[1]]['given_name']},
            'any_field_missing': {pair for pair in positives if any(not left_by_id[pair[0]][field] or not right_by_id[pair[1]][field] for field in corpus.fields)},
            'all_positive_links': positives}.items():
            error_slices[name] = {'true_links': len(pairs), 'candidate_misses': len(pairs - candidate_keys),
                'retrieved_but_not_linked': len((pairs & candidate_keys) - chosen), 'true_links_recovered': len(pairs & chosen)}
        baseline_metrics = {}
        for name, all_chosen in baselines.items():
            baseline_chosen = {pair for pair in all_chosen if pair[0] in anchors}
            baseline_truth = {**{pair: 0. for pair in baseline_chosen}, **{pair: 1. for pair in positives}}
            baseline_metric, baseline_groups = evaluate(baseline_chosen, baseline_truth, {pair: pair[0] for pair in baseline_truth})
            baseline_groups.update({key: [0, 0, 0, 0] for key in anchors - baseline_groups.keys()})
            baseline_metrics[name] = {**baseline_metric, **bootstrap(baseline_groups),
                'threshold': baseline_threshold if name == 'cosine_threshold' else 0.}
        report['partitions'][split] = {**metric, **bootstrap(grouped), 'anchors': len(anchors),
            'candidate_recall': len(positives & candidate_keys) / len(positives), 'error_slices': error_slices,
            'baselines': baseline_metrics}
        payload = out / (split + '.predictions.json')
        payload.write_text(json.dumps({'selected': sorted(chosen), 'labels': [[a, b, label, a] for (a, b), label in truth.items()],
                                      'anchors': sorted(anchors)}) + '\n')
        payloads.append(payload)
    target = .97 if args.variant == 'all' else .96
    report['quality_target'] = target
    report['quality_passed'] = report['partitions']['confirmation']['f1'] >= target
    report['acceptance_passed'] = report['quality_passed'] and report['latency_passed']
    report['evidence_files'] = {str(path.relative_to(out)): sha256(path) for path in payloads + [config_path, pointer, out / 'cli.stdout.txt', out / 'cli.stderr.txt']}
    output = out / 'report.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    with tarfile.open(out / 'frozen-evidence.tar.gz', 'w:gz') as archive:
        for name in report['evidence_files']:
            archive.add(out / name, arcname=name)
        archive.add(output, arcname='report.json')
    print(json.dumps({'corpus': corpus.name, 'process_wall_seconds': process_seconds,
                     'confirmation_f1': report['partitions']['confirmation']['f1'], 'acceptance_passed': report['acceptance_passed']}))
    # Measurements are preserved even when a quality or latency gate fails.
    # The read-only verifier, not successful process execution, decides acceptance.


if __name__ == '__main__':
    main()
