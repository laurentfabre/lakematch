#!/usr/bin/env python3
"""Exercise fresh-process cluster publication against sealed identity evidence."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import time

import pyarrow.parquet as pq
import yaml

from lakematch.publication import current
from evidence import ROOT, sha256
from offline_run import assert_offline
from run_identity_increment import mutate


def read_rows(root, name):
    # Read the Spark Parquet directory without starting another Spark process.
    return pq.ParquetDataset(Path(root) / name).read().to_pylist()


def main():
    assert_offline()
    started = time.perf_counter()
    index = json.loads(Path('bench/identity_index.json').read_text())['runs']['febrl3']
    manifest = json.loads((ROOT / index['manifest']).read_text())
    artifacts = {Path(row['path']).name: row for row in manifest['artifacts']}
    for item in artifacts.values():
        assert sha256(ROOT / item['path']) == item['sha256']
    reference = json.loads((ROOT / artifacts['report.json']['path']).read_text())
    with tarfile.open(ROOT / artifacts['identity-evidence.tar.gz']['path']) as archive:
        before, after = [json.load(archive.extractfile(name + '.json')) for name in ('before', 'after')]
    root = Path('data/cluster_cli').resolve()
    root.mkdir(parents=True, exist_ok=True)
    records = [json.loads(line) for line in Path('data/bench/febrl3/records.jsonl').read_text().splitlines()]
    records = [row for row in records if row['split'] == 'valid']
    changed, mutation = mutate(records, reference['config']['entity']['fields'], 'febrl3')
    assert mutation == reference['mutation']
    # A unique experiment-owned output root makes repeat invocations independent.
    from uuid import uuid4
    output = root / uuid4().hex
    config = deepcopy(reference['config'])
    config['input'].update(format='json', labels=None, validation_labels=None)
    config['output']['root'] = str(output)
    config['cluster']['method'] = reference['method']
    cli_runs = []
    def run(rows, batch):
        path = root / ('before.jsonl' if rows is records else 'after.jsonl')
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        config['input']['left'] = str(path)
        config_path = root / 'config.yaml'
        config_path.write_text(yaml.safe_dump(config, sort_keys=False))
        t0 = time.perf_counter()
        completed = subprocess.run([sys.executable, '-m', 'lakematch.cli', 'cluster',
            '--config', str(config_path), '--model-uri', reference['model']['model_uri'],
            '--batch-id', batch, '--pair-metadata', 'gram_cosine'], text=True, capture_output=True, timeout=180)
        (root / (batch + '.stderr.txt')).write_text(completed.stderr)
        if completed.returncode:
            print(completed.stderr, file=sys.stderr)
            raise RuntimeError(f'cluster CLI {batch} failed ({completed.returncode})')
        result = json.loads(completed.stdout)
        cli_runs.append({'batch_id': batch, 'seconds': time.perf_counter() - t0,
                         'reused': result['publication']['reused']})
        return result['publication']
    def equal(expected, published):
        columns = ['rec_id', 'mdm_id', 'record_digest', 'canonical_key']
        return sorted(tuple(row[key] for key in columns) for row in expected) == sorted(
            tuple(row[key] for key in columns) for row in read_rows(published['root'], 'crosswalk'))
    original = run(records, 'original')
    assert equal(before, original)
    incremental = run(changed, 'incremental')
    assert equal(after, incremental)
    retried = run(changed, 'incremental')
    assert retried['reused'] and retried['root'] == incremental['root']
    unchanged = run(changed, 'unchanged')
    assert equal(after, unchanged)
    assert read_rows(unchanged['root'], 'cluster_events') == []
    assert {row['change'] for row in read_rows(unchanged['root'], 'changes')} == {'unchanged'}
    historical = run(records, 'original')
    assert historical['reused'] and historical['root'] == original['root']
    assert current(output)['batch_id'] == 'unchanged'
    with sqlite3.connect(output / 'commits.sqlite') as connection:
        commits = connection.execute('SELECT count(*) FROM commits').fetchone()[0]
    assert commits == 3
    report = {'status': 'completed', 'cleanup': 'succeeded', 'iteration': 7,
        'identity_reference_run': index['run_id'], 'model': reference['model'], 'config': config,
        'crosswalk_equivalence': True, 'incremental_repeat_idempotent': True,
        'historical_retry_does_not_rewind': True, 'commits': commits, 'cli_runs': cli_runs,
        'confirmation_scored': False, 'wall_seconds': time.perf_counter() - started,
        'publications': {name: body for name, body in [('original', original), ('incremental', incremental), ('unchanged', unchanged)]}}
    (root / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    with tarfile.open(root / 'publication-evidence.tar.gz', 'w:gz') as archive:
        for name, body in report['publications'].items():
            for relative in body['files']:
                path = Path(body['root']) / relative
                assert sha256(path) == body['files'][relative]
                archive.add(path, arcname=f'{name}/{relative}')
        archive.add(root / 'report.json', arcname='report.json')
    print(json.dumps({'status': 'completed', 'commits': commits, 'cli_runs': cli_runs}))


if __name__ == '__main__':
    main()
