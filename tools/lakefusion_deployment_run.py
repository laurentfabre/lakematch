#!/usr/bin/env python3
"""Bounded, first-install LF-C deployment; never adopts existing resources."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

import psycopg
import requests
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from databricks.sdk.errors import NotFound

from evidence import ROOT, sha256
from workflow_bootstrap import bootstrap
from lakematch.mastering.access_registry import PostgresAccessRegistry


def main():
    config = json.loads((ROOT/'bench/lakefusion/deployment-inputs-20260923.json').read_text())
    bench = ROOT/'bench/lakefusion'
    destination = bench/'deployment-20260923.json'
    binding_path = bench/'deployment-binding-20260923.json'
    payload = ROOT/'data/test-runs/workflow-deployment-20260923'
    if any(p.exists() for p in (destination, binding_path, payload)):
        raise SystemExit('Fresh evidence and payload paths required')
    if config['profile'] != 'fevm-gdpr2' or config['project_id'] != 'lakematch-mdm-dev':
        raise SystemExit('This committed plan only authorizes the selected dedicated target')
    started = time.monotonic()
    deadline = started+2100  # outer runner reserves another 300 seconds for cleanup
    report = {'phase': 'LF-C', 'slot': 5, 'status': 'running', 'inputs': config,
        'started_at': datetime.now(timezone.utc).isoformat(), 'commands': [], 'checks': [],
        'cleanup': {}, 'observed_cost': None, 'cost_status': 'billing unreconciled',
        'confirmation_materialized': False, 'stage': 'inventory'}
    app_owned = project_owned = warehouse_owned = False
    endpoint_name = None
    cleaning = False

    def save():
        destination.write_text(json.dumps(report, indent=2)+'\n')

    def budget():
        if not cleaning and time.monotonic() >= deadline:
            raise TimeoutError('Work deadline reached')

    def stage(name):
        budget()
        report['stage'] = name
        print(name, flush=True)
        save()

    def cli(*parts, body=None, cwd=ROOT, timeout=120):
        budget()
        command = ['databricks', *parts, '--profile', config['profile'], '--output', 'json']
        if body is not None:
            command += ['--json', json.dumps(body)]
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True,
            timeout=timeout if cleaning else min(timeout, max(1, deadline-time.monotonic())))
        report['commands'].append({'command': command, 'exit_code': result.returncode})
        save()
        if result.returncode:
            # These commands never request tokens or secrets.
            report['command_error'] = result.stderr[-3000:]
            raise RuntimeError('Deployment CLI command failed')
        try:
            return json.loads(result.stdout) if result.stdout.strip() else {}
        except ValueError:
            return {'completed': True}

    def poll(label, get, accepted, seconds=300):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            budget()
            value = get()
            if accepted(value):
                report[label] = value
                save()
                return value
            time.sleep(5)
        raise TimeoutError(label+' exceeded its deadline')

    def operation(value):
        if value.get('name', '').startswith('projects/') and '/operations/' in value['name']:
            result = poll('operation', lambda: cli('postgres', 'get-operation', value['name']),
                          lambda x: x.get('done', False), 300)
            if result.get('error'):
                report['operation_error'] = result['error']
                raise RuntimeError('Lakebase operation failed')

    def app():
        return cli('apps', 'get', config['app_name'])

    def preserved():
        for path, key in [('spec/lakefusion/frozen/phase-a-v0.1.json', 'files'),
                          ('bench/lakefusion/runtime-inputs-20260923.json', 'scanner_inputs')]:
            items = json.loads((ROOT/path).read_text())[key]
            assert all(sha256(ROOT/p) == h for p, h in items.items())

    def interrupted(*_):
        raise InterruptedError('Bounded deployment interrupted')

    signal.signal(signal.SIGTERM, interrupted)
    w = WorkspaceClient(config=Config(profile=config['profile'], http_timeout_seconds=20,
                                       retry_timeout_seconds=30))
    save()
    try:
        preserved()
        assert w.config.host.rstrip('/') == config['workspace_host']
        assert str(w.get_workspace_id()) == config['workspace_id']
        user = w.current_user.me()
        principal = f"databricks:{config['workspace_id']}:{user.id}"
        existing = list(w.postgres.list_projects())
        assert not any(p.name == 'projects/'+config['project_id'] for p in existing), 'Project already exists'
        assert not any(a.name == config['app_name'] for a in w.apps.list()), 'App already exists'
        for run in w.jobs.list_runs(active_only=True, limit=25):
            if (run.run_name or '').startswith('lakematch'):
                raise RuntimeError('Another campaign job is running')
        review_schema = config['review_catalog']+'.'+config['review_schema']
        try:
            w.schemas.get(review_schema)
        except NotFound:
            pass
        else:
            raise RuntimeError('Review schema already exists; refuse adoption')
        warehouse = w.warehouses.get(config['warehouse_id']).as_dict()
        assert warehouse['state'] == 'STOPPED' and warehouse['enable_serverless_compute']
        assert warehouse['name'].startswith('lakematch-20260919-')
        assert warehouse['creator_name'] == user.user_name and warehouse['auto_stop_mins'] <= 10
        assert {'key': 'campaign', 'value': 'lakematch-20260919'} in warehouse['tags']['custom_tags']
        report['warehouse_before'] = warehouse

        stage('create dedicated project')
        settings = {'autoscaling_limit_min_cu': .5, 'autoscaling_limit_max_cu': 1,
                    'no_suspension': False, 'suspend_timeout_duration': '300s'}
        project_owned = True  # absent above; reconcile a lost create acknowledgement
        request = {'spec': {'display_name': 'Lakematch governed MDM pilot', 'pg_version': 17,
            'enable_pg_native_login': False, 'default_endpoint_settings': settings,
            'custom_tags': [{'key': 'application', 'value': 'lakematch'},
                            {'key': 'phase', 'value': 'lf-c'}]}, 'initial_endpoint_spec': settings}
        report['project_request'] = request
        operation(cli('postgres', 'create-project', config['project_id'], '--no-wait', body=request))
        branch = f"projects/{config['project_id']}/branches/{config['branch_id']}"
        endpoint_name = branch+'/endpoints/primary'
        endpoint = poll('endpoint', lambda: cli('postgres', 'get-endpoint', endpoint_name),
                        lambda x: bool(x.get('status', {}).get('hosts', {}).get('host')))
        status = endpoint['status']
        assert status['autoscaling_limit_max_cu'] <= 1 and status['autoscaling_limit_min_cu'] == .5
        assert status['suspend_timeout_duration'] == '300s'
        databases = list(w.postgres.list_databases(parent=branch))
        database = next(d for d in databases if d.status.postgres_database == config['database'])
        report['database'] = database.as_dict()
        binding = json.loads((ROOT/'runtime/binding.example.json').read_text())
        binding.update(app_name=config['app_name'], workspace_host=config['workspace_host'],
            workspace_id=config['workspace_id'], endpoint=endpoint_name, database_resource=database.name,
            host=status['hosts']['host'], database=config['database'])
        binding_path.write_text(json.dumps(binding, indent=2)+'\n')

        stage('build and deploy stopped app')
        subprocess.run([sys.executable, str(ROOT/'tools/build_workflow_bundle.py'), '--output', str(payload),
            '--binding', str(binding_path), '--warehouse-id', config['warehouse_id'],
            '--review-schema', review_schema], cwd=ROOT, check=True, timeout=480,
            env={**os.environ, 'UV_OFFLINE': '1'})
        report['payload'] = json.loads((payload/'payload.json').read_text())
        cli('bundle', 'validate', '--strict', '--target', 'pilot', cwd=payload)
        app_owned = True
        cli('bundle', 'deploy', '--target', 'pilot', cwd=payload, timeout=300)
        app_data = poll('created_app', app, lambda a: bool(a.get('service_principal_client_id')))
        serving_role = app_data['service_principal_client_id']
        assert re.fullmatch(r'[0-9a-f-]{36}', serving_role)
        assert app_data.get('compute_status', {}).get('state') in {'STOPPED', 'IDLE'}

        stage('install operator migrations and restricted grants')
        def connect():
            budget()
            credential = w.postgres.generate_database_credential(endpoint=endpoint_name)
            return psycopg.connect(host=binding['host'], dbname=config['database'], user=user.user_name,
                password=credential.token, sslmode='verify-full', sslrootcert='system', connect_timeout=10,
                autocommit=True, options='-c statement_timeout=15000 -c lock_timeout=5000 -c search_path=pg_catalog')
        with connect() as connection:
            report['operator_tls'] = connection.execute(
                'SELECT ssl,version,cipher FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone()
            report['serving_role_before'] = connection.execute('''SELECT r.rolname,r.rolsuper,r.rolbypassrls,
                r.rolcreaterole,r.rolcreatedb,ARRAY(SELECT p.rolname FROM pg_auth_members m
                JOIN pg_roles p ON p.oid=m.roleid WHERE m.member=r.oid)
                FROM pg_roles r WHERE r.rolname=%s''', (serving_role,)).fetchone()
            save()
        fixture = bootstrap(connect, serving_role, principal)
        report['fixture'] = fixture

        stage('prepare isolated Delta review schema')
        w.schemas.create(name=config['review_schema'], catalog_name=config['review_catalog'],
                         comment='Lakematch LF-C isolated synthetic deployment acceptance')
        warehouse_owned = True
        cli('warehouses', 'start', config['warehouse_id'], '--no-wait')
        poll('warehouse_running', lambda: cli('warehouses', 'get', config['warehouse_id']),
             lambda x: x.get('state') == 'RUNNING')
        sys.path.insert(0, str(ROOT/'app/src'))
        from lakematch_review.backend.store import DeltaStore, TABLE_DDL
        store = DeltaStore(w, config['warehouse_id'], review_schema)
        for name, ddl in TABLE_DDL.items():
            budget()
            store.query(f'CREATE TABLE {store.table(name)} ({ddl}) USING DELTA')
        store.query(f"GRANT USE CATALOG ON CATALOG {config['review_catalog']} TO `{serving_role}`")
        store.query(f'GRANT USE SCHEMA ON SCHEMA {review_schema} TO `{serving_role}`')
        for name in TABLE_DDL:
            privileges = 'SELECT, MODIFY' if name == 'review_labels' else 'SELECT'
            store.query(f'GRANT {privileges} ON TABLE {store.table(name)} TO `{serving_role}`')

        stage('start deployed app')
        cli('bundle', 'run', 'workflow', '--no-wait', '--target', 'pilot', cwd=payload, timeout=120)
        def ready(a):
            state = a.get('active_deployment', {}).get('status', {}).get('state')
            if state in {'FAILED', 'CANCELLED'}:
                report['failed_app'] = a
                raise RuntimeError('Apps deployment failed')
            return state == 'SUCCEEDED' and a.get('compute_status', {}).get('state') == 'ACTIVE'
        running = poll('running_app', app, ready, 600)
        url = running['url'].rstrip('/')
        report['app_url'] = url
        def api(method, path, body=None, key=None, expected=200):
            budget()
            headers = w.config.authenticate()
            if key:
                headers = {**headers, 'Idempotency-Key': key}
            response = requests.request(method, url+path, headers=headers, json=body,
                timeout=40, allow_redirects=False)
            report['checks'].append({'method': method, 'path': path, 'status': response.status_code})
            save()
            assert response.status_code == expected, f'Unexpected HTTP {response.status_code}'
            if path.startswith('/api/v1/'):
                assert response.headers.get('cache-control') == 'no-store'
            return response.json()

        stage('live workflow receipt and revocation checks')
        session = api('GET', '/api/session')
        assert session['storage'] == 'delta' and session['user'] != 'local-reviewer'
        report['session'] = session
        assert api('GET', '/api/queue?limit=1') == []
        route = '/api/v1/domains/company/tasks'
        body = {'kind': 'override', 'entity_ids': [fixture['master_id']], 'evidence': {},
                'reason': 'Synthetic deployment acceptance'}
        receipt = api('POST', route, body, 'deployment-task-v1')
        assert receipt == api('POST', route, body, 'deployment-task-v1')
        report['task_receipt'] = receipt
        access = PostgresAccessRegistry(connect)
        access.replace(principal, 'company', [], expected_revision=1, actor=principal,
                       reason='Deployment revocation acceptance', key='deployment-revoke-v1')
        api('GET', route, expected=403)
        api('POST', route, body, 'deployment-task-v1', expected=403)
        stage('restart and preserve revocation')
        cli('apps', 'stop', config['app_name'], '--no-wait')
        poll('restart_stopped', app, lambda x: x.get('compute_status', {}).get('state') == 'STOPPED', 180)
        cli('apps', 'start', config['app_name'], '--no-wait')
        poll('restarted_app', app, ready, 360)
        api('GET', route, expected=403)
        access.replace(principal, 'company', fixture['grants'], expected_revision=2, actor=principal,
                       reason='Restore synthetic demo access', key='deployment-regrant-v1')
        assert receipt == api('POST', route, body, 'deployment-task-v1')
        report['original_receipt_after_restart_regrant'] = True
        report['live_renewal_rls_second_user'] = 'not qualified by this bounded run'
        preserved()
        report['status'] = 'passed'
    except BaseException as error:
        report.update(status='failed', error_type=type(error).__name__)
        # Avoid persisting a credential-bearing SDK/SQL exception.
        print('Failed at '+report['stage']+': '+type(error).__name__, flush=True)
    finally:
        cleaning = True
        if app_owned:
            try:
                cli('apps', 'stop', config['app_name'], '--no-wait')
                report['cleanup']['app'] = poll('final_app', app,
                    lambda x: x.get('compute_status', {}).get('state') == 'STOPPED', 180)['compute_status']['state']
            except Exception as error:
                report['cleanup']['app_error'] = type(error).__name__
        if warehouse_owned:
            try:
                cli('warehouses', 'stop', config['warehouse_id'], '--no-wait')
                report['cleanup']['warehouse'] = poll('final_warehouse',
                    lambda: cli('warehouses', 'get', config['warehouse_id']),
                    lambda x: x.get('state') == 'STOPPED', 90)['state']
            except Exception as error:
                report['cleanup']['warehouse_error'] = type(error).__name__
        if project_owned:
            # Retain the explicitly requested target and all evidence for resume.
            # No project/branch/schema data is ever dropped by this runner.
            report['cleanup']['lakebase'] = 'retained dedicated target; requested auto-suspend after 300 seconds'
        if any(k.endswith('_error') for k in report['cleanup']):
            report['status'] = 'failed'
        report.update(ended_at=datetime.now(timezone.utc).isoformat(),
                      wall_seconds=round(time.monotonic()-started, 3))
        save()
        print(json.dumps({k: report.get(k) for k in ('status', 'stage', 'cleanup')}), flush=True)
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())
