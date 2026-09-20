#!/usr/bin/env python3
"""Read-only audit of local adapter evidence, also used before staging."""
import json

from evidence import ROOT, sha256


def check():
    kinds = ('dqx-parity', 'native-ml-all', 'native-ml-no_ssn')
    latest = {}
    for line in (ROOT / 'experiments/runs.jsonl').read_text().splitlines():
        event = json.loads(line)
        if event['kind'] in kinds:
            latest[event['kind']] = event
    results = {}
    for kind in kinds:
        event = latest[kind]
        manifest = json.loads((ROOT / event['manifest']).read_text())
        assert event['status'] == 'passed' and manifest['exit_code'] == 0
        assert 'no live members' in manifest['cleanup']
        artifacts = {}
        for item in manifest['artifacts']:
            path = ROOT / item['path']
            assert sha256(path) == item['sha256'], f'Changed adapter evidence: {path}'
            artifacts[path.name] = path
        assert 'Verified OS denies non-loopback network access' in artifacts['stdout.txt'].read_text()
        report = json.loads(artifacts['report.json'].read_text())
        assert report['status'] == 'completed'
        for path, expected in manifest['source_files'].items():
            if path.startswith('src/'):
                assert sha256(ROOT / path) == expected, f'Adapter source requires parity refresh: {path}'
        if kind == 'dqx-parity':
            assert report['native_dqx_exact_parity'] and report['construction_has_no_spark_actions_or_workspace_client']
        else:
            assert report['freeze_sha256'] == sha256(ROOT / 'bench/freeze.json')
            assert report['exact_minhash_keys'] and report['exact_ordered_candidates'] and report['native_plan']
            assert report['maximum_probability_difference'] < 1e-12
            assert len(report['hash_indices']) == 14
            assert all(row['expected'] == row['actual'] for row in report['hash_indices'])
            for name, expected in report['evidence_files'].items():
                assert sha256(artifacts[name]) == expected
        results[kind] = {'run_id': event['run_id'], 'manifest': event['manifest'], 'report': report,
            'artifacts': {name: str(path.relative_to(ROOT)) for name, path in artifacts.items()},
            'wall_seconds': event['wall_seconds']}
    return results


def main():
    results = check()
    lines = ['# Lazy serverless adapter evidence', '',
        'Offline local validation only. Remote SDP execution and Photon support require separate measurements.', '',
        '| Check | Result | Process seconds | Evidence |', '|---|---|---:|---|']
    for kind, entry in results.items():
        r = entry['report']
        result = ('2 valid / 4 quarantined; exact reasons and multiplicity; no definition-time actions'
            if kind == 'dqx-parity' else f"14 hash cases; exact keys/candidates; {r['pairs']} scores; maximum delta {r['maximum_probability_difference']:.3g}")
        lines.append(f"| {kind} | {result} | {entry['wall_seconds']:.2f} | [{entry['run_id']}](../{entry['manifest']}) |")
    lines += ['', 'The first native check failed on a harness column-name collision (`Row.index`). '
        'That failed run is retained. Iteration 2 fixed bracket-based column access; the SQL hash expression was unchanged. '
        '[Predeclared plan](SERVERLESS_ADAPTER_PLAN.md). No model or threshold was fitted or changed.']
    (ROOT / 'bench/SERVERLESS_ADAPTERS.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({kind: entry['run_id'] for kind, entry in results.items()}))


if __name__ == '__main__':
    main()
