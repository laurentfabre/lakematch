#!/usr/bin/env python3
"""Execute the predeclared LF-C slot-4 local payload acceptance."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

from evidence import ROOT, sha256


def main():
    bench = ROOT/'bench/lakefusion'
    output = bench/'runtime-20260923.json'
    junit = bench/'runtime-root-tests-20260923.xml'
    matrix = bench/'runtime-matrix-20260923.json'
    tests = bench/'runtime-tests-20260923'
    if any(p.exists() for p in (output, junit, matrix, tests)):
        raise SystemExit('Fresh acceptance paths required')
    started, base = time.monotonic(), None
    report = {'phase': 'LF-C', 'slot': 4, 'status': 'running', 'cloud_calls': 0,
        'started_at': datetime.now(timezone.utc).isoformat(), 'confirmation_materialized': False,
        'platform_oauth_tls': 'simulated; not live qualification', 'commands': [], 'cleanup': 'not started'}
    def preserved():
        for filename, key, label in [('spec/lakefusion/frozen/phase-a-v0.1.json', 'files', 'frozen_files_verified'),
            ('bench/lakefusion/runtime-inputs-20260923.json', 'scanner_inputs', 'scanner_inputs_verified')]:
            hashes = json.loads((ROOT/filename).read_text())[key]
            assert all(sha256(ROOT/p) == h for p, h in hashes.items()), label
            report[label] = len(hashes)
    def run(command, *, cwd=ROOT, timeout=180):
        result = subprocess.run([str(x) for x in command], cwd=cwd, env={**os.environ,
            'UV_OFFLINE': '1', 'LAKEMATCH_TEST_POSTGRES': '1'}, timeout=timeout)
        report['commands'].append({'command': [str(x) for x in command], 'exit_code': result.returncode})
        if result.returncode:
            raise RuntimeError('Required runtime acceptance step failed')
    try:
        preserved()
        sources = [p for folder in ('runtime', 'src/lakematch/mastering', 'app/migrations/mastering',
            'app/src/lakematch_review/backend', 'app/tests', 'tests/postgres') for p in (ROOT/folder).rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py', '.sql', '.json', '.toml', '.lock', '.in'}]
        sources += list((ROOT/'tests').glob('test_mastering_*.py'))
        sources += [ROOT/p for p in ('src/lakematch/__init__.py', 'src/lakematch/config.py',
            'app/pyproject.toml', 'app/uv.lock', 'app/package.json', 'app/bun.lock',
            'app/src/lakematch_review/ui/lib/api.ts', 'app/acceptance/test_workflow_access.py',
            'app/build_deploy.py', 'tools/build_workflow_bundle.py', 'tools/run_workflow_runtime_tests.py',
            'tools/lakefusion_runtime_run.py', 'tools/check_changes.py', 'tools/local_postgres.py',
            'requirements-postgres.lock', 'bench/lakefusion/RUNTIME_PLAN.md', 'bench/lakefusion/runtime-inputs-20260923.json')]
        report['source_hashes'] = {str(p.relative_to(ROOT)): sha256(p) for p in sources}
        with tempfile.TemporaryDirectory(prefix='lm-payload-accept-') as directory:
            base = Path(directory).resolve()
            payload = base/'bundle'
            run([sys.executable, 'tools/build_workflow_bundle.py', '--output', payload,
                '--binding', 'runtime/binding.example.json', '--warehouse-id', 'synthetic-warehouse',
                '--review-schema', 'synthetic_catalog.fixture'], timeout=480)
            report['payload'] = json.loads((payload/'payload.json').read_text())
            assert not list((payload/'app').rglob('.gitignore'))
            run(['node', 'node_modules/typescript/bin/tsc', '--noEmit'], cwd=ROOT/'app', timeout=60)
            run([ROOT/'app/.venv/bin/ty', 'check'], cwd=ROOT/'app', timeout=60)
            root_tests = [*sorted(str(p.relative_to(ROOT)) for p in (ROOT/'tests').glob('test_mastering_*.py')),
                          'tests/test_config.py', 'tests/test_publication.py', 'tests/test_source_hygiene.py',
                          'tests/test_source_scan.py', 'tests/postgres']
            run([sys.executable, '-m', 'pytest', '-q', *root_tests, '--junitxml='+str(junit)])
            suites = list(ET.parse(junit).getroot().iter('testsuite'))
            report['tests'] = {k: sum(int(s.attrib[k]) for s in suites) for k in ('tests', 'failures', 'errors', 'skipped')}
            assert report['tests']['tests'] >= 492 and not any(report['tests'][k] for k in ('failures', 'errors', 'skipped'))
            run([sys.executable, 'tools/run_workflow_runtime_tests.py', '--payload', payload,
                 '--report', matrix, '--junit-dir', tests], timeout=300)
            matrix_report = json.loads(matrix.read_text())
            assert matrix_report['status'] == 'passed' and len(matrix_report['runtimes']) == 2
            report['runtimes'] = matrix_report['runtimes']
            assert all(r['tests']['tests'] >= 111 for r in report['runtimes'])
            report['runtime_cleanup'] = matrix_report['cleanup']
        assert not base.exists()
        report['cleanup'] = 'owned payload removed; private database and isolated runtime cleanup asserted'
        preserved()
        changed = [p for p, h in report['source_hashes'].items() if sha256(ROOT/p) != h]
        assert not changed, f'Source changed during acceptance: {changed}'
        scale = 1 if sys.platform == 'darwin' else 1024
        report['peak_rss_bytes'] = {'parent': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*scale,
            'highest_child': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*scale}
        assert max(report['peak_rss_bytes'].values()) < 4*1024**3
        report['status'] = 'passed'
    except Exception as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
    finally:
        report.update(ended_at=datetime.now(timezone.utc).isoformat(), wall_seconds=round(time.monotonic()-started, 3))
        output.write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps({k: report.get(k) for k in ('status', 'tests', 'cleanup', 'error')}), flush=True)
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())
