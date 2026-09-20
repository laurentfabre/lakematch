#!/usr/bin/env python3
"""Read-only comparison of original sealed outputs and declared source replays."""
import hashlib
import json
import math
import tarfile

from compatibility import DECLARATION, validate
from evidence import ROOT, sha256
from lakematch.benchmark.metrics import select
from report_final import PAIR_CORPORA, audit_scores

SUFFIXES = ('linkage-all', 'linkage-no_ssn', *('pairs-' + name for name in PAIR_CORPORA))


def sealed(kind, sources):
    events = [json.loads(line) for line in (ROOT / 'experiments/runs.jsonl').read_text().splitlines()]
    rows = [event for event in events if event['kind'] == kind]
    assert rows, f'Missing {kind}'
    event = rows[-1]
    manifest = json.loads((ROOT / event['manifest']).read_text())
    assert event['status'] == 'passed' and manifest['exit_code'] == 0, f'{kind} failed'
    assert 'no live members' in manifest['cleanup']
    assert all(manifest['source_files'].get(path) == value for path, value in sources.items())
    paths = {}
    for item in manifest['artifacts']:
        path = ROOT / item['path']
        assert path.is_file() and sha256(path) == item['sha256']
        paths[path.name] = path
    assert 'Verified OS denies non-loopback network access' in paths['stdout.txt'].read_text()
    assert sha256(paths['freeze.json']) == sha256(ROOT / 'bench/freeze.json')
    if kind.startswith('replay-'):
        assert sha256(paths['source_compatibility.json']) == sha256(DECLARATION)
        declaration = json.loads(DECLARATION.read_text())
        assert manifest['started_at'] > declaration['declared_at']
    report = json.loads(paths['report.json'].read_text())
    assert report['status'] == 'completed' and report['cleanup'] == 'succeeded'
    payloads = {}
    with tarfile.open(paths['frozen-evidence.tar.gz']) as archive:
        assert archive.extractfile('report.json').read() == paths['report.json'].read_bytes()
        for name, digest in report['evidence_files'].items():
            content = archive.extractfile(name).read()
            assert hashlib.sha256(content).hexdigest() == digest
            if name.endswith('.json'):
                payloads[name] = json.loads(content)
    return event, report, payloads


def compare_scores(original, replay, threshold, cardinality):
    def index(rows):
        result = {(row[0], row[1]): row[2] for row in rows}
        assert len(result) == len(rows), 'Duplicate scored pairs'
        assert all(math.isfinite(value) for value in result.values()), 'Nonfinite scores'
        return result
    old, new = index(original), index(replay)
    assert old.keys() == new.keys(), 'Candidate pair identities changed'
    delta = max((abs(old[key] - new[key]) for key in old), default=0.)
    assert delta <= 1e-12, f'Probability/metadata delta {delta} exceeds 1e-12'
    assert select(original, threshold, cardinality) == select(replay, threshold, cardinality), 'Link decisions changed'
    return delta


def audit_one(suffix):
    freeze = json.loads((ROOT / 'bench/freeze.json').read_text())
    declaration = validate(freeze)
    old_event, old, old_payload = sealed('frozen-' + suffix, freeze['execution_sources'])
    event, replay, payload = sealed('replay-' + suffix, declaration['execution_sources'])
    audit_scores(replay, payload, freeze)
    assert replay['config'] == old['config'], 'Full replay config changed'
    assert replay['frozen_model'] == old['frozen_model']
    threshold, cardinality = [old['config']['decision'][key] for key in ('threshold', 'cardinality')]
    if suffix.startswith('linkage-'):
        before, after = old_payload['all.predictions.json'], payload['all.predictions.json']
        deltas = {}
        for field in ('p', 'cos', 'rank', 'gap'):
            deltas[field] = compare_scores([[row['a_id'], row['b_id'], row[field]] for row in before],
                [[row['a_id'], row['b_id'], row[field]] for row in after], threshold if field == 'p' else 0., cardinality)
        assert replay['partitions'] == old['partitions'], 'Partition metrics or slices changed'
        assert replay['acceptance_passed'], 'Replayed FEBRL quality/latency gate failed'
    else:
        before, after = [item['heldout.predictions.json'] for item in (old_payload, payload)]
        assert sorted(before['labels']) == sorted(after['labels'])
        deltas = {name: compare_scores(before[name], after[name], threshold if name == 'scores' else 0., cardinality)
                  for name in ('scores', 'cosine_scores')}
        assert replay['metrics'] == old['metrics']
    return {'original_run': old_event['run_id'], 'replay_run': event['run_id'],
        'manifest': event['manifest'], 'maximum_deltas': deltas, 'decisions_identical': True}


def collect():
    results, errors = {}, []
    for suffix in SUFFIXES:
        try:
            results[suffix] = audit_one(suffix)
        except (AssertionError, KeyError, OSError, TypeError, ValueError) as exc:
            errors.append(f'{suffix}: {exc}')
    return results, errors


if __name__ == '__main__':
    results, errors = collect()
    report = {'status': 'compatible' if not errors else 'failed_or_incomplete',
        'declaration_sha256': sha256(DECLARATION), 'results': results, 'errors': errors}
    (ROOT / 'bench/compatibility_index.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    raise SystemExit(bool(errors))
