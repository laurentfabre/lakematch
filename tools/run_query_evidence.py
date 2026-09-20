#!/usr/bin/env python3
"""Two bounded evidence reads on a temporary owned serverless warehouse."""
import argparse
from datetime import datetime, timezone
import json
import re
import subprocess
import sys
import time
from uuid import uuid4

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import CreateWarehouseRequestWarehouseType, EndpointTags, EndpointTagPair

from evidence import ROOT, sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--run-report', required=True, action='append')
    args = parser.parse_args()
    assert args.profile == 'fevm-gdpr2'
    destination = ROOT / args.report
    assert not destination.exists(), 'Use an immutable observation path'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]
    root = ROOT / 'data/query_evidence' / stamp
    root.mkdir(parents=True)
    name = 'lakematch-20260919-evidence-' + stamp
    report = {'status': 'running', 'profile': args.profile, 'warehouse_name': name,
        'started_at': datetime.now(timezone.utc).isoformat(), 'observed_cost': None,
        'plan_sha256': sha256(ROOT / 'bench/QUERY_EVIDENCE_PLAN.md'), 'cleanup': {}}
    w = WorkspaceClient(profile=args.profile)
    warehouse_id, statement_id, statement_terminal = None, None, False
    creation_attempted = False

    def save():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + '\n')

    try:
        assert not any('lakematch-20260919' in (run.run_name or '') for run in w.jobs.list_runs(active_only=True)), 'Active campaign experiment'
        assert all(p.state.value == 'IDLE' for p in w.pipelines.list_pipelines()
                   if 'lakematch-20260919' in (p.name or '')), 'Active campaign pipeline'
        save()
        creation_attempted = True
        created = w.warehouses.create(name=name, cluster_size='2X-Small', enable_serverless_compute=True,
            warehouse_type=CreateWarehouseRequestWarehouseType.PRO, min_num_clusters=1, max_num_clusters=1,
            auto_stop_mins=10, tags=EndpointTags(custom_tags=[EndpointTagPair(key='campaign', value='lakematch-20260919')]))
        warehouse_id = report['warehouse_id'] = created.response.id
        save()
        deadline = time.monotonic() + 300
        while True:
            warehouse = w.warehouses.get(warehouse_id)
            report['warehouse'] = warehouse.as_dict()
            save()
            if warehouse.state.value == 'RUNNING':
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('Owned evidence warehouse startup exceeded 300 seconds')
            time.sleep(5)
        billing = root / 'billing.json'
        command = [sys.executable, 'tools/capture_billing.py', '--profile', args.profile,
            '--warehouse-id', warehouse_id, '--report', str(billing)]
        for path in args.run_report:
            command += ['--run-report', path]
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=300)
        (root / 'billing.stdout.txt').write_text(process.stdout)
        (root / 'billing.stderr.txt').write_text(process.stderr)
        report['billing_exit_code'] = process.returncode
        if billing.exists():
            report['billing_status'] = json.loads(billing.read_text())['status']
        capture = ROOT / 'bench/photon_index.json'
        index = json.loads(capture.read_text())
        ids = index['job_tasks']['pipeline']['query_ids']
        assert len(ids) == len(set(ids)) == 16 and all(re.fullmatch(r'[0-9a-f-]{36}', key) for key in ids)
        sql = ('SELECT statement_id, statement_text, to_json(query_source) AS source_json, '
               'to_json(query_tags) AS tags_json FROM system.query.history '
               "WHERE workspace_id = '7474658055368199' AND statement_id IN (" +
               ','.join("'" + key + "'" for key in ids) + ') LIMIT 17')
        report.update(query_index_sha256=sha256(capture), query_statement=sql)
        result = w.statement_execution.execute_statement(sql, warehouse_id, wait_timeout='0s', row_limit=17, byte_limit=2000000)
        statement_id = report['query_statement_id'] = result.statement_id
        save()
        deadline = time.monotonic() + 180
        while result.status.state.value in {'PENDING', 'RUNNING'}:
            if time.monotonic() >= deadline:
                raise TimeoutError('Query-history read exceeded 180 seconds')
            time.sleep(2)
            result = w.statement_execution.get_statement(statement_id)
        statement_terminal = True
        (root / 'query-history-response.json').write_text(json.dumps(result.as_dict(), indent=2) + '\n')
        assert result.status.state.value == 'SUCCEEDED', str(result.status.as_dict())
        assert not result.manifest.truncated and result.manifest.total_row_count <= 16
        assert not result.result or not result.result.next_chunk_index, 'Additional query-history chunks required'
        columns = [column.name for column in result.manifest.schema.columns]
        rows = [dict(zip(columns, row)) for row in (result.result.data_array if result.result else []) or []]
        actual = [row['statement_id'] for row in rows]
        assert len(actual) == len(set(actual)) and set(actual) <= set(ids), 'Unexpected statement identity'
        (root / 'query-history-rows.json').write_text(json.dumps(rows, indent=2) + '\n')
        report.update(status='captured', query_rows=len(rows), query_rows_complete=set(actual) == set(ids),
            unredacted_statement_count=sum(bool(row['statement_text']) and row['statement_text'] != '<REDACTED>' for row in rows))
    except Exception as exc:
        report.update(status='failed_or_incomplete', error=f'{type(exc).__name__}: {exc}')
    finally:
        errors = []
        if creation_attempted and warehouse_id is None:
            try:
                matches = [item for item in w.warehouses.list() if item.name == name]
                if len(matches) == 1:
                    warehouse_id = report['warehouse_id'] = matches[0].id
                elif matches:
                    errors.append('Ambiguous owned warehouse creation response')
            except Exception as exc:
                errors.append('Warehouse creation inventory: ' + str(exc))
        billing = root / 'billing.json'
        if billing.exists():
            partial = json.loads(billing.read_text())
            if partial.get('statement_id') and (partial['status'] == 'pending' or partial.get('cleanup_error')):
                try:
                    w.statement_execution.cancel_execution(partial['statement_id'])
                    report['cleanup']['billing_cancellation_requested'] = True
                except Exception as exc:
                    errors.append(str(exc))
        if statement_id and not statement_terminal:
            try:
                w.statement_execution.cancel_execution(statement_id)
                report['cleanup']['query_cancellation_requested'] = True
            except Exception as exc:
                errors.append(str(exc))
        if warehouse_id:
            try:
                w.warehouses.stop(warehouse_id)
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    state = w.warehouses.get(warehouse_id).state.value
                    report['cleanup']['warehouse_state'] = state
                    if state == 'STOPPED':
                        break
                    time.sleep(5)
                else:
                    errors.append('Owned warehouse STOPPED state unverified')
            except Exception as exc:
                errors.append(str(exc))
        report['cleanup']['errors'] = errors
        report['ended_at'] = datetime.now(timezone.utc).isoformat()
        report['evidence_files'] = {str(path.relative_to(ROOT)): sha256(path) for path in root.iterdir() if path.is_file()}
        save()
    print(json.dumps({key: report.get(key) for key in ('status', 'billing_status', 'query_rows', 'unredacted_statement_count', 'cleanup', 'error')}))
    return bool(report['cleanup']['errors'])


if __name__ == '__main__':
    sys.exit(main())
