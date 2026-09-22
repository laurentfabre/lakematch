#!/usr/bin/env python3
"""Bounded local LF-C workflow acceptance; fresh evidence and owned databases."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from lakematch.mastering.contracts import DomainContract, digest
from lakematch.mastering.identity_contract import IdentityContext, SourceRef
from lakematch.mastering.identity_registry import PostgresIdentityRegistry
from lakematch.mastering.registry import PostgresRegistry, apply_migrations
from lakematch.mastering.workflow import PostgresWorkflow
from lakematch.mastering.workflow_contract import WorkflowContext
from evidence import sha256
from local_postgres import LocalPostgres

ROOT = Path(__file__).resolve().parents[1]


def required_tests(command, output, *, cwd, timeout, env=None):
    command = [*command, '--junitxml=' + str(output.resolve())]
    result = subprocess.run(command, cwd=cwd, env=env, timeout=timeout)
    suites = list(ET.parse(output).getroot().iter('testsuite'))
    counts = {k: sum(int(s.attrib[k]) for s in suites) for k in ('tests', 'failures', 'errors', 'skipped')}
    return {'command': command, 'exit_code': result.returncode, **counts}


def preserved_inputs():
    freeze = json.loads((ROOT / 'spec/lakefusion/frozen/phase-a-v0.1.json').read_text())['files']
    scanner = json.loads((ROOT / 'reports/scan-followup-20260922/summary.json').read_text())['input_reports']
    assert all(sha256(ROOT / p) == h for p, h in freeze.items()), 'Frozen Phase A content drifted'
    assert all(sha256(ROOT / p) == v['sha256'] for p, v in scanner.items()), 'Scanner input changed'
    return {'frozen_files_verified': len(freeze), 'scanner_inputs_verified': len(scanner)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--tests-output', required=True, type=Path)
    parser.add_argument('--app-tests-output', required=True, type=Path)
    args = parser.parse_args()
    if len({p.resolve() for p in (args.output, args.tests_output, args.app_tests_output)}) != 3:
        parser.error('Report and test outputs must be distinct paths')
    for path in (args.output, args.tests_output, args.app_tests_output):
        if path.exists():
            parser.error('Fresh output paths required; retain prior evidence')
        path.parent.mkdir(parents=True, exist_ok=True)
    started, server = time.monotonic(), None
    report = {'phase': 'LF-C', 'slot': 1, 'packages': ['LM-007', 'LM-009'], 'status': 'running',
              'started_at': datetime.now(timezone.utc).isoformat(), 'cloud_calls': 0,
              'confirmation_materialized': False, 'corpus': 'small synthetic workflow fixtures',
              'actor_source': 'trusted synthetic workers; no authentication claim',
              'driver': {'psycopg': version('psycopg')}, 'cleanup': 'not started'}
    try:
        report.update(preserved_inputs())
        source = [*sorted((ROOT / 'src/lakematch/mastering').glob('*.py')),
                  *sorted((ROOT / 'app/migrations/mastering').glob('*.sql')),
                  *sorted((ROOT / 'tests/postgres').glob('*.py')),
                  *sorted((ROOT / 'tests').glob('test_mastering_*.py')),
                  *sorted((ROOT / 'app/tests').glob('*.py')),
                  ROOT / 'spec/lakefusion/WORKFLOW.md', ROOT / 'bench/lakefusion/WORKFLOW_PLAN.md',
                  ROOT / 'tools/lakefusion_workflow_run.py', ROOT / 'tools/local_postgres.py',
                  ROOT / 'requirements-postgres.lock', ROOT / 'app/pyproject.toml']
        report['source_hashes'] = {str(p.relative_to(ROOT)): sha256(p) for p in source}
        tests = [str(p.relative_to(ROOT)) for p in sorted((ROOT / 'tests').glob('test_mastering_*.py'))]
        tests += ['tests/test_config.py', 'tests/test_publication.py', 'tests/test_source_hygiene.py',
                  'tests/test_source_scan.py', 'tests/postgres']
        report['tests'] = required_tests([sys.executable, '-m', 'pytest', '-q', *tests], args.tests_output,
            cwd=ROOT, timeout=180, env={**os.environ, 'LAKEMATCH_TEST_POSTGRES': '1'})
        report['app_tests'] = required_tests([str(ROOT / 'app/.venv/bin/python'), '-m', 'pytest', '-q', 'tests'],
            args.app_tests_output, cwd=ROOT / 'app', timeout=120)
        for key in ('tests', 'app_tests'):
            if any(report[key][k] for k in ('exit_code', 'failures', 'errors', 'skipped')):
                raise RuntimeError('Required tests did not all pass: ' + key)
        domain = DomainContract.from_dict(json.loads((ROOT / 'examples/mastering/company_pilot/domain.json').read_text()))
        context = WorkflowContext(domain.domain_id, domain.version, domain.sha256)
        report['context'] = asdict(context)
        with LocalPostgres() as server:
            report['postgres'] = subprocess.check_output([server.binaries['postgres'], '--version'], text=True).strip()
            with server.connect() as connection:
                report['migrations'] = apply_migrations(connection, ROOT / 'app/migrations/mastering')
                assert connection.execute('SHOW listen_addresses').fetchone()[0] == ''
                assert connection.execute('SHOW fsync').fetchone()[0] == 'on'
            registry = PostgresRegistry(server.connect)
            registry.submit_domain(domain, actor='fixture_engineer', expected_latest=0)
            registry.transition('domain', 'company', 'company', 1, state='approved', expected_revision=1,
                                actor='fixture_approver', reason='Synthetic workflow acceptance')
            identities = PostgresIdentityRegistry(server.connect, IdentityContext('company', 1, domain.sha256))
            store = PostgresWorkflow(server.connect, context)
            def options(key, actor='fixture_steward'):
                return {'actor': actor, 'reason': 'Synthetic workflow lifecycle', 'key': key}
            ids = [identities.allocate([SourceRef('erp_vendor', str(n))], **options('identity-' + str(n)))
                   ['result']['master_id'] for n in range(2)]
            before_identity = [identities.get(i) for i in ids]
            created = store.create_task('merge', ids, evidence={'fixture': True}, **options('create'))
            task_id = created['result']['task']['task_id']
            claimed = store.claim(task_id, 1, seconds=60, **options('claim'))
            leased = claimed['result']['task']
            proposed = store.propose(task_id, 2, leased['lease_token'], {i: 1 for i in ids},
                {'survivor_id': ids[0]}, evidence={'reviewed': True}, **options('propose'))
            operation_id = proposed['result']['operation']['operation_id']
            approved = store.approve(operation_id, 1, **options('approve', 'fixture_approver'))
            def snapshot():
                with server.connect() as connection:
                    outbox = connection.execute('SELECT event_id,kind,payload,state,attempts FROM lm_control.outbox_event').fetchall()
                return {'task': store.get_task(task_id), 'operation': store.get_operation(operation_id),
                        'history': store.history(task_id=task_id),
                        'outbox': [[str(r[0]), *r[1:]] for r in outbox]}
            before = snapshot()
            server.restart()
            after = snapshot()
            assert after == before
            assert len(after['outbox']) == 1 and after['outbox'][0][3] == 'pending'
            assert store.create_task('merge', ids, evidence={'fixture': True}, **options('create')) == created
            assert store.claim(task_id, 1, seconds=60, **options('claim')) == claimed
            assert store.propose(task_id, 2, leased['lease_token'], {i: 1 for i in ids},
                {'survivor_id': ids[0]}, evidence={'reviewed': True}, **options('propose')) == proposed
            assert store.approve(operation_id, 1, **options('approve', 'fixture_approver')) == approved
            assert [identities.get(i) for i in ids] == before_identity
            report.update(database_restart_exact=True, all_four_receipts_replay_exactly=True,
                          identities_unchanged=True, approved_outbox_count=1, lifecycle=after,
                          lifecycle_sha256=digest(after))
        report.update(preserved_inputs())
        assert all(sha256(ROOT / p) == h for p, h in report['source_hashes'].items()), 'Source changed during run'
        multiplier = 1 if sys.platform == 'darwin' else 1024
        report['peak_rss_bytes'] = {'parent': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * multiplier,
                                   'highest_child': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * multiplier}
        if max(report['peak_rss_bytes'].values()) > 4 * 1024**3:
            raise RuntimeError('Observed per-process RSS exceeds the 4 GiB bound')
        report['status'] = 'passed'
    except Exception as error:
        report.update(status='failed', error=f'{type(error).__name__}: {error}')
    finally:
        if server is not None:
            report['cleanup'] = server.cleanup
        report.update(ended_at=datetime.now(timezone.utc).isoformat(), wall_seconds=round(time.monotonic() - started, 3))
        args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({k: report.get(k) for k in ('status', 'tests', 'app_tests', 'database_restart_exact', 'cleanup', 'error')}), flush=True)
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())
