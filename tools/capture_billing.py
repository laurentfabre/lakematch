#!/usr/bin/env python3
"""Bounded read of billing records attributable to explicit campaign receipts."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import time

from databricks.sdk import WorkspaceClient

from evidence import ROOT, sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', required=True)
    parser.add_argument('--warehouse-id', required=True)
    parser.add_argument('--run-report', action='append', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    assert args.profile == 'fevm-gdpr2'
    path = ROOT / args.report
    assert not path.exists(), 'Billing observations are immutable; use a new receipt path'
    resources = set()
    sources = {}
    for name in args.run_report:
        source = ROOT / name
        run = json.loads(source.read_text())
        assert run['profile'] == args.profile and run['run_id']
        for ident in (run.get('job_id'), run.get('pipeline_id'), run['run_id'], run.get('run', {}).get('job_id')):
            if ident:
                resources.add(str(ident))
        sources[name] = sha256(source)
    assert all(re.fullmatch(r'[0-9a-f-]+', value) for value in resources)
    clause = ' OR '.join("instr(to_json(usage_metadata), '" + value + "') > 0" for value in sorted(resources))
    sql = """SELECT record_id, record_type, sku_name, usage_unit,
      CAST(usage_quantity AS STRING) AS usage_quantity,
      CAST(usage_start_time AS STRING) AS usage_start_time,
      CAST(usage_end_time AS STRING) AS usage_end_time,
      to_json(usage_metadata) AS metadata_json
      FROM system.billing.usage
      WHERE workspace_id = '7474658055368199' AND usage_date >= DATE '2026-09-19'
      AND (""" + clause + ') ORDER BY usage_start_time, record_id LIMIT 500'
    report = {'status': 'pending', 'profile': args.profile, 'warehouse_id': args.warehouse_id,
        'source_receipts': sources, 'resource_ids': sorted(resources), 'statement': sql,
        'captured_at': datetime.now(timezone.utc).isoformat(), 'observed_cost': None,
        'scope': 'Only explicitly supplied campaign receipts; not total account or campaign billing',
        'limits': {'statement_seconds': 180, 'maximum_rows': 500},
        'cleanup': 'No warehouse started or stopped; existing shared resource only'}
    w = WorkspaceClient(profile=args.profile)
    statement_id, terminal = None, False
    try:
        warehouse = w.warehouses.get(args.warehouse_id)
        report['warehouse_state'] = warehouse.state.value
        assert warehouse.state.value == 'RUNNING', 'Shared warehouse is stopped; no automatic startup'
        result = w.statement_execution.execute_statement(sql, args.warehouse_id, wait_timeout='0s',
                                                        row_limit=500, byte_limit=2000000)
        statement_id = report['statement_id'] = result.statement_id
        deadline = time.monotonic() + 180
        while result.status.state.value in {'PENDING', 'RUNNING'}:
            if time.monotonic() >= deadline:
                raise TimeoutError('Billing statement exceeded 180 seconds')
            time.sleep(2)
            result = w.statement_execution.get_statement(statement_id)
        terminal = True
        report['response'] = result.as_dict()
        assert result.status.state.value == 'SUCCEEDED', str(result.status.as_dict())
        assert not result.manifest.truncated, 'Billing response was truncated'
        assert result.manifest.total_row_count < 500, 'Billing row limit reached'
        assert not result.result or not result.result.next_chunk_index, 'Billing response needs further chunks'
        columns = [column.name for column in result.manifest.schema.columns]
        rows = [dict(zip(columns, row)) for row in (result.result.data_array if result.result else []) or []]
        seen, totals = set(), {}
        for row in rows:
            assert row['record_id'] not in seen, 'Duplicate billing record'
            seen.add(row['record_id'])
            metadata = json.loads(row['metadata_json'])
            assert any(str(value) in resources for key, value in metadata.items()
                       if key in {'job_id', 'job_run_id', 'dlt_pipeline_id', 'dlt_update_id', 'cluster_id'}), 'Unattributed billing row'
            key = row['sku_name'] + '/' + row['usage_unit']
            totals[key] = totals.get(key, Decimal(0)) + Decimal(row['usage_quantity'])
        report.update(status='captured_usage' if rows else 'no_attributed_rows_yet',
            row_count=len(rows), usage_by_sku_and_unit={key: str(value) for key, value in totals.items()},
            limitation='Billing can arrive late or be corrected; missing rows are not zero cost. '
                       'Usage units are observed; currency charges remain unreconciled.')
    except Exception as exc:
        report.update(status='unavailable_or_incomplete', error=f'{type(exc).__name__}: {exc}')
    finally:
        if statement_id and not terminal:
            w.statement_execution.cancel_execution(statement_id)
            report['statement_cancellation_requested'] = True
        report['ended_at'] = datetime.now(timezone.utc).isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report.get(key) for key in ('status', 'row_count', 'usage_by_sku_and_unit', 'error')}))


if __name__ == '__main__':
    main()
