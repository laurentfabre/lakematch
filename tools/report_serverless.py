#!/usr/bin/env python3
"""Audit sealed remote runs and render their measured capabilities and gaps."""
from collections import Counter
import json

from evidence import ROOT, sha256
from report_identity import audit as audit_identity

KINDS = ('serverless-frozen-dqx', 'serverless-frozen-native', 'serverless-cluster-fixture')


def audit_fixture(report):
    result = report['result']
    assert result['commits'] == 3
    for key in ('exact_journal_replay', 'unchanged_input_stable',
                'historical_retry_does_not_rewind', 'interrupted_write_kept_previous_head'):
        assert result[key] is True, key
    matches = [ROOT / path for path in report['exported_artifacts']
               if path.endswith('/volume/publication-snapshots.json')]
    assert len(matches) == 1, 'Missing durable snapshot export'
    path = matches[0]
    assert sha256(path) == result['evidence_files'][path.name]
    snapshots = json.loads(path.read_text())
    assert set(snapshots) == {'original', 'incremental', 'unchanged'}
    for name, body in result['publications'].items():
        assert body['sequence'] == {'original': 1, 'incremental': 2, 'unchanged': 3}[name]
        assert body['batch_id'] == name and body['reused'] is False
        for table, table_info in body['tables'].items():
            assert table_info['version'] == 0
            assert table_info['rows'] == len(snapshots[name][table])
    assert result['publications']['incremental']['recovered_tables']
    before, after = [snapshots[name]['crosswalk'] for name in ('original', 'incremental')]
    changes = snapshots['incremental']['changes']
    events = snapshots['incremental']['cluster_events']
    audited = audit_identity({'before.json': before, 'after.json': after,
        'changes.json': changes, 'cluster_events.json': events}, {
        'observed_changes': dict(Counter(row['change'] for row in changes)),
        'cluster_events': dict(Counter(row['event'] for row in events)),
        'mutation': {'per_operation_count': 1, 'added': ['b3'], 'deleted': ['a3'], 'changed': ['a2']}})
    old_ids, new_ids = [{row['rec_id']: row['mdm_id'] for row in rows} for rows in (before, after)]
    assert all(old_ids[key] == new_ids[key] for key in old_ids.keys() & new_ids.keys())
    canonical = lambda rows: Counter(json.dumps(row, sort_keys=True) for row in rows)
    assert canonical(after) == canonical(snapshots['unchanged']['crosswalk'])
    assert snapshots['unchanged']['cluster_events'] == []
    assert {row['change'] for row in snapshots['unchanged']['changes']} == {'unchanged'}
    return audited


