#!/usr/bin/env python3
"""Execute the predeclared classifier factorial, one bounded corpus at a time."""
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
    args = parser.parse_args()
    env = {**os.environ, 'JAVA_HOME': str(Path('.tools/jdk/jdk-17.0.20.1+1/Contents/Home').resolve()),
           'PYSPARK_PYTHON': sys.executable, 'SPARK_LOCAL_IP': '127.0.0.1',
           'MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR': 'false', 'MLFLOW_ENABLE_TELEMETRY': 'false',
           'MLFLOW_DISABLE_AGENT_HINT': 'true'}
    for case in args.case or CASES:
        corpus, variant, name = CASES[case]
        command = [sys.executable, 'tools/experiment.py', '--phase', 'ZR-3', '--kind', 'methods-' + case,
            '--hypothesis', 'The predeclared string/estimator factorial measures validation F1 and compatible cardinality policies; all models and resource metrics are preserved without confirmation scoring',
            '--dataset', name, '--baseline', 'levenshtein__gbt', '--primary-metric', 'Validation F1 with paired group bootstrap and macro corpus weighting',
            '--timeout', '900', '--seed', '0', '--seed', '2026091901', '--seed', '2026091902',
            '--artifact', f'data/methods/{name}/report.json', '--artifact', f'data/methods/{name}/methods-evidence.tar.gz',
            '--', '/usr/bin/sandbox-exec', '-f', 'tools/offline.sb', sys.executable, 'tools/run_methods.py', corpus]
        if variant:
            command += ['--febrl-variant', variant]
        result = subprocess.run(command, env=env)
        if result.returncode:
            return result.returncode
        subprocess.run([sys.executable, 'tools/report_methods.py'], env=env, check=True)
        # The report tool has verified every raw event log inside the immutable
        # experiment archive. Remove only this run's duplicate scratch copy.
        report = json.loads(Path(f'data/methods/{name}/report.json').read_text())
        event_root = Path(report['spark_event_root']).resolve()
        if event_root.parent == Path(f'data/methods/{name}/spark-events').resolve():
            shutil.rmtree(event_root)
    return 0


if __name__ == '__main__':
    sys.exit(main())
