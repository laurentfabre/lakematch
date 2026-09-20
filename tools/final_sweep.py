#!/usr/bin/env python3
"""Run the predeclared frozen confirmation/scale iteration sequentially."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from run_candidate_pairs import CORPORA


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--section', choices=['linkage', 'pairs', 'scale', 'all'], default='all')
    args = parser.parse_args()
    env = {**os.environ, 'JAVA_HOME': str(Path('.tools/jdk/jdk-17.0.20.1+1/Contents/Home').resolve()),
        'PYSPARK_PYTHON': sys.executable, 'SPARK_LOCAL_IP': '127.0.0.1',
        'MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR': 'false', 'MLFLOW_ENABLE_TELEMETRY': 'false',
        'MLFLOW_DISABLE_AGENT_HINT': 'true'}
    runs = []
    if args.section in ('all', 'linkage'):
        for variant in ('all', 'no_ssn'):
            runs.append(('frozen-linkage-' + variant, 'data/frozen_linkage/febrl4_half_' + variant,
                'frozen-evidence.tar.gz', 300, ['tools/run_frozen_linkage.py', variant]))
    if args.section in ('all', 'pairs'):
        for corpus in CORPORA:
            runs.append(('frozen-pairs-' + corpus, 'data/frozen_pairs/' + corpus,
                'frozen-evidence.tar.gz', 420, ['tools/run_frozen_pairs.py', corpus]))
    if args.section in ('all', 'scale'):
        for n, timeout in [(1000, 600), (10000, 600), (100000, 900), (1000000, 1800)]:
            runs.append(('scale-' + str(n), 'data/scale/' + str(n), 'scale-evidence.tar.gz', timeout,
                ['tools/run_scale.py', '--records', str(n)]))
    for kind, root, archive, timeout, command in runs:
        result = subprocess.run([sys.executable, 'tools/experiment.py', '--phase', 'ZR-3', '--kind', kind,
            '--hypothesis', 'Frozen validation choice meets confirmation gates and reveals bounded scale limits',
            '--baseline', 'Frozen nearest-neighbour/cosine validation baselines; synthetic exact-duplicate truth',
            '--dataset', kind, '--primary-metric', 'F1, candidate recall, process wall time, pre-top-k join cardinality',
            '--timeout', str(timeout), '--seed', '0', '--seed', '2026091901', '--seed', '2026091902',
            '--artifact', root + '/report.json', '--artifact', root + '/' + archive,
            '--artifact', 'bench/freeze.json', '--', '/usr/bin/sandbox-exec', '-f', 'tools/offline.sb',
            sys.executable, *command], env=env)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == '__main__':
    sys.exit(main())