def collect():
    latest, history = {}, []
    for line in (ROOT / 'experiments/runs.jsonl').read_text().splitlines():
        event = json.loads(line)
        if event['kind'] in KINDS:
            latest[event['kind']] = event
            history.append({key: event[key] for key in ('run_id', 'kind', 'status', 'manifest')})
    runs, errors = {}, []
    for kind in KINDS:
        try:
            assert kind in latest, 'No sealed run'
            event = latest[kind]
            manifest = json.loads((ROOT / event['manifest']).read_text())
            paths = {}
            for item in manifest['artifacts']:
                path = ROOT / item['path']
                assert path.is_file() and sha256(path) == item['sha256'], f'Missing/changed {path}'
                paths[path.name] = path
            candidates = [path for name, path in paths.items() if name.startswith('serverless-') and name.endswith('-report.json')]
            assert len(candidates) == 1, 'Missing sealed remote report'
            report = json.loads(candidates[0].read_text())
            runs[kind] = {'run_id': event['run_id'], 'manifest': event['manifest'],
                'report_path': str(candidates[0].relative_to(ROOT)), 'report_sha256': sha256(candidates[0]),
                'report': report, 'audited': False}
            cleanup = report['cleanup']
            assert report['profile'] == 'fevm-gdpr2'
            assert cleanup['job_terminal'] is True and not cleanup['errors'], 'Job cleanup unverified'
            assert report['pipeline_id'] is None or cleanup['pipeline_idle'] is True, 'Pipeline cleanup unverified'
            assert event['status'] == 'passed' and manifest['exit_code'] == 0, report.get('error', 'Experiment failed')
            assert report['status'] == 'completed' and report['run']['state']['result_state'] == 'SUCCESS'
            assert 'no live members' in manifest['cleanup']
            exported = report['exported_artifacts']
            assert exported and all((ROOT / p).is_file() and sha256(ROOT / p) == h for p, h in exported.items())
            task_names = {'train', 'cluster'} if kind.endswith('fixture') else {'prepare', 'pipeline', 'audit'}
            tasks = report['run']['tasks']
            assert {task['task_key'] for task in tasks} == task_names
            assert all(task['state'].get('result_state') == 'SUCCESS' for task in tasks)
            result = report['result']
            assert result['status'] == 'completed'
            output_key = 'cluster' if kind.endswith('fixture') else 'audit'
            assert json.loads(report['outputs'][output_key]['notebook_output']['result']) == result
            if kind.endswith('fixture'):
                runs[kind]['identity_audit'] = audit_fixture(report)
            else:
                engine = 'dqx' if kind.endswith('dqx') else 'native'
                assert result['quality_engine'] == engine
                assert set(result['variants']) == {'all', 'no_ssn'}
                for row in result['variants'].values():
                    assert row['quarantine'] == {'left': 3, 'right': 3}
                    assert row['candidate_pairs'] <= 100000
                    assert set(row['partitions']) == {'valid', 'confirmation'}
                    assert all(part['absolute_f1_delta_from_local'] <= .01 for part in row['partitions'].values())
                config = report['pipeline']['spec']['configuration']
                assert config['lakematch.quality_engine'] == engine
                enabled = 'true' if engine == 'dqx' else 'false'
                assert config['lakematch.app_enabled'] == config['lakematch.genie_enabled'] == enabled
            runs[kind]['audited'] = True
        except (AssertionError, KeyError, OSError, TypeError, ValueError) as exc:
            errors.append(f'{kind}: {exc}')
    return runs, errors, history


def render(runs, errors, history):
    lines = ['# Serverless execution evidence', '',
        'Selected workspace: `fevm-gdpr2`. Frozen models and thresholds are unchanged. '
        'App/Genie configuration flags do not establish application or delegated API functionality.', '',
        '| Experiment | Remote run | Result | Cleanup |', '|---|---|---|---|']
    for kind in KINDS:
        if kind not in runs:
            lines.append(f'| {kind} | — | missing | untested |')
            continue
        row = runs[kind]
        report = row['report']
        cleanup = report.get('cleanup', {})
        cleaned = cleanup.get('job_terminal') and not cleanup.get('errors') and (
            report.get('pipeline_id') is None or cleanup.get('pipeline_idle'))
        lines.append(f"| {kind} | {report.get('run_id')} | {'audited pass' if row['audited'] else report['status']} | {'verified' if cleaned else 'unverified'} |")
        if row['audited'] and 'variants' in report['result']:
            for variant, value in report['result']['variants'].items():
                part = value['partitions']['confirmation']
                lines.append(f"| ↳ {variant} | — | F1 {part['f1']:.6f}; absolute local delta {part['absolute_f1_delta_from_local']:.6f} | {value['quarantine']} quarantined |")
    lines += ['', '## Retained attempts', '']
    lines += [f"- [{row['run_id']}](../{row['manifest']}): {row['status']}." for row in history]
    lines += ['', '## Outstanding evidence', '',
        'Training/clustering fixture evidence is limited to its small synthetic inputs. '
        'Normal remote cluster CLI publication remains unimplemented. '
        'Observed DBUs/cost and query-profile Photon task-time shares/operator fallbacks remain missing. '
        'Photon enabled in configuration is not measured Photon execution. The shared warehouse is not campaign-owned.']
    lines += ['', *['- ' + error for error in errors]]
    (ROOT / 'bench/SERVERLESS.md').write_text('\n'.join(lines) + '\n')
    (ROOT / 'bench/serverless_index.json').write_text(json.dumps({
        'status': 'partial', 'runs': {kind: {key: value for key, value in row.items() if key != 'report'}
                                    for kind, row in runs.items()},
        'errors': errors, 'history': history, 'observed_cost': None, 'photon_profile_evidence': None}, indent=2) + '\n')


if __name__ == '__main__':
    runs, errors, history = collect()
    render(runs, errors, history)
    print(json.dumps({'audited': [name for name, row in runs.items() if row['audited']], 'errors': errors}))
