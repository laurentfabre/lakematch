"""Replay all eight frozen corpora into a fresh directory, preserving prior outputs."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from evidence import ROOT, sha256
from frozen import load_freeze
from report_compatibility import compare_scores, sealed


def prepare(destination):
    destination.mkdir(parents=True, exist_ok=False)
    # Copy source bytes unchanged: the existing freeze checks still apply.
    for name in ('src', 'tools', 'bench'):
        shutil.copytree(ROOT / name, destination / name,
                        ignore=shutil.ignore_patterns('__pycache__'))
    data = destination / 'data'
    data.mkdir()
    shutil.copytree(ROOT / 'data/bench', data / 'bench')
    # These are existing inputs/model stores. Replay output directories are absent.
    for name in ('sources', 'frozen_sources', 'frozen_sources.tar.gz',
                 'candidate_pairs', 'linkage_candidates'):
        (data / name).symlink_to(ROOT / 'data' / name)
    for entry in load_freeze()['models'].values():
        target = destination / entry['selection_report']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / entry['selection_report'], target)


def audit(suffix, report, output, freeze):
    event, original, payloads = sealed('frozen-' + suffix, freeze['execution_sources'])
    assert report['status'] == 'completed' and report['cleanup'] == 'succeeded'
    assert report['frozen_model'] == original['frozen_model']
    assert report['freeze_sha256'] == sha256(ROOT / 'bench/freeze.json')
    expected = json.loads(json.dumps(original['config']))
    if suffix.startswith('linkage-'):
        # Only filesystem destinations differ in the isolated replay checkout.
        for section, names in {'input': ('left', 'right'), 'output': ('root',),
                               'model': ('path', 'pointer')}.items():
            for name in names:
                expected[section][name] = report['config'][section][name]
    assert report['config'] == expected, 'Replay changed a model or decision setting'
    for name, digest in report['evidence_files'].items():
        assert sha256(output / name) == digest
    threshold = original['config']['decision']['threshold']
    cardinality = original['config']['decision']['cardinality']
    if suffix.startswith('linkage-'):
        old = payloads['all.predictions.json']
        new = json.loads((output / 'all.predictions.json').read_text())
        deltas = {field: compare_scores(
            [[r['a_id'], r['b_id'], r[field]] for r in old],
            [[r['a_id'], r['b_id'], r[field]] for r in new],
            threshold if field == 'p' else 0., cardinality)
            for field in ('p', 'cos', 'rank', 'gap')}
        assert report['partitions'] == original['partitions']
        metrics = report['partitions']['confirmation']
        duration = report['process_wall_seconds']
    else:
        old = payloads['heldout.predictions.json']
        new = json.loads((output / 'heldout.predictions.json').read_text())
        assert sorted(old['labels']) == sorted(new['labels'])
        deltas = {field: compare_scores(old[field], new[field],
                  threshold if field == 'scores' else 0., cardinality)
                  for field in ('scores', 'cosine_scores')}
        assert report['metrics'] == original['metrics']
        metrics = {**report['metrics'], 'candidate_recall': report['candidate_recall']}
        duration = report['wall_seconds_including_spark']
    return {'case': suffix, 'corpus': report['corpus'], 'original_run': event['run_id'],
            'status': 'passed', 'decisions_identical': True, 'maximum_deltas': deltas,
            'metrics': metrics, 'wall_seconds': duration,
            'quality_passed': report.get('quality_passed'),
            'latency_passed': report.get('latency_passed'),
            'scope': report['scope']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    destination, report_path = args.output.resolve(), args.report.resolve()
    freeze = load_freeze()
    for name in freeze['models']:
        load_freeze(name)
    prepare(destination)
    env = {**os.environ, 'PYTHONPATH': str(destination / 'src'),
           'PYSPARK_PYTHON': sys.executable, 'SPARK_LOCAL_IP': '127.0.0.1',
           'MLFLOW_ENABLE_TELEMETRY': 'false', 'MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR': 'false'}
    cases = [('linkage-' + variant, 'tools/run_frozen_linkage.py', variant,
              'data/frozen_linkage/febrl4_half_' + variant, 300)
             for variant in ('all', 'no_ssn')]
    cases += [('pairs-' + name, 'tools/run_frozen_pairs.py', name,
               'data/frozen_pairs/' + name, 420)
              for name in freeze['models'] if not name.startswith('febrl4_')]
    result = {'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat(),
              'freeze_sha256': sha256(ROOT / 'bench/freeze.json'),
              'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'input_and_model_hashes_verified': len(freeze['models']),
              'output': str(destination), 'results': []}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        for suffix, script, argument, relative_output, timeout in cases:
            print('Replaying ' + suffix, flush=True)
            output = destination / relative_output
            output.mkdir(parents=True)
            with (output / 'runner.stdout.txt').open('w') as out, (output / 'runner.stderr.txt').open('w') as err:
                subprocess.run(['/usr/bin/sandbox-exec', '-f', str(ROOT / 'tools/offline.sb'),
                                sys.executable, script, argument], cwd=destination, env=env,
                               stdout=out, stderr=err, timeout=timeout, check=True)
            assert 'Verified OS denies non-loopback network access' in (output / 'runner.stdout.txt').read_text()
            report = json.loads((output / 'report.json').read_text())
            result['results'].append(audit(suffix, report, output, freeze))
            print(json.dumps(result['results'][-1]), flush=True)
            report_path.write_text(json.dumps(result, indent=2) + '\n')
        result['status'] = 'passed'
    except Exception as error:
        result.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        result['ended_at'] = datetime.now(timezone.utc).isoformat()
        report_path.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
