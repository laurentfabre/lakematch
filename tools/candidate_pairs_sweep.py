#!/usr/bin/env python3
"""The finite six-corpus candidate/classifier validation experiment."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from run_candidate_pairs import CORPORA


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--corpus', choices=CORPORA, action='append')
    args = parser.parse_args()
    env = {**os.environ, 'JAVA_HOME': str(Path('.tools/jdk/jdk-17.0.20.1+1/Contents/Home').resolve()),
        'PYSPARK_PYTHON': sys.executable, 'SPARK_LOCAL_IP': '127.0.0.1',
        'MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR': 'false', 'MLFLOW_ENABLE_TELEMETRY': 'false', 'MLFLOW_DISABLE_AGENT_HINT': 'true'}
    for corpus in args.corpus or CORPORA:
        root = f'data/candidate_pairs/{corpus}'
        result = subprocess.run([sys.executable, 'tools/experiment.py', '--phase', 'ZR-3', '--kind', 'candidate-pairs-' + corpus,
            '--hypothesis', 'Retrieval-filtered supplied-pair validation identifies the feasible macro-F1 candidate winner',
            '--baseline', 'gram_topk when within fixed budgets', '--dataset', corpus,
            '--primary-metric', 'Validation F1 and candidate recall; unknown pairs remain unknown',
            '--timeout', '900', '--seed', '0', '--seed', '2026091901', '--seed', '2026091902',
            '--artifact', root + '/report.json', '--artifact', root + '/candidate-pairs-evidence.tar.gz',
            '--', '/usr/bin/sandbox-exec', '-f', 'tools/offline.sb', sys.executable, 'tools/run_candidate_pairs.py', corpus], env=env)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == '__main__':
    sys.exit(main())
