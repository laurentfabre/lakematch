#!/usr/bin/env python3
"""Deploy one owned triggered pipeline; retain evidence and stop it on all exits."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from evidence import ROOT, sha256

TERMINAL = {'TERMINATED', 'SKIPPED', 'INTERNAL_ERROR'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', required=True)
    parser.add_argument('--target', choices=['serverless', 'serverless_native'], required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--fixture', action='store_true', help='Run the separate train/cluster publication fixture')
    args = parser.parse_args()
    if args.profile != 'fevm-gdpr2':
        raise ValueError('This campaign is authorized only on fevm-gdpr2')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    local = ROOT / 'data/serverless_runs' / (stamp + '-' + args.target + ('-fixture' if args.fixture else ''))
    local.mkdir(parents=True)
    volume = '/Volumes/gdpr2_catalog/lakematch_20260919/artifacts/' + (
        'cluster_fixture/' + stamp if args.fixture else 'serverless_frozen')
    destination = ROOT / args.report
    destination.parent.mkdir(parents=True, exist_ok=True)
    report = {'status': 'running', 'profile': args.profile, 'target': args.target,
        'started_at': datetime.now(timezone.utc).isoformat(), 'commands': [], 'observed_cost': None,
        'run_id': None, 'pipeline_id': None, 'volume_root': volume,
        'scope': ('synthetic remote fit/reload, verified merge and Delta commit recovery' if args.fixture else
            'frozen inference and quality parity; training/clustering/app/Genie remain separate gates'),
        'sources': {str(p.relative_to(ROOT)): sha256(p) for directory in ('src', 'deployment', 'integration', 'resources')
            for p in sorted((ROOT / directory).rglob('*')) if p.is_file() and p.suffix in {'.py', '.yml'}},
        'bundle_sha256': sha256(ROOT / 'databricks.yml'),
        'input_manifest_sha256': None if args.fixture else sha256(ROOT / 'data/serverless_frozen/manifest.json')}

    def save():
        destination.write_text(json.dumps(report, indent=2) + '\n')

    def cli(*parts, timeout=120, json_output=True):
        command = ['databricks', *parts, '--profile', args.profile, '--output', 'json']
        report['commands'].append(command)
        save()
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        number = len(report['commands'])
        (local / f'command-{number:03d}.stdout.txt').write_text(result.stdout)
        (local / f'command-{number:03d}.stderr.txt').write_text(result.stderr)
        if result.returncode:
            raise RuntimeError(f'{parts[:2]}: {result.stderr.strip()[:4000]}')
        return json.loads(result.stdout) if json_output and result.stdout.strip() else {}

    def rows(value, key):
        return value if isinstance(value, list) else value.get(key, [])

    run_id, pipeline_id, terminal = None, None, False
    cleanup_errors = []
    try:
        active = rows(cli('jobs', 'list-runs', '--active-only'), 'runs')
        if any('lakematch-20260919' in item.get('run_name', '') for item in active):
            raise RuntimeError('An active campaign run exists; refusing concurrent remote work')
        inventory = rows(cli('pipelines', 'list-pipelines'), 'statuses')
        if any('lakematch-20260919' in item.get('name', '') and item.get('state') != 'IDLE' for item in inventory):
            raise RuntimeError('A campaign pipeline is active; refusing deployment')
        cli('bundle', 'validate', '--strict', '--target', args.target)
        if not args.fixture:
            cli('fs', 'cp', str(ROOT / 'data/serverless_frozen'), 'dbfs:' + volume,
                '--recursive', '--overwrite', timeout=180, json_output=False)
        cli('bundle', 'deploy', '--target', args.target, '--auto-approve', timeout=300, json_output=False)
        summary = cli('bundle', 'summary', '--target', args.target)
        report['bundle_summary'] = summary
        resources = summary['resources']
        job_id = report['job_id'] = int(resources['jobs']['cluster_fixture' if args.fixture else 'frozen_pipeline']['id'])
        if not args.fixture:
            pipeline_id = report['pipeline_id'] = resources['pipelines']['matching']['id']
        parameters = ['--json', json.dumps({'job_id': job_id, 'job_parameters': {'root': volume}})] if args.fixture else [str(job_id)]
        run_id = report['run_id'] = cli('jobs', 'run-now', *parameters, '--no-wait',
            '--idempotency-token', 'lakematch-' + uuid4().hex)['run_id']
        timeout = 1200 if args.fixture else 1800
        deadline = time.monotonic() + timeout
        next_events = time.monotonic()
        while time.monotonic() < deadline:
            run = report['run'] = cli('jobs', 'get-run', str(run_id))
            state = run['state']['life_cycle_state']
            save()
            print(f"{args.target} run {run_id}: {state}", flush=True)
            if state in TERMINAL:
                terminal = True
                report['outputs'] = {}
                for task in run.get('tasks', []):
                    if task.get('run_id') and task['task_key'] != 'pipeline':
                        try:
                            report['outputs'][task['task_key']] = cli('jobs', 'get-run-output', str(task['run_id']))
                        except RuntimeError as exc:
                            report['outputs'][task['task_key']] = {'capture_error': str(exc)}
                if run['state'].get('result_state') != 'SUCCESS':
                    raise RuntimeError(f"Pipeline job failed: {run['state']}")
                result = json.loads(report['outputs']['cluster' if args.fixture else 'audit']['notebook_output']['result'])
                assert result['status'] == 'completed'
                assert result['commits'] == 3 if args.fixture else len(result['variants']) == 2
                report['result'] = result
                report['status'] = 'completed'
                break
            if pipeline_id and time.monotonic() >= next_events:
                events = rows(cli('pipelines', 'list-pipeline-events', pipeline_id, '--limit', '100'), 'events')
                started_at = run['start_time'] / 1000
                fatal = [event for event in events if event.get('error', {}).get('fatal') and
                    datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00')).timestamp() >= started_at]
                if fatal:
                    report['fatal_pipeline_events'] = fatal
                    save()
                    raise RuntimeError('Fatal pipeline error; cancelling before unchanged automatic retries: ' + fatal[0]['message'])
                next_events = time.monotonic() + 30
            time.sleep(10)
        else:
            raise TimeoutError(f'Job exceeded its {timeout}-second envelope')
    except BaseException as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        if run_id is not None and not terminal:
            try:
                cli('jobs', 'cancel-run', str(run_id))
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    report['run'] = cli('jobs', 'get-run', str(run_id))
                    if report['run']['state']['life_cycle_state'] in TERMINAL:
                        terminal = True
                        break
                    time.sleep(5)
                if not terminal:
                    cleanup_errors.append('Job termination unverified')
            except Exception as exc:
                cleanup_errors.append(str(exc))
        if pipeline_id is not None:
            try:
                # Stop only the pipeline ID returned by this campaign's bundle.
                cli('pipelines', 'stop', pipeline_id, '--no-wait')
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    report['pipeline'] = cli('pipelines', 'get', pipeline_id)
                    if report['pipeline']['state'] == 'IDLE':
                        break
                    time.sleep(5)
                else:
                    cleanup_errors.append('Pipeline IDLE state unverified')
                report['pipeline_events'] = cli('pipelines', 'list-pipeline-events', pipeline_id, '--limit', '1000')
            except Exception as exc:
                cleanup_errors.append(str(exc))
        if run_id is not None:
            try:
                cli('fs', 'cp', 'dbfs:' + volume, str(local / 'volume'), '--recursive', timeout=180, json_output=False)
            except Exception as exc:
                report['artifact_export_error'] = str(exc)
        report['cleanup'] = {'job_terminal': terminal if run_id else None,
            'pipeline_idle': report.get('pipeline', {}).get('state') == 'IDLE' if pipeline_id else None,
            'errors': cleanup_errors, 'shared_warehouse': 'not started or stopped by this runner'}
        report['exported_artifacts'] = {str(p.relative_to(ROOT)): sha256(p) for p in sorted(local.rglob('*')) if p.is_file()}
        report['ended_at'] = datetime.now(timezone.utc).isoformat()
        if cleanup_errors:
            report['status'] = 'failed'
        save()
    if cleanup_errors:
        raise RuntimeError(f'Cleanup incomplete: {cleanup_errors}')


if __name__ == '__main__':
    main()
