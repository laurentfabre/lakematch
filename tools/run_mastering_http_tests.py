#!/usr/bin/env python3
"""Offline, fresh-wheel APX/worker integration in an owned Python 3.12 runtime.

Prepare caches with the documented uv commands first. This checker never calls
Databricks, starts a public server or installs into either project environment.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

from evidence import sha256

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--junit-output', type=Path)
    parser.add_argument('--report-output', type=Path)
    args = parser.parse_args()
    for path in (args.junit_output, args.report_output):
        if path is not None:
            if path.exists():
                parser.error('Use a fresh evidence path')
            path.parent.mkdir(parents=True, exist_ok=True)
    if sys.version_info[:2] != (3, 12):
        parser.error('Run this check with the root Python 3.12 environment')
    report = {'status': 'running', 'steps': [], 'network': 'offline dependency cache only',
              'started_at': datetime.now(timezone.utc).isoformat()}
    started, base = time.monotonic(), None
    def run(command, *, env=None, timeout=60):
        result = subprocess.run([str(v) for v in command], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=timeout)
        report['steps'].append({'command': [str(v) for v in command], 'exit_code': result.returncode})
        if result.returncode:
            print(result.stdout, result.stderr, file=sys.stderr)
            raise RuntimeError('Required offline HTTP preparation/check failed')
        return result.stdout
    try:
        with tempfile.TemporaryDirectory(prefix='lm-access-http-') as directory:
            base = Path(directory).resolve()
            environment = base/'runtime'
            env = {**os.environ, 'UV_PROJECT_ENVIRONMENT': str(environment), 'UV_OFFLINE': '1'}
            run(['uv', 'sync', '--project', ROOT/'app', '--frozen', '--no-install-project',
                 '--python', sys.executable], env=env)
            python = environment/'bin/python'
            run(['uv', 'pip', 'install', '--python', python, '-r', ROOT/'requirements-postgres.lock',
                 'PyYAML==6.0.3'], env=env)
            run(['uv', 'build', ROOT/'app', '--wheel', '--out-dir', base/'wheels'], env=env)
            wheels = list((base/'wheels').glob('*.whl'))
            if len(wheels) != 1:
                raise RuntimeError('Expected exactly one freshly built app wheel')
            report['wheel'] = {'name': wheels[0].name, 'sha256': sha256(wheels[0]), 'bytes': wheels[0].stat().st_size}
            run(['uv', 'pip', 'install', '--python', python, '--no-deps', wheels[0]], env=env)
            # The worker comes from this repository's explicit source, while
            # the APX app must resolve exclusively from the newly installed wheel.
            test_env = {**env, 'PYTHONPATH': str(ROOT/'src'), 'LAKEMATCH_TEST_POSTGRES': '1'}
            check = '''
from pathlib import Path
from importlib.metadata import version
import hashlib,json,sys
import lakematch_review.backend.app as app
import lakematch_review.backend.mastering as transport
root, runtime = map(Path,sys.argv[1:])
paths={'app':Path(app.__file__).resolve(),'transport':Path(transport.__file__).resolve()}
assert all(p.is_relative_to(runtime) for p in paths.values()), paths
assert hashlib.sha256(paths['transport'].read_bytes()).hexdigest()==hashlib.sha256((root/'app/src/lakematch_review/backend/mastering.py').read_bytes()).hexdigest()
assert version('fastapi')=='0.128.0'
print(json.dumps({'imports':{k:str(v) for k,v in paths.items()},'versions':{p:version(p) for p in ('fastapi','starlette','pydantic','psycopg','pyyaml','pytest')}}))
'''
            report.update(json.loads(run([python, '-c', check, ROOT, environment], env=test_env)))
            junit = args.junit_output.resolve() if args.junit_output else base/'tests.xml'
            output = run([python, '-m', 'pytest', '-q', ROOT/'app/tests',
                          ROOT/'app/acceptance/test_workflow_access.py', '--junitxml='+str(junit)], env=test_env, timeout=90)
            suites = list(ET.parse(junit).getroot().iter('testsuite'))
            report['tests'] = {k: sum(int(s.attrib[k]) for s in suites) for k in ('tests', 'failures', 'errors', 'skipped')}
            if any(report['tests'][k] for k in ('failures', 'errors', 'skipped')):
                raise RuntimeError('Every required HTTP/app test must pass without skips')
            print(output.strip(), flush=True)
        if base.exists():
            raise RuntimeError('Owned HTTP runtime was not removed')
        report.update(status='passed', cleanup='owned HTTP runtime removed; database fixture cleanup asserted')
    except Exception as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}',
                      cleanup='owned HTTP runtime removed' if base is not None and not base.exists() else 'not confirmed')
    finally:
        report.update(ended_at=datetime.now(timezone.utc).isoformat(), wall_seconds=round(time.monotonic()-started, 3))
        if args.report_output:
            args.report_output.write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps({k: report.get(k) for k in ('status', 'tests', 'cleanup', 'error')}), flush=True)
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())
