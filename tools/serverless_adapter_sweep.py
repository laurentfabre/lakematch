#!/usr/bin/env python3
"""The three predeclared local checks for lazy serverless adapters."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--section', choices=['all', 'native'], default='all')
    args = parser.parse_args()
    env = {**os.environ, 'JAVA_HOME': str(Path('.tools/jdk/jdk-17.0.20.1+1/Contents/Home').resolve()),
        'PYSPARK_PYTHON': sys.executable, 'SPARK_LOCAL_IP': '127.0.0.1',
        'MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR': 'false', 'MLFLOW_ENABLE_TELEMETRY': 'false',
        'MLFLOW_DISABLE_AGENT_HINT': 'true', 'PYTHONPATH': str(Path('.tools/dqx-runtime').resolve())}
    rows = [('dqx-parity', 120, ['tools/check_dqx_offline.py'], 'data/dqx', ['integration/check_dqx.py'])]
    rows += [('native-ml-' + variant, 300, ['tools/check_native_ml.py', variant], 'data/native_ml/' + variant,
              ['data/native_ml/' + variant + '/native-state.json', 'data/native_ml/' + variant + '/native.plan.txt'])
             for variant in ('all', 'no_ssn')]
    if args.section == 'native':
        rows = rows[1:]
    else:
        rows += [('serverless-feature-regression', 120, ['tools/check_serverless_features.py'],
            'data/native_ml', ['data/native_ml/feature-regression.xml'])]
    for kind, timeout, command, out, extras in rows:
        argv = [sys.executable, 'tools/experiment.py', '--phase', 'ZR-6', '--kind', kind,
            '--hypothesis', 'Lazy optional adapters preserve native quality and exact frozen MLlib inference',
            '--baseline', 'Native quality / persisted MLlib MinHash and GBT',
            '--dataset', 'seeded quality rows or FEBRL validation records only',
            '--primary-metric', 'Exact row/key/candidate equality, probability error below 1e-12',
            '--timeout', str(timeout), '--seed', '0', '--seed', '2026091901', '--artifact', out + '/report.json']
        for artifact in extras:
            argv += ['--artifact', artifact]
        result = subprocess.run([*argv, '--', '/usr/bin/sandbox-exec', '-f', 'tools/offline.sb', sys.executable, *command], env=env)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == '__main__':
    sys.exit(main())
