#!/usr/bin/env python3
"""Exposed original-FEBRL diagnostic with the selected immutable pair model."""
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

from lakematch.benchmark.metrics import bootstrap, evaluate, select
from evidence import ROOT, sha256
from frozen import load_freeze
from offline_run import assert_offline


def baseline(root):
    from lakematch import candidates, entity
    from lakematch.config import from_dict
    from lakematch.engine import read_records
    from lakematch.runtime import Materializer, create_session, probe
    raw = yaml.safe_load((root / 'config.yaml').read_text())
    raw['candidates']['method'] = 'gram_topk'
    config = from_dict(raw)
    started = time.perf_counter()
    spark = create_session(config)
    try:
        with Materializer(spark, config, probe(spark)) as work:
            frames = [work.materialize(entity.prepare(read_records(spark, config['input'][side], config), config), side)
                      for side in ('left', 'right')]
            plan = candidates.build(*frames, config)
            budget = plan.validate_budget()
            scores = [row.asDict() for row in plan.pairs.select('a_id', 'b_id', 'cos').collect()]
    finally:
        spark.stop()
    (root / 'baseline.json').write_text(json.dumps({'scores': scores, 'candidate_budget': budget,
        'seconds_including_spark': time.perf_counter() - started,
        'definition': 'IDF gram top-k retrieval and nearest-neighbour-only selection; no classifier'}) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline-worker', action='store_true')
    args = parser.parse_args()
    assert_offline()
    root = ROOT / 'data/original_febrl'
    if args.baseline_worker:
        baseline(root)
        return
    started = time.perf_counter()
    frozen = load_freeze('febrl4_half_all')
    entry = frozen['models']['febrl4_half_all']
    root.mkdir(parents=True, exist_ok=True)
    config = deepcopy(entry['config'])
    from recordlinkage.datasets import load_febrl4
    left, right, links = load_febrl4(return_links=True)
    truth = {(str(a), str(b)): 1. for a, b in links}
    for side, frame in [('left', left), ('right', right)]:
        rows = [{'rec_id': str(index), **{name: '' if str(row[name]) == 'nan' else str(row[name])
                 for name in config['entity']['fields']}} for index, row in frame.iterrows()]
        path = root / (side + '.jsonl')
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        config['input'][side] = str(path)
    config['input'].update(format='json', labels=None, validation_labels=None)
    config['output']['root'] = str(root / 'output')
    config['model']['path'] = str(root / 'model')
    config['model']['pointer'] = str(root / 'frozen-model.json')
    (root / 'frozen-model.json').write_text(json.dumps({**entry['model'],
        'tracking_uri': config['mlflow']['tracking_uri'], 'benchmark_only': True, 'accepted': False}) + '\n')
    (root / 'config.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
    t0 = time.perf_counter()
    run = subprocess.run([sys.executable, '-m', 'lakematch.cli', 'run', '--config', str(root / 'config.yaml'),
        '--save-scores'], capture_output=True, text=True, timeout=240)
    seconds = time.perf_counter() - t0
    (root / 'cli.stdout.txt').write_text(run.stdout)
    (root / 'cli.stderr.txt').write_text(run.stderr)
    if run.returncode:
        raise RuntimeError('Original FEBRL CLI failed: ' + run.stderr[-3000:])
    scores = pq.ParquetDataset(root / 'output/scores').read().to_pylist()
    predicted = {(row['a_id'], row['b_id']) for row in pq.ParquetDataset(root / 'output/links').read().to_pylist()}
    process = subprocess.run([sys.executable, __file__, '--baseline-worker'], capture_output=True, text=True, timeout=240)
    (root / 'baseline.stdout.txt').write_text(process.stdout)
    (root / 'baseline.stderr.txt').write_text(process.stderr)
    if process.returncode:
        raise RuntimeError('Original FEBRL nearest-neighbour baseline failed: ' + process.stderr[-3000:])
    simple = json.loads((root / 'baseline.json').read_text())
    selected = select([(r['a_id'], r['b_id'], r['cos']) for r in simple['scores']], 0., 'many_to_one')
    def metrics(chosen):
        labels = {**dict.fromkeys(chosen, 0.), **truth}
        result, groups = evaluate(chosen, labels, {pair: pair[0] for pair in labels})
        return {**result, **bootstrap(groups)}, groups
    model_metrics, model_groups = metrics(predicted)
    baseline_metrics, baseline_groups = metrics(selected)
    payload = {'scores': scores, 'truth': sorted(truth), 'links': sorted(predicted), 'baseline_links': sorted(selected)}
    (root / 'predictions.json').write_text(json.dumps(payload) + '\n')
    report = {'status': 'completed', 'cleanup': 'succeeded', 'corpus': 'febrl4_original',
        'exposure': 'Full exposed original corpus, including historical development anchors; diagnostic only',
        'source': 'recordlinkage 0.16 load_febrl4', 'license': 'BSD-3-Clause distribution, synthetic FEBRL data',
        'confirmation_scored': False, 'frozen_model': entry['model'], 'freeze_sha256': sha256(ROOT / 'bench/freeze.json'),
        'config': config, 'left_records': len(left), 'right_records': len(right), 'true_links': len(truth),
        'metrics': model_metrics, 'candidate_recall': len(set(truth) & {(r['a_id'], r['b_id']) for r in scores}) / len(truth),
        'process_wall_seconds': seconds, 'wall_seconds_including_baseline_and_reporting': time.perf_counter() - started,
        'nearest_neighbour': {**baseline_metrics, **bootstrap(baseline_groups, model_groups),
            'paired_delta_reference': 'baseline minus selected frozen model',
            'candidate_budget': simple['candidate_budget'], 'seconds_including_spark': simple['seconds_including_spark'],
            'definition': simple['definition']}, 'cost': {'remote_spend': 0, 'live_label_spend': 0}}
    names = ['predictions.json', 'baseline.json', 'left.jsonl', 'right.jsonl', 'config.yaml', 'frozen-model.json',
        'cli.stdout.txt', 'cli.stderr.txt', 'baseline.stdout.txt', 'baseline.stderr.txt']
    report['evidence_files'] = {name: sha256(root / name) for name in names}
    (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    with tarfile.open(root / 'original-evidence.tar.gz', 'w:gz') as archive:
        for name in [*names, 'report.json']:
            archive.add(root / name, arcname=name)
    print(json.dumps({'f1': model_metrics['f1'], 'nearest_neighbour_f1': baseline_metrics['f1'], 'seconds': seconds}))


if __name__ == '__main__':
    main()
