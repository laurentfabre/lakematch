"""Independently compare clustering replays against preserved validation output."""
import json
import tarfile

from evidence import ROOT, sha256
from frozen import tree_hashes
from report_compatibility import compare_scores


def audit(report, payload):
    reference = json.loads((ROOT / 'bench/cluster_replay_reference.json').read_text())[report['corpus']]
    assert report['replay_reference'] == reference
    assert sha256(ROOT / reference['report']) == reference['report_sha256']
    assert sha256(ROOT / reference['archive']) == reference['archive_sha256']
    assert tree_hashes(ROOT / reference['model_path']) == reference['model_files']
    old = json.loads((ROOT / reference['report']).read_text())
    assert report['config'] == old['config'] and report['model'] == old['model']
    assert report['threshold'] == old['threshold'] and report['new_models_fitted'] == 0
    with tarfile.open(ROOT / reference['archive']) as archive:
        old_edges = json.load(archive.extractfile('edges.json'))
        assert old_edges['truth'] == payload['edges.json']['truth']
        for field, metric in [('edges', 'probability'), ('cosine', 'cosine')]:
            delta = compare_scores(old_edges[field], payload['edges.json'][field],
                                   old['threshold'] if field == 'edges' else 0., 'unrestricted')
            assert delta == report['replay_maximum_deltas'][metric]
        for row in report['rows']:
            name = row['method'] + '.predictions.json'
            assert json.load(archive.extractfile(name)) == payload[name], f'Changed {name}'
    assert {row['name']: row['threshold'] for row in old['baselines']} == {
        row['name']: row['threshold'] for row in report['baselines']}
