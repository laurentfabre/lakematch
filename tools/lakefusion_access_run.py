#!/usr/bin/env python3
"""Bounded LF-C access acceptance; generates fresh local evidence only."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from lakematch.mastering.access_contract import AccessDenied
from lakematch.mastering.access_registry import PostgresAccessRegistry, grant_workflow_role
from lakematch.mastering.authorized_workflow import AuthorizedWorkflow
from lakematch.mastering.contracts import DomainContract, digest
from lakematch.mastering.identity_contract import IdentityContext, SourceRef
from lakematch.mastering.identity_registry import PostgresIdentityRegistry
from lakematch.mastering.registry import PostgresRegistry, apply_migrations
from lakematch.mastering.workflow_contract import WorkflowContext
from evidence import sha256
from local_postgres import LocalPostgres

ROOT = Path(__file__).resolve().parents[1]


def preserved():
    frozen = json.loads((ROOT/'spec/lakefusion/frozen/phase-a-v0.1.json').read_text())['files']
    scanner = json.loads((ROOT/'bench/lakefusion/access-inputs-20260923.json').read_text())['scanner_inputs']
    assert all(sha256(ROOT/p) == h for p, h in frozen.items()), 'Frozen Phase A content changed'
    assert all(sha256(ROOT/p) == h for p, h in scanner.items()), 'Scanner input changed'
    return {'frozen_files_verified': len(frozen), 'scanner_inputs_verified': len(scanner)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--slot', type=int, choices=range(2, 9), default=2)
    parser.add_argument('--plan', type=Path, default=Path('bench/lakefusion/ACCESS_PLAN.md'))
    for option in ('output', 'tests-output', 'http-report', 'http-tests'):
        parser.add_argument('--'+option, required=True, type=Path)
    args = parser.parse_args()
    paths = (args.output, args.tests_output, args.http_report, args.http_tests)
    if len({p.resolve() for p in paths}) != len(paths) or any(p.exists() for p in paths):
        parser.error('Distinct fresh evidence paths required')
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
    started, server = time.monotonic(), None
    report = {'phase': 'LF-C', 'slot': args.slot, 'packages': ['LM-007', 'LM-008'], 'status': 'running',
              'started_at': datetime.now(timezone.utc).isoformat(), 'cloud_calls': 0,
              'confirmation_materialized': False, 'platform_ingress': 'simulated; not live authentication proof',
              'cleanup': 'not started', 'commands': []}
    def run(command, *, cwd=ROOT, timeout=180, env=None):
        command = [str(v) for v in command]
        result = subprocess.run(command, cwd=cwd, timeout=timeout, env=env)
        report['commands'].append({'command': command, 'cwd': str(cwd), 'exit_code': result.returncode})
        if result.returncode:
            raise RuntimeError('Required acceptance step failed')
    try:
        report.update(preserved())
        source = [*sorted((ROOT/'src/lakematch/mastering').glob('*.py')),
                  *sorted((ROOT/'app/migrations/mastering').glob('*.sql')),
                  *sorted((ROOT/'app/src/lakematch_review/backend').rglob('*.py')),
                  *sorted((ROOT/'tests/postgres').glob('*.py')),
                  *sorted((ROOT/'tests').glob('test_mastering_*.py')),
                  *sorted((ROOT/'app/tests').glob('*.py')),
                  ROOT/'app/acceptance/test_workflow_access.py', ROOT/'app/src/lakematch_review/ui/lib/api.ts',
                  ROOT/'app/pyproject.toml', ROOT/'app/uv.lock', ROOT/'app/package.json', ROOT/'app/bun.lock',
                  ROOT/'spec/lakefusion/ACCESS.md', ROOT/'bench/lakefusion/ACCESS_PLAN.md',
                  args.plan.resolve(), ROOT/'app/build_deploy.py',
                  ROOT/'bench/lakefusion/access-inputs-20260923.json', ROOT/'tools/check_changes.py',
                  ROOT/'tools/lakefusion_access_run.py', ROOT/'tools/run_mastering_http_tests.py',
                  ROOT/'tools/local_postgres.py', ROOT/'requirements-postgres.lock']
        report['source_hashes'] = {str(p.relative_to(ROOT)): sha256(p) for p in source}
        run([ROOT/'app/.venv/bin/python', 'build_deploy.py'], cwd=ROOT/'app', timeout=420)
        # APX dev check refreshes router tooling; use the repository's established
        # pinned type-check commands after the frozen build instead.
        run(['node', 'node_modules/typescript/bin/tsc', '--noEmit'], cwd=ROOT/'app', timeout=60)
        run([ROOT/'app/.venv/bin/ty', 'check'], cwd=ROOT/'app', timeout=60)
        report.update(apx_build_passed=True, type_check_passed=True)
        tests = [str(p.relative_to(ROOT)) for p in sorted((ROOT/'tests').glob('test_mastering_*.py'))]
        tests += ['tests/test_config.py', 'tests/test_publication.py', 'tests/test_source_hygiene.py',
                  'tests/test_source_scan.py', 'tests/postgres']
        run([sys.executable, '-m', 'pytest', '-q', *tests, '--junitxml='+str(args.tests_output.resolve())],
            env={**os.environ, 'LAKEMATCH_TEST_POSTGRES': '1'})
        suites = list(ET.parse(args.tests_output).getroot().iter('testsuite'))
        report['tests'] = {k: sum(int(s.attrib[k]) for s in suites) for k in ('tests', 'failures', 'errors', 'skipped')}
        if any(report['tests'][k] for k in ('failures', 'errors', 'skipped')):
            raise RuntimeError('All required root checks must pass without skips')
        run([sys.executable, 'tools/run_mastering_http_tests.py', '--junit-output', args.http_tests,
             '--report-output', args.http_report])
        http = json.loads(args.http_report.read_text())
        assert http['status'] == 'passed'
        report['http_tests'], report['http_runtime_cleanup'] = http['tests'], http['cleanup']
        domain = DomainContract.from_dict(json.loads((ROOT/'examples/mastering/company_pilot/domain.json').read_text()))
        context = WorkflowContext('company', 1, domain.sha256)
        with LocalPostgres() as server:
            with server.connect() as connection:
                report['migrations'] = apply_migrations(connection, ROOT/'app/migrations/mastering')
                report['postgres'] = connection.execute('SELECT version()').fetchone()[0]
                assert connection.execute('SHOW listen_addresses').fetchone()[0] == ''
                assert connection.execute('SHOW fsync').fetchone()[0] == 'on'
                connection.execute('CREATE ROLE workflow_acceptance NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE')
                grant_workflow_role(connection, 'workflow_acceptance')
            registry = PostgresRegistry(server.connect)
            registry.submit_domain(domain, actor='engineer', expected_latest=0)
            registry.transition('domain', 'company', 'company', 1, state='approved', expected_revision=1,
                                actor='approver', reason='Synthetic access acceptance')
            def options(key):
                return {'actor': 'synthetic_steward', 'reason': 'Access lifecycle', 'key': key}
            identities = PostgresIdentityRegistry(server.connect, IdentityContext('company', 1, domain.sha256))
            master = identities.allocate([SourceRef('erp_vendor', 'one')], **options('identity'))['result']['master_id']
            access = PostgresAccessRegistry(server.connect)
            grants = [{'role': 'steward', 'fields': None, 'object_ids': [master]}]
            first = access.replace('synthetic_steward', 'company', grants, expected_revision=0,
                                   actor='operator', reason='Grant', key='grant')
            def connect():
                connection = server.connect()
                connection.execute('SET ROLE workflow_acceptance')
                return connection
            store = AuthorizedWorkflow(connect, context, 'synthetic_steward')
            created = store.create_task('override', [master], evidence={}, **options('create'))
            task_id = created['result']['task']['task_id']
            claimed = store.claim(task_id, 1, seconds=60, **options('claim'))
            assert claimed['authorization']['definition_sha256'] == first['definition_sha256']
            revoked = access.replace('synthetic_steward', 'company', [], expected_revision=1,
                                     actor='operator', reason='Revoke', key='revoke')
            denied = 0
            for operation in (lambda: store.get_task(task_id), lambda: store.history(task_id=task_id),
                              lambda: store.claim(task_id, 1, seconds=60, **options('claim'))):
                try:
                    operation()
                except AccessDenied:
                    denied += 1
            assert denied == 3
            server.restart()
            try:
                store.get_task(task_id)
            except AccessDenied:
                denied += 1
            assert denied == 4
            restored = access.replace('synthetic_steward', 'company', grants, expected_revision=2,
                                      actor='operator', reason='Regrant', key='regrant')
            assert store.claim(task_id, 1, seconds=60, **options('claim')) == claimed
            report.update(revoked_reads_and_retries_denied=denied, revocation_survives_restart=True,
                          original_receipt_after_regrant=True, restricted_database_role=True,
                          lifecycle={'grant': first, 'revoke': revoked, 'regrant': restored,
                                     'claim': claimed, 'history_sha256': digest(store.history(task_id=task_id))})
        report.update(preserved())
        changed = [p for p, h in report['source_hashes'].items() if sha256(ROOT/p) != h]
        assert not changed, f'Source changed during acceptance: {changed}'
        scale = 1 if sys.platform == 'darwin' else 1024
        report['peak_rss_bytes'] = {'parent': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*scale,
                                   'highest_child': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*scale}
        if max(report['peak_rss_bytes'].values()) > 4*1024**3:
            raise RuntimeError('Observed per-process RSS exceeds 4 GiB')
        report['status'] = 'passed'
    except Exception as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
    finally:
        if server is not None:
            report['cleanup'] = server.cleanup
        report.update(ended_at=datetime.now(timezone.utc).isoformat(), wall_seconds=round(time.monotonic()-started, 3))
        args.output.write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps({k: report.get(k) for k in ('status', 'tests', 'http_tests', 'cleanup', 'error')}), flush=True)
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())
