#!/usr/bin/env python3
"""Sequential corpus experiments under the frozen clustering plan."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['splink', 'native'])
    parser.add_argument('--corpus', choices=['febrl3', 'historical_50k'], action='append')
    parser.add_argument('--estimator', choices=['gbt', 'logistic_regression', 'random_forest'])
    args = parser.parse_args()
    if args.mode == 'native' and not args.estimator:
        parser.error('Native comparison requires the selected estimator')
    env = {**os.environ, 'JAVA_HOME': str(Path('.tools/jdk/jdk-17.0.20.1+1/Contents/Home').resolve()),
        'PYSPARK_PYTHON': sys.executable, 'SPARK_LOCAL_IP': '127.0.0.1',
        'MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR': 'false', 'MLFLOW_ENABLE_TELEMETRY': 'false',
        'MLFLOW_DISABLE_AGENT_HINT': 'true'}
    for corpus in args.corpus or ['febrl3', 'historical_50k']:
        splink = args.mode == 'splink'
        root = f'data/{"splink" if splink else "clusters"}/{corpus}'
        command = [sys.executable, 'tools/experiment.py', '--phase', 'ZR-4',
            '--kind', ('splink-' if splink else 'cluster-') + corpus,
            '--hypothesis', ('A training-only supervised Splink model establishes a measured clustering baseline on disjoint validation entities'
                if splink else 'Four convergent clusterers differ in validation pairwise and B-cubed F1 on the same frozen scored graph'),
            '--dataset', corpus, '--baseline', 'connected_components',
            '--primary-metric', 'Validation clustering pairwise F1; B-cubed secondary; paired entity bootstrap',
            '--timeout', '600' if splink else '900', '--seed', '0', '--seed', '2026091901', '--seed', '2026091902',
            '--artifact', root + '/report.json',
            '--artifact', root + ('/splink-evidence.tar.gz' if splink else '/cluster-evidence.tar.gz'),
            '--', '/usr/bin/sandbox-exec', '-f', 'tools/offline.sb',
            str(Path('.tools/splink-env/bin/python').absolute()) if splink else sys.executable,
            'tools/run_splink_cluster.py' if splink else 'tools/run_clusters.py', corpus]
        if not splink:
            command += ['--estimator', args.estimator]
        result = subprocess.run(command, env=env)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == '__main__':
    sys.exit(main())
