#!/usr/bin/env python3
"""Audit available query-history timing; do not infer missing operator profiles."""
import argparse
import json

from evidence import ROOT, sha256


def summarize(queries, task_ids):
    totals = {}
    seen = set()
    for query in queries:
        ident = query['query_id']
        assert ident not in seen, 'Duplicate query would double-count task time'
        seen.add(ident)
        task_id = query.get('query_source', {}).get('job_info', {}).get('job_task_run_id')
        assert task_id in task_ids, 'Query is not assigned to this exact job run'
        assert query['status'] == 'FINISHED', 'Incomplete query timings'
        metric = query['metrics']
        total, photon = metric.get('task_total_time_ms'), metric.get('photon_total_time_ms')
        assert total is not None and photon is not None and 0 <= photon <= total, 'Invalid or missing task timings'
        row = totals.setdefault(task_ids[task_id], {'queries': 0, 'task_total_time_ms': 0,
            'photon_total_time_ms': 0, 'query_ids': []})
        row['queries'] += 1
        row['query_ids'].append(ident)
        row['task_total_time_ms'] += total
        row['photon_total_time_ms'] += photon
    for row in totals.values():
        row['photon_task_time_share'] = (row['photon_total_time_ms'] / row['task_total_time_ms']
                                       if row['task_total_time_ms'] else None)
    return totals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', required=True)
    parser.add_argument('--run-report', required=True)
    args = parser.parse_args()
    capture_path, run_path = ROOT / args.capture, ROOT / args.run_report
    capture, run = [json.loads(path.read_text()) for path in (capture_path, run_path)]
    assert capture['source_report_sha256'] == sha256(run_path)
    assert run['profile'] == capture['profile'] == 'fevm-gdpr2'
    assert run['run_id'] == capture['run_id']
    assert capture['event_pages_complete'] and capture['query_history_pages_complete']
    for name, expected in capture['evidence_files'].items():
        assert sha256(ROOT / name) == expected
    query_path = next(ROOT / name for name in capture['evidence_files'] if name.endswith('/query-history.json'))
    queries = json.loads(query_path.read_text())
    tasks = {str(task['run_id']): task['task_key'] for task in run['run']['tasks']}
    totals = summarize(queries, tasks)
    assert len(queries) == capture['matching_query_count']
    for task, summary in capture['query_metrics_by_job_task'].items():
        assert all(totals[task][key] == value for key, value in summary.items())
    report = {'status': 'partial_query_history_metrics', 'run_id': run['run_id'],
        'capture': str(capture_path.relative_to(ROOT)), 'capture_sha256': sha256(capture_path),
        'query_history_sha256': sha256(query_path), 'job_tasks': totals,
        'matching_stage_attribution': None, 'executed_operator_profiles': None, 'observed_cost': None}
    (ROOT / 'bench/photon_index.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Serverless Photon evidence — incomplete', '',
        f"Completed DQX run `{run['run_id']}` on `fevm-gdpr2`. "
        f"[Terminal capture](../{report['capture']}); query IDs and hashes are in [the index](photon_index.json).", '',
        'The Query History API reports cumulative execution time for all tasks and for Photon tasks. '
        'The ratios below sum those milliseconds across the exact job-task query IDs. '
        'They exclude provisioning and are not wall-clock percentages.', '',
        '| Job task | Queries | All task ms | Photon task ms | Photon share |', '|---|---:|---:|---:|---:|']
    for task in ('prepare', 'pipeline', 'audit'):
        row = totals[task]
        share = f"{row['photon_task_time_share']:.2%}" if row['photon_task_time_share'] is not None else 'not measured'
        lines.append(f"| {task} | {row['queries']} | {row['task_total_time_ms']:,} | {row['photon_total_time_ms']:,} | {share} |")
    lines += ['', '## Remaining acceptance evidence', '',
        'The pipeline row aggregates its 16 refresh queries. Query text is redacted and no query tags '
        'identify the output table, so this capture does not assign query timings to individual candidate, '
        'feature, scoring or link stages. Raw events contain the 16 completed flows and planning summaries, '
        'but no complete executed operator profiles. The attempted query-profile export route returned '
        '`ENDPOINT_NOT_FOUND`; no alternate profile was selected.', '',
        'The documented export route is the query-profile UI Download action, which saves JSON. '
        'The reviewed public documentation does not establish a supported REST export. '
        '[Research receipt](../experiments/query-profile-export-research.json). '
        'Exporting the pipeline query profiles from this workspace is still required.', '',
        'Every fallback operator, per-matching-stage Photon share, campaign-attributed DBUs and observed '
        'cost remain missing. No cause for the low aggregate Photon share is inferred from timing alone. '
        'ZR-6 remains incomplete.', '',
        '## Capture corrections', '',
        'The first raw-event request exceeded the API limit of 250 events per page. The next capture '
        'filtered only SQL text and returned zero matches because the text is redacted. The corrected '
        'capture uses exact job-task IDs, retains all 40 queries, and restricts events to the completed '
        'run window. All earlier requests and files are retained; new captures use immutable directories.']
    (ROOT / 'bench/PHOTON.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({task: {key: value for key, value in row.items() if key != 'query_ids'} for task, row in totals.items()}))


if __name__ == '__main__':
    main()
