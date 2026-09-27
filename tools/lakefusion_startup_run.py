#!/usr/bin/env python3
"""Bounded live acceptance against a verified retained deployment, without bootstrap."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

import certifi
import psycopg
import requests
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from databricks.sdk.service.sql import ExecuteStatementRequestOnWaitTimeout
from databricks.sdk.service.workspace import ExportFormat

from evidence import ROOT, sha256
from workflow_retained import RetainedStateError, require, verify_retained_fixture
from lakematch.mastering.access_registry import PostgresAccessRegistry
from lakematch.mastering.contracts import digest


def redact_app_logs(raw):
    """Keep startup stack traces while excluding credential-bearing log lines."""
    lines = []
    for line in raw.splitlines():
        if re.search(r'(?i)(?:password|client_secret|authorization|(?:access_|refresh_)?token)[\s"\x27]*[:=]', line):
            lines.append('[credential-bearing log line omitted]')
        else:
            line = re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[REDACTED_JWT]', line)
            line = re.sub(r'dapi[a-fA-F0-9]{32,}', '[REDACTED_PAT]', line)
            line = re.sub(r'(https?://)[^\s/@:]+:[^\s/@]+@', r'\1[REDACTED]@', line)
            lines.append(line)
    return '\n'.join(lines)[-16000:]


def verify_uploaded_payload(export, source_path, files):
    """Read back every uploaded app file; never accept a stale deployment snapshot."""
    require(isinstance(source_path, str) and source_path.startswith('/Workspace/'),
            'Explicit workspace source path required')
    expected = {name[4:]: entry for name, entry in files.items() if name.startswith('app/')}
    require('app.yaml' in expected and 'binding.json' in expected and len(expected) <= 32,
            'Incomplete or oversized app file manifest')
    verified = {}
    for name, entry in expected.items():
        require(not name.startswith('/') and '..' not in name.split('/'), 'Invalid app file path')
        content = base64.b64decode(export(source_path+'/'+name), validate=True)
        actual = {'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)}
        require(actual == entry, 'Uploaded app file differs from the declared payload: '+name)
        verified[name] = actual
    return verified


def deployment_ready(value, deployment_id=None):
    deployment = value.get('active_deployment') or {}
    if deployment_id is not None and deployment.get('deployment_id') != deployment_id:
        return False
    state = (deployment.get('status') or {}).get('state')
    require(state not in {'FAILED', 'CANCELLED'}, 'Selected application deployment failed')
    return (state == 'SUCCEEDED' and value.get('compute_status', {}).get('state') == 'ACTIVE'
            and value.get('app_status', {}).get('state') == 'RUNNING')


def instance_qualification(app, *, collect_when_unreported=False):
    """Missing telemetry never passes qualification; observed drift always stops work."""
    require(app.get('compute_size') == 'MEDIUM', 'Medium app compute is required')
    for key in ('compute_min_instances', 'compute_max_instances'):
        require(app.get(key) is None or type(app[key]) is int and app[key] == 1,
                'Configured instance count exceeds the declared singleton envelope')
    count = app.get('compute_status', {}).get('active_instances')
    if count is None:
        require(collect_when_unreported, 'Singleton compute must be observed')
        return {'status': 'unqualified', 'active_instances': None,
                'reason': 'Platform omitted the active-instance count'}
    require(type(count) is int and count == 1, 'Observed instance count is not one')
    return {'status': 'passed', 'active_instances': count}


def main():
    start = time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True, type=Path)
    args = parser.parse_args()
    inputs = json.loads(args.inputs.read_text())
    config = json.loads((ROOT/'bench/lakefusion/deployment-inputs-20260923.json').read_text())
    require(config['profile'] == 'fevm-gdpr2' and config['app_name'] == 'lakematch-mdm-dev',
            'Only the selected dedicated target is authorized')
    runs = [json.loads(line) for line in (ROOT/'experiments/runs.jsonl').read_text().splitlines()]
    require(sum(r['phase'] == 'LF-C' for r in runs) == inputs['slot']-1
            and inputs['slot'] <= inputs['phase_limit'] == 32, 'Phase ledger or authorized cap mismatch')
    for name, expected in inputs['preserved_inputs'].items():
        require(sha256(ROOT/name) == expected, 'Pinned installation evidence changed')
    prior = json.loads((ROOT/inputs['installation_report']).read_text())
    payload_evidence = prior
    if inputs.get('runtime_report'):
        require(inputs['runtime_report'] in inputs['preserved_inputs'], 'Runtime report must be hash-pinned')
        payload_evidence = json.loads((ROOT/inputs['runtime_report']).read_text())
    require(config == prior['inputs'], 'Installation resource configuration changed')
    binding = json.loads((ROOT/inputs['binding']).read_text())
    destination, payload = ROOT/inputs['report'], ROOT/inputs['payload']
    require(not destination.exists() and not payload.exists(), 'Fresh report and payload paths required')
    original_payload = ROOT/inputs['retained_payload']
    for name, details in payload_evidence['payload']['files'].items():
        require(sha256(original_payload/name) == details['sha256'], 'Retained payload changed')
        if not inputs.get('rebuild', False):
            target = payload/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original_payload/name, target)
    active_payload = payload_evidence['payload']
    work_end, cleanup_end = start+2100, start+2370
    report = {'phase': 'LF-C', 'slot': inputs['slot'], 'status': 'running',
              'started_at': datetime.now(timezone.utc).isoformat(), 'inputs': inputs,
              'payload_source_commit': payload_evidence.get('payload_source_commit', '8320d42'),
              'payload': active_payload, 'commands': [], 'checks': [], 'observations': [],
              'cleanup': {}, 'stage': 'inventory', 'cost_status': 'billing unreconciled',
              'observed_cost': None, 'confirmation_materialized': False}
    cleaning = False
    app_owned = warehouse_owned = False
    latest_start = None
    w = None

    def save():
        destination.write_text(json.dumps(report, indent=2)+'\n')

    def budget():
        remaining = (cleanup_end if cleaning else work_end)-time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Declared run deadline reached')
        return remaining

    def stage(name):
        budget()
        report['stage'] = name
        save()
        print(name, flush=True)

    def cli(*parts, cwd=ROOT, timeout=60):
        command = ['databricks', *parts, '--profile', config['profile'], '--output', 'json']
        entry = {'command': command, 'started_at': datetime.now(timezone.utc).isoformat()}
        report['commands'].append(entry)
        save()
        try:
            result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                    timeout=min(timeout, budget()))
        except subprocess.TimeoutExpired as error:
            def decoded(value):
                return value.decode(errors='replace') if isinstance(value, bytes) else value or ''
            entry.update(timed_out=True, stdout=decoded(error.stdout)[-6000:], stderr=decoded(error.stderr)[-6000:])
            save()
            raise
        entry['exit_code'] = result.returncode
        if result.returncode:
            entry.update(stdout=result.stdout[-6000:], stderr=result.stderr[-6000:])
            save()
            raise RuntimeError('Recorded deployment CLI command failed')
        save()
        try:
            return json.loads(result.stdout) if result.stdout.strip() else {}
        except ValueError:
            return {'completed': True}

    def app():
        return cli('apps', 'get', config['app_name'])

    def poll(label, fetch, accepted, seconds):
        end = min(time.monotonic()+seconds, time.monotonic()+budget())
        while time.monotonic() < end:
            value = fetch()
            if 'compute_status' in value:
                report['observations'].append({'at': datetime.now(timezone.utc).isoformat(),
                    'label': label, 'compute_status': value['compute_status'],
                    'app_status': value.get('app_status'), 'active_deployment': value.get('active_deployment')})
                save()
            if accepted(value):
                report[label] = value
                save()
                return value
            time.sleep(5)
        raise TimeoutError(label+' exceeded its declared deadline')

    def preserved():
        for path, key in [('spec/lakefusion/frozen/phase-a-v0.1.json', 'files'),
                          ('bench/lakefusion/runtime-inputs-20260923.json', 'scanner_inputs')]:
            entries = json.loads((ROOT/path).read_text())[key]
            require(all(sha256(ROOT/p) == h for p, h in entries.items()), 'Frozen/scanner input changed')
        require(all(sha256(payload/p) == v['sha256'] for p, v in active_payload['files'].items()),
                'Copied payload changed')

    def begin_start():
        nonlocal latest_start
        # Reserve time for the platform's 20-minute STARTING stop restriction.
        require(cleanup_end-time.monotonic() >= 1350, 'Insufficient startup and cleanup reserve')
        latest_start = time.monotonic()
        cli('apps', 'start', config['app_name'], '--no-wait')

    def uploaded(source_path):
        def export(path):
            budget()
            return w.workspace.export(path, format=ExportFormat.AUTO).content
        return verify_uploaded_payload(export, source_path, active_payload['files'])

    def interrupted(*_):
        raise InterruptedError('Bounded deployment interrupted')

    signal.signal(signal.SIGTERM, interrupted)
    save()
    try:
        if inputs.get('rebuild', False):
            stage('build committed runtime payload')
            subprocess.run([sys.executable, str(ROOT/'tools/build_workflow_bundle.py'),
                '--output', str(payload), '--binding', str(ROOT/inputs['binding']),
                '--warehouse-id', config['warehouse_id'],
                '--review-schema', config['review_catalog']+'.'+config['review_schema'],
                '--platform-default-instances'], cwd=ROOT, check=True, timeout=min(480, budget()),
                env={**os.environ, 'UV_OFFLINE': '1'})
            active_payload = json.loads((payload/'payload.json').read_text())
            report['payload'] = active_payload
            report['payload_source_commit'] = subprocess.check_output(
                ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
            save()
        require(sha256(payload/'app/binding.json') == sha256(ROOT/inputs['binding']), 'Payload binding mismatch')
        preserved()
        w = WorkspaceClient(config=Config(profile=config['profile'], http_timeout_seconds=20,
                                           retry_timeout_seconds=30))
        require(w.config.host.rstrip('/') == config['workspace_host']
                and str(w.get_workspace_id()) == config['workspace_id'], 'Workspace binding changed')
        user = w.current_user.me()
        principal = f"databricks:{config['workspace_id']}:{user.id}"
        project = w.postgres.get_project('projects/'+config['project_id'])
        require(project.uid == 'ca930294-0763-4eaa-9638-b8be2c4f98b6', 'Project UID changed')
        endpoint = w.postgres.get_endpoint(binding['endpoint']).as_dict()
        status = endpoint['status']
        require(status['hosts']['host'] == binding['host'] and status['autoscaling_limit_max_cu'] <= 1
                and status['autoscaling_limit_min_cu'] == .5 and status['suspend_timeout_duration'] == '300s',
                'Lakebase binding or resource envelope changed')
        report['endpoint_before'] = endpoint
        actual_app = app()
        require(actual_app['service_principal_client_id'] == prior['created_app']['service_principal_client_id']
                and actual_app['resources'] == prior['created_app']['resources'], 'App binding changed')
        require(actual_app['compute_status']['state'] == 'STOPPED', 'Owned app must initially be stopped')
        require(not actual_app.get('active_deployment') and not actual_app.get('pending_deployment'),
                'This first-start plan refuses an existing source deployment')
        role = actual_app['service_principal_client_id']
        report['app_before'] = actual_app
        warehouse = w.warehouses.get(config['warehouse_id']).as_dict()
        require(warehouse['state'] == 'STOPPED' and warehouse['enable_serverless_compute']
                and warehouse['name'].startswith('lakematch-20260919-')
                and warehouse['creator_name'] == user.user_name and warehouse['auto_stop_mins'] <= 10
                and {'key': 'campaign', 'value': 'lakematch-20260919'} in warehouse['tags']['custom_tags'],
                'Campaign warehouse ownership or envelope changed')
        report['warehouse_before'] = warehouse
        for run in w.jobs.list_runs(active_only=True, limit=25):
            require(not (run.run_name or '').startswith('lakematch'), 'Another campaign job is active')

        stage('verify retained database without mutations')
        def connect():
            budget()
            credential = w.postgres.generate_database_credential(endpoint=binding['endpoint'])
            return psycopg.connect(host=binding['host'], dbname=binding['database'], user=user.user_name,
                password=credential.token, sslmode='verify-full', sslrootcert=certifi.where(), connect_timeout=10,
                autocommit=True, options='-c statement_timeout=15000 -c lock_timeout=5000 -c search_path=pg_catalog')
        fixture = prior['fixture']
        report['retained_fixture'] = verify_retained_fixture(connect, role, principal, fixture)
        report['fixture'] = fixture
        with connect() as connection:
            report['operator_tls'] = connection.execute(
                'SELECT ssl,version,cipher FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone()

        stage('verify isolated Delta metadata and grants')
        review_schema = config['review_catalog']+'.'+config['review_schema']
        tables = list(w.tables.list(config['review_catalog'], config['review_schema']))
        expected_tables = {'review_queue', 'review_labels', 'review_metadata'}
        require({t.name for t in tables} == expected_tables and all(t.data_source_format.value == 'DELTA'
                for t in tables), 'Retained review table set changed')
        report['review_tables'] = [t.as_dict() for t in tables]
        report['review_grants'] = []
        for kind, name, expected in [('catalog', config['review_catalog'], {'USE_CATALOG'}),
                                      ('schema', review_schema, {'USE_SCHEMA'}),
                                      *[('table', review_schema+'.'+t,
                                         {'SELECT', 'MODIFY'} if t == 'review_labels' else {'SELECT'})
                                        for t in sorted(expected_tables)]]:
            permissions = w.grants.get(kind, name, principal=role).as_dict()
            actual = {p for a in permissions.get('privilege_assignments', [])
                      if a['principal'] == role for p in a.get('privileges', [])}
            require(actual == expected, 'Retained direct review grants changed')
            report['review_grants'].append({'type': kind, 'name': name, 'permissions': permissions})
        warehouse_owned = True
        cli('warehouses', 'start', config['warehouse_id'], '--no-wait')
        poll('warehouse_running', lambda: cli('warehouses', 'get', config['warehouse_id']),
             lambda value: value.get('state') == 'RUNNING', 300)
        for table in sorted(expected_tables):
            budget()
            result = w.statement_execution.execute_statement(
                f'SELECT 1 FROM {review_schema}.{table} LIMIT 1', config['warehouse_id'],
                row_limit=1, byte_limit=1024, wait_timeout='15s',
                on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CANCEL).as_dict()
            require(result.get('status', {}).get('state') == 'SUCCEEDED'
                    and not (result.get('result') or {}).get('data_array'), 'Review table not empty or read failed')

        stage('validate and deploy retained payload while stopped')
        cli('bundle', 'validate', '--strict', '--target', 'pilot', cwd=payload, timeout=120)
        app_owned = True
        cli('bundle', 'deploy', '--auto-approve', '--target', 'pilot', cwd=payload, timeout=300)
        require(app()['compute_status']['state'] == 'STOPPED', 'Bundle unexpectedly started compute')
        source_path = ('/Workspace/Users/'+user.user_name+'/.bundle/lakematch-workflow/'
                       +config['app_name']+'/files/app')
        report['uploaded_payload'] = uploaded(source_path)
        stage('start compute separately from source deployment')
        begin_start()
        poll('compute_ready', app, lambda value: value.get('compute_status', {}).get('state') == 'ACTIVE', 600)
        poll('prior_deployment_idle', app, lambda value: all(
            ((value.get(key) or {}).get('status') or {}).get('state') != 'IN_PROGRESS'
            for key in ('active_deployment', 'pending_deployment')), 120)
        stage('deploy source onto ready compute')
        # bundle run resolves inline config against retained deployment state.
        # Deploy the verified app.yaml without overriding it with that old config.
        deployment = cli('apps', 'deploy', config['app_name'], '--source-code-path', source_path,
                         '--mode', 'SNAPSHOT', '--no-wait', timeout=120)
        require(bool(deployment.get('deployment_id')), 'Source deployment ID was not returned')
        report['submitted_deployment'] = deployment
        running = poll('running_app', app,
                       lambda value: deployment_ready(value, deployment['deployment_id']), 600)
        report['snapshot_payload'] = uploaded(running['active_deployment']['deployment_artifacts']['source_code_path'])
        report['initial_instance_qualification'] = instance_qualification(running,
            collect_when_unreported=inputs.get('collect_workflow_with_unreported_instances') is True)
        url = running['url'].rstrip('/')
        report['app_url'] = url

        def api(method, path, body=None, key=None, expected=200):
            budget()
            headers = w.config.authenticate()
            if key:
                headers = {**headers, 'Idempotency-Key': key}
            response = requests.request(method, url+path, headers=headers, json=body,
                                        timeout=min(40, budget()), allow_redirects=False)
            report['checks'].append({'method': method, 'path': path, 'status': response.status_code})
            save()
            require(response.status_code == expected, 'Unexpected HTTP response; see recorded status')
            if path.startswith('/api/v1/'):
                require(response.headers.get('cache-control') == 'no-store', 'Missing no-store response header')
            return response.json()

        stage('live workflow retries and permission revocation')
        session = api('GET', '/api/session')
        require(session['storage'] == 'delta' and session['user'] != 'local-reviewer', 'Real Apps session required')
        report['session'] = session
        require(api('GET', '/api/queue?limit=1') == [], 'Expected empty isolated review queue')
        route = '/api/v1/domains/company/tasks'
        body = {'kind': 'override', 'entity_ids': [fixture['master_id']], 'evidence': {},
                'reason': 'Synthetic deployment acceptance'}
        receipt = api('POST', route, body, 'deployment-task-v1')
        report['task_receipt'] = receipt
        save()
        require(receipt == api('POST', route, body, 'deployment-task-v1'), 'Original receipt did not replay')
        access = PostgresAccessRegistry(connect)
        access.replace(principal, 'company', [], expected_revision=1, actor=principal,
                       reason='Deployment revocation acceptance', key='deployment-revoke-v1')
        api('GET', route, expected=403)
        api('POST', route, body, 'deployment-task-v1', expected=403)
        stage('restart and preserve revoked access')
        cli('apps', 'stop', config['app_name'], '--no-wait')
        poll('restart_stopped', app, lambda value: value['compute_status']['state'] == 'STOPPED', 180)
        begin_start()
        restarted = poll('restarted_app', app, deployment_ready, 600)
        report['restart_snapshot_payload'] = uploaded(restarted['active_deployment']['deployment_artifacts']['source_code_path'])
        report['restart_instance_qualification'] = instance_qualification(restarted,
            collect_when_unreported=inputs.get('collect_workflow_with_unreported_instances') is True)
        api('GET', route, expected=403)
        access.replace(principal, 'company', fixture['grants'], expected_revision=2, actor=principal,
                       reason='Restore synthetic demo access', key='deployment-regrant-v1')
        require(receipt == api('POST', route, body, 'deployment-task-v1'), 'Restart receipt did not replay')
        with connect() as connection:
            counts = connection.execute('''SELECT (SELECT count(*) FROM lm_control.steward_task),
                (SELECT count(*) FROM lm_control.workflow_command)''').fetchone()
            require(counts == (1, 1), 'Duplicate task or command receipt')
            saved = connection.execute('SELECT receipt,receipt_sha256 FROM lm_control.workflow_command').fetchone()
            require(saved == (receipt, digest(receipt)), 'HTTP receipt differs from durable receipt')
            report['final_workflow_counts'] = list(counts)
        report['original_receipt_after_restart_regrant'] = True
        report['live_renewal_rls_second_user'] = 'not qualified by this bounded run'
        preserved()
        report['workflow_status'] = 'passed'
        require(all(report[k]['status'] == 'passed' for k in (
            'initial_instance_qualification', 'restart_instance_qualification')),
            'Workflow passed; instance-count qualification remains unavailable')
        report['status'] = 'passed'
    except BaseException as error:
        report.update(status='failed', error_type=type(error).__name__)
        # Only locally constructed validation messages are persisted. SDK/SQL errors
        # may include credentials; command diagnostics are captured separately above.
        if isinstance(error, RetainedStateError):
            report['validation_error'] = str(error)
        print('Failed at '+report['stage']+': '+type(error).__name__, flush=True)
        if app_owned:
            try:
                report['failure_app'] = app()
                command = ['databricks', 'apps', 'logs', config['app_name'], '--tail-lines', '150',
                           '--source', 'APP', '--profile', config['profile']]
                result = subprocess.run(command, capture_output=True, text=True, timeout=min(40, budget()))
                report['app_log_diagnostic'] = {'command': command, 'exit_code': result.returncode,
                    'redacted_log': redact_app_logs(result.stdout+'\n'+result.stderr)}
            except Exception as diagnostic_error:
                report['app_log_diagnostic_error'] = type(diagnostic_error).__name__
            save()
    finally:
        cleaning = True
        if warehouse_owned:
            try:
                cli('warehouses', 'stop', config['warehouse_id'], '--no-wait')
                report['cleanup']['warehouse'] = poll('final_warehouse',
                    lambda: cli('warehouses', 'get', config['warehouse_id']),
                    lambda value: value.get('state') == 'STOPPED', 90)['state']
            except Exception as error:
                report['cleanup']['warehouse_error'] = type(error).__name__
        if app_owned:
            try:
                while budget() > 0:
                    current = app()
                    state = current['compute_status']['state']
                    if state == 'STOPPED':
                        report['cleanup']['app'] = 'STOPPED'
                        report['final_app'] = current
                        break
                    if state != 'STOPPING' and (state != 'STARTING' or latest_start is None
                                               or time.monotonic()-latest_start >= 1210):
                        cli('apps', 'stop', config['app_name'], '--no-wait')
                    time.sleep(5)
            except Exception as error:
                report['cleanup']['app_error'] = type(error).__name__
        if w is not None:
            try:
                report['final_endpoint'] = w.postgres.get_endpoint(binding['endpoint']).as_dict()
                report['cleanup']['lakebase'] = 'Dedicated project, data and DAB state retained; idle suspension configured'
            except Exception as error:
                report['cleanup']['lakebase_error'] = type(error).__name__
        if any(key.endswith('_error') for key in report['cleanup']):
            report['status'] = 'failed'
        report.update(ended_at=datetime.now(timezone.utc).isoformat(), wall_seconds=round(time.monotonic()-start, 3))
        save()
        print(json.dumps({key: report.get(key) for key in ('status', 'stage', 'cleanup')}), flush=True)
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())
