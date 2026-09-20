#!/usr/bin/env python3
"""Finite sequential execution of every specified public/synthetic corpus.

This command executes experiments. Reporters and verify_zr.sh never invoke it.
No remote compute, downloads, model selection or automatic failed-run retries.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from evidence import ROOT, sha256


def scale_retry_blocker(ledger):
    """The campaign has not authorized repeating its failed million-row tier."""
    for line in reversed(ledger.read_text().splitlines()):
        event = json.loads(line)
        if event['kind'] == 'scale-1000000' and event['status'] != 'passed':
            return {'reason': 'The failed million-record tier requires an explicit revised plan before retrying',
                    'retained_run_id': event['run_id'], 'manifest': event['manifest']}
    return None


def stages():
    p = sys.executable
    return [
        ('eight_frozen_linkage_corpora', [p, 'tools/run_compatibility.py']),
        ('febrl4_original', [p, 'tools/experiment.py', '--phase', 'ZR-3', '--kind', 'original-febrl',
            '--hypothesis', 'Frozen selected pipeline and independent nearest-neighbour baseline characterize original FEBRL',
            '--baseline', 'Nearest neighbour without classifier', '--dataset', 'Exposed public synthetic FEBRL4 original 5000x5000',
            '--primary-metric', 'Diagnostic F1, candidate recall and startup-inclusive latency', '--timeout', '600',
            '--artifact', 'data/original_febrl/report.json', '--artifact', 'data/original_febrl/original-evidence.tar.gz',
            '--artifact', 'bench/source_compatibility.json', '--artifact', 'bench/freeze.json',
            '--', '/usr/bin/sandbox-exec', '-f', 'tools/offline.sb', p, 'tools/run_original_febrl.py']),
        ('febrl3_and_historical_native', [p, 'tools/cluster_sweep.py', 'native', '--estimator', 'gbt', '--replay']),
        ('synthetic_scale_ladder', [p, 'tools/final_sweep.py', '--section', 'scale']),
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', action='store_true', help='Print commands; do not execute or claim acceptance')
    args = parser.parse_args()
    if args.plan:
        print(json.dumps({'status': 'plan_only', 'stages': stages(),
            'known_limit': 'The previous 1,000,000-record tier exhausted the fixed JVM heap; no automatic retry is authorized by the current goal.'}, indent=2))
        return 0
    from compatibility import validate
    from frozen import load_freeze
    validate(load_freeze())
    report = {'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat(),
        'declaration_sha256': sha256(ROOT / 'bench/source_compatibility.json'), 'stages': []}
    path = ROOT / 'bench/campaign_execution.json'
    env = {**os.environ, 'JAVA_HOME': str(ROOT / '.tools/jdk/jdk-17.0.20.1+1/Contents/Home'),
        'PYSPARK_PYTHON': sys.executable, 'SPARK_LOCAL_IP': '127.0.0.1'}
    try:
        for name, command in stages():
            item = {'name': name, 'command': command, 'started_at': datetime.now(timezone.utc).isoformat()}
            report['stages'].append(item)
            path.write_text(json.dumps(report, indent=2) + '\n')
            if name == 'synthetic_scale_ladder':
                blocked = scale_retry_blocker(ROOT / 'experiments/runs.jsonl')
                if blocked:
                    item.update(status='blocked', **blocked)
                    report['status'] = 'blocked'
                    print(json.dumps(blocked), file=sys.stderr)
                    return 2
            result = subprocess.run(command, cwd=ROOT, env=env)
            item.update(exit_code=result.returncode, ended_at=datetime.now(timezone.utc).isoformat())
            if result.returncode:
                report['status'] = 'failed'
                return result.returncode
        report['status'] = 'completed'
        return 0
    except BaseException as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        report['ended_at'] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(report, indent=2) + '\n')
        # Render even on failure so missing/failed tiers remain visible.
        for command in ('tools/report_final.py', 'tools/report_clusters.py'):
            subprocess.run([sys.executable, command], cwd=ROOT, env=env, check=False)


if __name__ == '__main__':
    sys.exit(main())
