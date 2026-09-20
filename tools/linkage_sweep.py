#!/usr/bin/env python3
"""Run the three declared retrieval/scoring comparisons sequentially."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--features', choices=['native_all', 'idf_only', 'scalar_fields'], required=True)
    parser.add_argument('--estimator', choices=['gbt', 'logistic_regression', 'random_forest'], required=True)
    parser.add_argument('--variant', choices=['all', 'no_ssn', 'no_ssn_dob'], action='append')
    args = parser.parse_args()
    env = {**os.environ, 'JAVA_HOME': str(Path('.tools/jdk/jdk-17.0.20.1+1/Contents/Home').resolve()),
        'PYSPARK_PYTHON': sys.executable, 'SPARK_LOCAL_IP': '127.0.0.1',
        'MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR': 'false', 'MLFLOW_ENABLE_TELEMETRY': 'false',
        'MLFLOW_DISABLE_AGENT_HINT': 'true'}
    for variant in args.variant or ['all', 'no_ssn', 'no_ssn_dob']:
        root = f'data/linkage_candidates/febrl4_half_{variant}'
        command = [sys.executable, 'tools/experiment.py', '--phase', 'ZR-3', '--kind', 'linkage-' + variant,
            '--hypothesis', 'Candidate recall and classifier F1 at identical pair budgets discriminate all five retrievers on the closed-world FEBRL validation tasks',
            '--baseline', 'gram_topk', '--dataset', 'febrl4_half_' + variant,
            '--primary-metric', 'Validation F1 with paired anchor bootstrap; no confirmation scoring',
            '--timeout', '900', '--seed', '0', '--seed', '2026091901', '--seed', '2026091902',
            '--artifact', root + '/report.json', '--artifact', root + '/linkage-evidence.tar.gz',
            '--', '/usr/bin/sandbox-exec', '-f', 'tools/offline.sb', sys.executable,
            'tools/run_linkage_candidates.py', variant, '--features', args.features, '--estimator', args.estimator]
        result = subprocess.run(command, env=env)
        if result.returncode:
            return result.returncode
        subprocess.run([sys.executable, 'tools/report_linkage.py'], env=env, check=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
