#!/usr/bin/env python3
"""Replay eight frozen models sequentially, without refitting or retuning."""
import os
from pathlib import Path
import subprocess
import sys

from compatibility import DECLARATION, validate
from frozen import load_freeze
from report_final import PAIR_CORPORA


def main():
    freeze = load_freeze()
    validate(freeze)
    env = {**os.environ, 'JAVA_HOME': str(Path('.tools/jdk/jdk-17.0.20.1+1/Contents/Home').resolve()),
        'PYSPARK_PYTHON': sys.executable, 'SPARK_LOCAL_IP': '127.0.0.1',
        'MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR': 'false', 'MLFLOW_ENABLE_TELEMETRY': 'false',
        'MLFLOW_DISABLE_AGENT_HINT': 'true'}
    runs = [('linkage-' + variant, 'data/frozen_linkage/febrl4_half_' + variant, 300,
             ['tools/run_frozen_linkage.py', variant]) for variant in ('all', 'no_ssn')]
    runs += [('pairs-' + name, 'data/frozen_pairs/' + name, 420,
              ['tools/run_frozen_pairs.py', name]) for name in PAIR_CORPORA]
    for suffix, root, timeout, command in runs:
        result = subprocess.run([sys.executable, 'tools/experiment.py', '--phase', 'ZR-3',
            '--kind', 'replay-' + suffix, '--hypothesis', 'Declared integration changes preserve every frozen prediction',
            '--baseline', 'Sealed iteration-7 predictions', '--dataset', suffix,
            '--primary-metric', 'Exact pair/decision identity and probability delta <=1e-12',
            '--timeout', str(timeout), '--artifact', root + '/report.json',
            '--artifact', root + '/frozen-evidence.tar.gz', '--artifact', 'bench/freeze.json',
            '--artifact', str(DECLARATION), '--', '/usr/bin/sandbox-exec', '-f', 'tools/offline.sb',
            sys.executable, *command], env=env)
        if result.returncode:
            return result.returncode
        # Audit immediately, so a semantic discrepancy stops the dependent sweep.
        from report_compatibility import audit_one
        audit_one(suffix)
    return subprocess.run([sys.executable, 'tools/report_compatibility.py'], env=env).returncode


if __name__ == '__main__':
    sys.exit(main())
