#!/usr/bin/env python3
"""Fresh app + workflow wheels, without repository-source imports or Spark."""
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
import zipfile

from evidence import ROOT, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--junit-dir', type=Path)
    parser.add_argument('--python', choices=['3.11', '3.12'], action='append')
    parser.add_argument('--payload', type=Path, help='Install the complete generated deployment payload')
    args = parser.parse_args()
    if args.report and args.report.exists() or args.junit_dir and args.junit_dir.exists():
        parser.error('Use fresh evidence paths')
    if args.junit_dir:
        args.junit_dir.mkdir(parents=True)
    started, base = time.monotonic(), None
    report = {'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat(),
              'network': 'offline dependency caches only', 'runtimes': [], 'commands': []}
    def run(command, *, env, cwd=ROOT, timeout=90):
        result = subprocess.run([str(x) for x in command], cwd=cwd, env=env, timeout=timeout,
                                capture_output=True, text=True)
        report['commands'].append({'command': [str(x) for x in command], 'exit_code': result.returncode})
        if result.returncode:
            print(result.stdout, result.stderr, file=sys.stderr)
            raise RuntimeError('Required runtime preparation or check failed')
        return result.stdout
    try:
        with tempfile.TemporaryDirectory(prefix='lm-runtime-') as directory:
            base = Path(directory).resolve()
            env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
            env.update(UV_OFFLINE='1', PYTHONNOUSERSITE='1', LAKEMATCH_TEST_POSTGRES='1')
            if args.payload:
                payload = args.payload.resolve()
                saved = json.loads((payload/'payload.json').read_text())
                assert all(sha256(payload/p) == v['sha256'] for p, v in saved['files'].items())
                report['payload_sha256'] = sha256(payload/'payload.json')
                wheels = sorted((payload/'app/wheels').glob('*.whl'))
            else:
                for project in ('app', 'runtime'):
                    run(['uv', 'build', ROOT/project, '--wheel', '--out-dir', base/'wheels'], env=env)
                wheels = sorted((base/'wheels').glob('*.whl'))
            assert len(wheels) == 2
            report['wheels'] = [{'name': p.name, 'sha256': sha256(p), 'bytes': p.stat().st_size} for p in wheels]
            # The portable source is copied byte-for-byte, not transformed.
            runtime = next(p for p in wheels if p.name.startswith('lakematch_workflow_runtime-'))
            with zipfile.ZipFile(runtime) as archive:
                source = {n: __import__('hashlib').sha256(archive.read(n)).hexdigest()
                          for n in archive.namelist() if n.startswith('lakematch/') and n.endswith('.py')}
                assert all(sha256(ROOT/'src'/n) == h for n, h in source.items())
                report['portable_source_hashes'] = source
            for version in args.python or ['3.11', '3.12']:
                target = base/('python-'+version)
                current = {**env, 'UV_PROJECT_ENVIRONMENT': str(target)}
                python = target/'bin/python'
                if args.payload:
                    run(['uv', 'venv', target, '--python', version, '--no-project'], cwd=base, env=current)
                    run(['uv', 'pip', 'install', '--python', python, '--require-hashes', '-r', 'requirements.txt'],
                        cwd=payload/'app', env=current)
                else:
                    run(['uv', 'sync', '--project', ROOT/'app', '--frozen', '--no-install-project',
                         '--python', version], env=current)
                    run(['uv', 'pip', 'install', '--python', python, '-r', ROOT/'requirements-postgres.lock',
                         '-r', ROOT/'runtime/requirements-yaml.lock', *wheels], env=current)
                run(['uv', 'pip', 'check', '--python', python], env=current)
                check = '''
from pathlib import Path
from importlib.metadata import version,PackageNotFoundError
import importlib, json,sys
base=Path(sys.argv[1]).resolve()
names=['lakematch','lakematch.mastering.workflow_api','lakematch_runtime.app','lakematch_review.backend.app']
paths={n:Path(importlib.import_module(n).__file__).resolve() for n in names}
assert all(p.is_relative_to(base) for p in paths.values()), paths
for forbidden in ['pyspark','mlflow','lakematch']:
    try: version(forbidden)
    except PackageNotFoundError: pass
    else: raise AssertionError('Unexpected engine dependency: '+forbidden)
assert not any(n.startswith(('pyspark','mlflow')) for n in sys.modules)
print(json.dumps({'python':sys.version.split()[0],'imports':{n:str(p) for n,p in paths.items()},
'versions':{n:version(n) for n in ['lakematch-workflow-runtime','fastapi','databricks-sdk','psycopg']}}))
'''
                info = json.loads(run([python, '-c', check, target], cwd=base, env=current))
                if args.payload:
                    # Add only the test harness after the production install/import check.
                    run(['uv', 'pip', 'install', '--python', python, 'pytest==9.1.1', 'httpx==0.28.1'], env=current)
                junit = ((args.junit_dir.resolve() if args.junit_dir else base)/('python-'+version+'.xml'))
                output = run([python, '-m', 'pytest', '-q', ROOT/'app/tests',
                    ROOT/'app/acceptance/test_workflow_access.py', ROOT/'runtime/tests', '--junitxml='+str(junit)],
                    cwd=base, env=current, timeout=120)
                suites = list(ET.parse(junit).getroot().iter('testsuite'))
                info['tests'] = {k: sum(int(s.attrib[k]) for s in suites) for k in ('tests', 'failures', 'errors', 'skipped')}
                assert all(info['tests'][k] == 0 for k in ('failures', 'errors', 'skipped'))
                report['runtimes'].append(info)
                print(version+': '+output.strip().splitlines()[-1], flush=True)
        assert not base.exists()
        report.update(status='passed', cleanup='owned wheel/runtime directories removed; private database cleanup asserted')
    except Exception as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}',
                      cleanup='owned runtime removed' if base and not base.exists() else 'not confirmed')
    finally:
        report.update(ended_at=datetime.now(timezone.utc).isoformat(), wall_seconds=round(time.monotonic()-started, 3))
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps({k: report.get(k) for k in ('status', 'cleanup', 'error')}), flush=True)
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())
