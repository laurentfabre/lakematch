#!/usr/bin/env python3
"""Read-only capture of owned pipeline events and available query-history metrics."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import QueryFilter, TimeRange
from evidence import ROOT, sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', required=True)
    parser.add_argument('--run-report', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    if args.profile != 'fevm-gdpr2':
        raise ValueError('Campaign profile must be explicitly fevm-gdpr2')
    source = ROOT / args.run_report
    run = json.loads(source.read_text())
    assert run['profile'] == args.profile and run['cleanup']['job_terminal']
    assert run['cleanup']['pipeline_idle'] and not run['cleanup']['errors']
    w = WorkspaceClient(profile=args.profile)
    pipeline_id = run['pipeline_id']
    root = ROOT / 'data/serverless_profiles' / str(run['run_id'])
    root.mkdir(parents=True, exist_ok=True)
    start = run['run']['start_time']
    end = run['run']['end_time']
    events, event_complete, token = [], False, None
    for _ in range(3):
        query = {'max_results': 250}
        if token:
            query['page_token'] = token
        else:
            stamp = datetime.fromtimestamp(start / 1000, timezone.utc).isoformat()
            query['filter'] = "timestamp >= '" + stamp + "'"
        page = w.api_client.do('GET', f'/api/2.0/pipelines/{pipeline_id}/events', query=query)
        events.extend(page.get('events', []))
        token = page.get('next_page_token')
        if not token:
            event_complete = True
            break
    (root / 'events.json').write_text(json.dumps(events, indent=2) + '\n')
    queries, query_complete, token = [], False, None
    user_id = int(w.current_user.me().id)
    for _ in range(3):
        if token:
            page = w.query_history.list(page_token=token, max_results=1000, include_metrics=True)
        else:
            page = w.query_history.list(filter_by=QueryFilter(
                query_start_time_range=TimeRange(start_time_ms=start, end_time_ms=end), user_ids=[user_id]),
                max_results=1000, include_metrics=True)
        for query in page.res or []:
            item = query.as_dict()
            if ('lakematch_20260919' in item.get('query_text', '') or
                    pipeline_id in str(item.get('query_source', ''))):
                queries.append(item)
        token = page.next_page_token if page.has_next_page else None
        if not token:
            query_complete = True
            break
    (root / 'query-history.json').write_text(json.dumps(queries, indent=2) + '\n')
    complete_flows = [event for event in events if
        event.get('details', {}).get('flow_progress', {}).get('status') == 'COMPLETED']
    report = {'status': 'captured', 'profile': args.profile, 'run_id': run['run_id'], 'pipeline_id': pipeline_id,
        'captured_at': datetime.now(timezone.utc).isoformat(), 'source_report_sha256': sha256(source),
        'event_pages_complete': event_complete, 'query_history_pages_complete': query_complete,
        'completed_flows': {event['origin']['flow_name']: event['details']['flow_progress'].get('metrics', {}) for event in complete_flows},
        'matching_query_count': len(queries), 'observed_cost': None,
        'photon_operator_profiles': None,
        'limitation': 'Raw events expose output/flow metrics. Query history does not supply operator fallback profiles; no measured per-stage Photon claim.',
        'evidence_files': {str(path.relative_to(ROOT)): sha256(path) for path in root.iterdir() if path.is_file()}}
    (ROOT / args.report).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'completed_flows': len(complete_flows), 'matching_queries': len(queries), 'operator_profiles': None}))


if __name__ == '__main__':
    main()
