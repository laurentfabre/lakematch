"""Independently audit the exposed original-FEBRL diagnostic."""
import hashlib
import json
import tarfile

from compatibility import DECLARATION, validate
from evidence import ROOT, sha256
from lakematch.benchmark.metrics import bootstrap, evaluate, select


def collect():
    freeze = json.loads((ROOT / 'bench/freeze.json').read_text())
    declaration = validate(freeze)
    events = [json.loads(line) for line in (ROOT / 'experiments/runs.jsonl').read_text().splitlines()]
    found = [event for event in events if event['kind'] == 'original-febrl']
    assert found, 'Fresh selected-pipeline original-FEBRL diagnostic is missing'
    event = found[-1]
    manifest = json.loads((ROOT / event['manifest']).read_text())
    assert event['status'] == 'passed' and manifest['exit_code'] == 0
    assert 'no live members' in manifest['cleanup']
    assert all(manifest['source_files'].get(path) == value for path, value in declaration['execution_sources'].items())
    paths = {}
    for item in manifest['artifacts']:
        path = ROOT / item['path']
        assert path.is_file() and sha256(path) == item['sha256']
        paths[path.name] = path
    assert sha256(paths['source_compatibility.json']) == sha256(DECLARATION)
    assert sha256(paths['freeze.json']) == sha256(ROOT / 'bench/freeze.json')
    assert 'Verified OS denies non-loopback network access' in paths['stdout.txt'].read_text()
    report = json.loads(paths['report.json'].read_text())
    assert report['status'] == 'completed' and report['cleanup'] == 'succeeded'
    assert report['confirmation_scored'] is False and report['exposure']
    assert report['left_records'] == report['right_records'] == report['true_links'] == 5000
    entry = freeze['models']['febrl4_half_all']
    assert report['frozen_model'] == entry['model']
    for key in ('entity', 'candidates', 'features', 'matcher', 'decision'):
        assert report['config'][key] == entry['config'][key]
    with tarfile.open(paths['original-evidence.tar.gz']) as archive:
        assert archive.extractfile('report.json').read() == paths['report.json'].read_bytes()
        payloads = {}
        for name, expected in report['evidence_files'].items():
            content = archive.extractfile(name).read()
            assert hashlib.sha256(content).hexdigest() == expected
            if name in ('predictions.json', 'baseline.json'):
                payloads[name] = json.loads(content)
    payload = payloads['predictions.json']
    truth = dict.fromkeys(map(tuple, payload['truth']), 1.)
    assert len(truth) == 5000
    policy = report['config']['decision']
    decisions = select([(row['a_id'], row['b_id'], row['p']) for row in payload['scores']],
                       policy['threshold'], policy['cardinality'])
    assert decisions == set(map(tuple, payload['links']))
    baseline = select([(row['a_id'], row['b_id'], row['cos']) for row in payloads['baseline.json']['scores']], 0., 'many_to_one')
    assert baseline == set(map(tuple, payload['baseline_links']))
    groups = {}
    for name, chosen in [('metrics', decisions), ('nearest_neighbour', baseline)]:
        labels = {**dict.fromkeys(chosen, 0.), **truth}
        actual, groups[name] = evaluate(chosen, labels, {pair: pair[0] for pair in labels})
        assert all(report[name][key] == value for key, value in actual.items())
        assert bootstrap(groups[name])['f1_95ci'] == report[name]['f1_95ci']
    assert bootstrap(groups['nearest_neighbour'], groups['metrics'])['paired_delta_95ci'] == report['nearest_neighbour']['paired_delta_95ci']
    found = {(row['a_id'], row['b_id']) for row in payload['scores']}
    assert report['candidate_recall'] == len(found & truth.keys()) / 5000
    assert 0 < report['process_wall_seconds'] < manifest['wall_seconds']
    return {'run_id': event['run_id'], 'manifest': event['manifest'], 'report': report}
