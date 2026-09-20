#!/usr/bin/env python3
"""Independently replay sealed identity journals without starting Spark."""
from collections import Counter, defaultdict
import hashlib
import json
import tarfile

from evidence import ROOT, sha256

DEPS = {'src/lakematch/' + name + '.py' for name in ('identity', 'clustering', 'runtime', 'config',
    'entity', 'features', 'feature_stats', 'similarity', 'candidates', 'blocking', 'matcher',
    'tracking', 'composite_model', 'embeddings', 'benchmark/corpora')}
DEPS |= {'tools/run_identity_increment.py', 'tools/run_clusters.py', 'tools/offline.sb',
         'tools/offline_run.py', 'bench/IDENTITY_PLAN.md', 'pyproject.toml', 'requirements-local.lock'}


def audit(payload, report):
    fields = ['mdm_id', 'record_digest', 'canonical_key']
    snapshots = {}
    for name in ('before', 'after'):
        rows = payload[name + '.json']
        snapshots[name] = {row['rec_id']: tuple(row[key] for key in fields) for row in rows}
        assert len(snapshots[name]) == len(rows), 'duplicate crosswalk IDs'
        assert all(all(values) for values in snapshots[name].values())
    before, after = snapshots['before'], snapshots['after']
    changes = payload['changes.json']
    assert {row['rec_id'] for row in changes} == before.keys() | after.keys()
    assert len(changes) == len(before.keys() | after.keys())
    replay, counts = {}, Counter()
    edges = set()
    for row in changes:
        key = row['rec_id']
        old = tuple(row['old_' + name] for name in fields)
        new = tuple(row['new_' + name] for name in fields)
        assert old == before.get(key, (None, None, None))
        assert new == after.get(key, (None, None, None))
        if key not in before:
            expected = 'added'
        elif key not in after:
            expected = 'deleted'
        else:
            moved, changed = old[0] != new[0], old[1] != new[1]
            expected = 'moved_and_changed' if moved and changed else 'moved' if moved else 'changed' if changed else 'unchanged'
            edges.add((old[0], new[0]))
        assert row['change'] == expected
        counts[expected] += 1
        if new[0] is not None:
            replay[key] = new
    assert replay == after
    assert dict(counts) == report['observed_changes']
    mutation = report['mutation']
    count = mutation['per_operation_count']
    assert count == max(1, len(before) // 100)
    assert counts['added'] == counts['deleted'] == count
    assert counts['changed'] + counts['moved_and_changed'] == count
    assert before.keys() - after.keys() == set(mutation['deleted'])
    assert after.keys() - before.keys() == set(mutation['added'])
    assert {key for key in before.keys() & after.keys() if before[key][1] != after[key][1]} == set(mutation['changed'])
    old_to_new, new_to_old = defaultdict(set), defaultdict(set)
    for old, new in edges:
        old_to_new[old].add(new)
        new_to_old[new].add(old)
    expected_events = []
    for new, old in new_to_old.items():
        if len(old) > 1:
            expected_events.append(('merge', tuple(sorted(old)), (new,)))
    for old, new in old_to_new.items():
        if len(new) > 1:
            expected_events.append(('split', (old,), tuple(sorted(new))))
    expected_events += [('rekey', (old,), (new,)) for old, new in edges
                       if old != new and len(old_to_new[old]) == len(new_to_old[new]) == 1]
    expected_events += [('retired', (old,), ()) for old in {row[0] for row in before.values()} - old_to_new.keys()]
    expected_events += [('created', (), (new,)) for new in {row[0] for row in after.values()} - new_to_old.keys()]
    actual_events = [(row['event'], tuple(row['old_ids']), tuple(row['new_ids'])) for row in payload['cluster_events.json']]
    assert Counter(expected_events) == Counter(actual_events)
    assert dict(Counter(row[0] for row in actual_events)) == report['cluster_events']
    return {'independent_replay': True, 'independent_event_reconciliation': True,
            'records': len(after), 'operation_count': count, 'changes': dict(counts),
            'events': report['cluster_events']}


def main():
    latest, failures = {}, []
    for line in (ROOT / 'experiments/runs.jsonl').read_text().splitlines():
        event = json.loads(line)
        if event['kind'] not in {'identity-febrl3', 'identity-historical_50k'}:
            continue
        manifest = json.loads((ROOT / event['manifest']).read_text())
        if event['status'] != 'passed':
            failures.append(event)
        if all(manifest['source_files'].get(path) == sha256(ROOT / path) for path in DEPS):
            latest[event['kind'][9:]] = (event, manifest)
    index = {'status': 'partial', 'confirmation_scored': False, 'runs': {}, 'missing': [], 'failures': failures}
    lines = ['# Incremental identity evidence', '',
        'Fixed validation-only mutations under [IDENTITY_PLAN.md](IDENTITY_PLAN.md), using the selected verified-merge models and frozen thresholds.',
        'Each run recomputes unchanged input, applies the mutation, and repeats changed input. The reporter independently replays every journal row and reconstructs every cluster event.', '',
        '| Corpus | Records | Added / changed / deleted | Stable original IDs | Exact replay | Idempotent repeat | Wall s |',
        '|---|---:|---|---|---|---|---:|']
    for corpus in ('febrl3', 'historical_50k'):
        if corpus not in latest or latest[corpus][0]['status'] != 'passed':
            index['missing'].append(corpus)
            continue
        event, manifest = latest[corpus]
        paths = {}
        for artifact in manifest['artifacts']:
            path = ROOT / artifact['path']
            assert path.is_file() and sha256(path) == artifact['sha256']
            paths[path.name] = path
        report = json.loads(paths['report.json'].read_text())
        assert report['status'] == 'completed' and report['cleanup'] == 'succeeded'
        assert report['confirmation_scored'] is False and 'no live members' in manifest['cleanup']
        assert 'Verified OS denies non-loopback network access' in paths['stdout.txt'].read_text()
        assert all(report.get(key) is True for key in ('unchanged_input_stable', 'exact_journal_replay', 'incremental_repeat_idempotent'))
        assert [row['name'] for row in report['runs']] == ['before', 'after', 'repeated']
        payload = {}
        with tarfile.open(paths['identity-evidence.tar.gz'], 'r:gz') as archive:
            assert archive.extractfile('report.json').read() == paths['report.json'].read_bytes()
            for path, expected in report['evidence_files'].items():
                with archive.extractfile(path) as member:
                    assert hashlib.file_digest(member, 'sha256').hexdigest() == expected
                payload[path] = json.load(archive.extractfile(path))
        assert payload['mutation.json'] == report['mutation']
        result = audit(payload, report)
        index['runs'][corpus] = {'run_id': event['run_id'], 'manifest': event['manifest'],
            'report': str(paths['report.json'].relative_to(ROOT)), 'report_sha256': sha256(paths['report.json']), **result}
        count = result['operation_count']
        lines.append(f"| {corpus} | {result['records']:,} | {count} / {count} / {count} | pass | pass | pass | {report['wall_seconds_including_spark']:.2f} |")
    lines += ['', 'Event counts (merge/split/rekey may coexist):', '']
    lines += [f"- `{corpus}`: `{json.dumps(row['events'], sort_keys=True)}`; [{row['run_id']}](../{row['manifest']})." for corpus, row in index['runs'].items()]
    lines += ['', 'Canonical-key additions/deletions may legitimately rekey identities; those changes are journalled. This measures validation partitions, not the full 50,578-record historical source. Durable CLI publication/recovery and the remaining phase verifiers retain their own requirements.']
    if not index['missing']:
        index['status'] = 'incremental_checks_completed'
    else:
        lines += ['', 'Missing compatible completed runs: ' + ', '.join(index['missing']) + '.']
    (ROOT / 'bench/IDENTITY.md').write_text('\n'.join(lines) + '\n')
    (ROOT / 'bench/identity_index.json').write_text(json.dumps(index, indent=2) + '\n')
    print(json.dumps({'completed': list(index['runs']), 'missing': index['missing'], 'failures': len(failures)}))


if __name__ == '__main__':
    main()
