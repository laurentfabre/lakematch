import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import report_serverless
from evidence import sha256


def receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(report_serverless, 'ROOT', tmp_path)
    def record(key, changed=False):
        return {'rec_id': key, 'mdm_id': key[0], 'canonical_key': key[0] + '1',
                'record_digest': key + ('-changed' if changed else '')}
    before = [record(key) for key in ('a1', 'a2', 'a3', 'b1', 'b2')]
    after = [record(key, key == 'a2') for key in ('a1', 'a2', 'b1', 'b2', 'b3')]
    def journal(old, new):
        old, new = [{row['rec_id']: row for row in rows} for rows in (old, new)]
        rows = []
        for key in sorted(old.keys() | new.keys()):
            change = 'added' if key not in old else 'deleted' if key not in new else (
                'changed' if old[key]['record_digest'] != new[key]['record_digest'] else 'unchanged')
            rows.append({'rec_id': key, 'change': change, **{
                side + '_' + field: mapping.get(key, {}).get(field)
                for side, mapping in [('old', old), ('new', new)]
                for field in ('mdm_id', 'canonical_key', 'record_digest')}})
        return rows
    snapshots = {
        'original': {'crosswalk': before, 'changes': journal([], before),
                     'cluster_events': [{'event': 'created', 'old_ids': [], 'new_ids': [key]} for key in ('a', 'b')]},
        'incremental': {'crosswalk': after, 'changes': journal(before, after), 'cluster_events': []},
        'unchanged': {'crosswalk': after, 'changes': journal(after, after), 'cluster_events': []}}
    path = tmp_path / 'export/volume/publication-snapshots.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(snapshots))
    result = {'commits': 3, 'exact_journal_replay': True, 'unchanged_input_stable': True,
        'historical_retry_does_not_rewind': True, 'interrupted_write_kept_previous_head': True,
        'evidence_files': {path.name: sha256(path)}, 'publications': {}}
    for sequence, (name, tables) in enumerate(snapshots.items(), 1):
        result['publications'][name] = {'sequence': sequence, 'batch_id': name, 'reused': False,
            'recovered_tables': ['abandoned_attempt'] if name == 'incremental' else [],
            'tables': {table: {'version': 0, 'rows': len(rows)} for table, rows in tables.items()}}
    return {'result': result, 'exported_artifacts': {str(path.relative_to(tmp_path)): sha256(path)}}, path


def test_remote_receipt_independently_replays_exported_journal(tmp_path, monkeypatch):
    report, _ = receipt(tmp_path, monkeypatch)
    assert report_serverless.audit_fixture(report)['independent_replay']


def test_remote_receipt_rejects_rehashed_but_inconsistent_snapshot(tmp_path, monkeypatch):
    report, path = receipt(tmp_path, monkeypatch)
    snapshots = json.loads(path.read_text())
    snapshots['incremental']['crosswalk'][0]['record_digest'] = 'unreported-change'
    path.write_text(json.dumps(snapshots))
    report['result']['evidence_files'][path.name] = sha256(path)
    with pytest.raises(AssertionError):
        report_serverless.audit_fixture(report)


def test_remote_receipt_requires_abandoned_table_recovery(tmp_path, monkeypatch):
    report, _ = receipt(tmp_path, monkeypatch)
    report['result']['publications']['incremental']['recovered_tables'] = []
    with pytest.raises(AssertionError):
        report_serverless.audit_fixture(report)
