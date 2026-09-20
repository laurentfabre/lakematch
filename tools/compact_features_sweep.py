#!/usr/bin/env python3
"""Execute the predeclared compact feature comparison, one bounded corpus at a time."""
import argparse
import os
import json
from pathlib import Path
import shutil
import subprocess
import sys

CASES = {**{'febrl4-' + v: ('febrl4', v, 'febrl4_half_' + v) for v in ('all', 'no_ssn', 'no_ssn_dob')},
         **{name: (name, None, name) for name in ('bpid', 'abt_buy', 'affiliations', 'amazon_google', 'walmart_amazon', 'dblp_acm')}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=CASES, action='append')
    parser.add_argument("--estimator", choices=["gbt", "logistic_regression", "random_forest"], required=True)
    args = parser.parse_args()
    env = {**os.environ, 'JAVA_HOME': str(Path('.tools/jdk/jdk-17.0.20.1+1/Contents/Home').resolve()),
           'PYSPARK_PYTHON': sys.executable, 'SPARK_LOCAL_IP': '127.0.0.1',
           'MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR': 'false', 'MLFLOW_ENABLE_TELEMETRY': 'false',
           'MLFLOW_DISABLE_AGENT_HINT': 'true'}
    for case in args.case or CASES:
        corpus, variant, name = CASES[case]
        command = [sys.executable, 'tools/experiment.py', '--phase', 'ZR-3', '--kind', 'compact-' + case,
            '--hypothesis', 'Two compact native feature sets may preserve macro validation F1 at lower measured cost than all three token families; compare the selected estimator without confirmation scoring',
            '--dataset', name, '--baseline', 'native_all', '--primary-metric', 'Validation F1 with paired group bootstrap and macro corpus weighting',
            '--timeout', '600', '--seed', '0', '--seed', '2026091901', '--seed', '2026091902',
            '--artifact', f'data/compact_features/{name}/report.json', '--artifact', f'data/compact_features/{name}/methods-evidence.tar.gz',
            '--', '/usr/bin/sandbox-exec', '-f', 'tools/offline.sb', sys.executable, 'tools/run_compact_features.py', corpus, '--estimator', args.estimator]
        if variant:
            command += ['--febrl-variant', variant]
        result = subprocess.run(command, env=env)
        if result.returncode:
            return result.returncode
        subprocess.run([sys.executable, 'tools/report_compact_features.py'], env=env, check=True)
        # The report tool has verified every raw event log inside the immutable
        # experiment archive. Remove only this run's duplicate scratch copy.
        report = json.loads(Path(f'data/compact_features/{name}/report.json').read_text())
        event_root = Path(report['spark_event_root']).resolve()
        if event_root.parent == Path(f'data/compact_features/{name}/spark-events').resolve():
            shutil.rmtree(event_root)
    return 0


if __name__ == '__main__':
    sys.exit(main())
