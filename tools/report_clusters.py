#!/usr/bin/env python3
"""Read sealed clustering evidence, validate it, and report partial comparisons."""
import hashlib
import json
import tarfile

from lakematch.benchmark.clusters import cluster_metrics
from evidence import ROOT, sha256

CORPORA = ['febrl3', 'historical_50k']
COMMON = {'src/lakematch/benchmark/clusters.py', 'src/lakematch/benchmark/corpora.py',
          'src/lakematch/benchmark/metrics.py', 'tools/offline.sb', 'tools/offline_run.py',
          'bench/CLUSTER_PLAN.md', 'bench/PROTOCOL.md'}
NATIVE = {'src/lakematch/' + name + '.py' for name in ('clustering', 'runtime', 'config',
    'entity', 'features', 'feature_stats', 'matcher', 'tracking', 'composite_model',
    'blocking', 'candidates', 'similarity', 'embeddings')}


def main():
    compatible, failures = {}, []
    for line in (ROOT / 'experiments/runs.jsonl').read_text().splitlines():
        event = json.loads(line)
        if not event['kind'].startswith(('splink-', 'cluster-')):
            continue
        manifest = json.loads((ROOT / event['manifest']).read_text())
        if event['status'] != 'passed':
            failures.append({'run_id': event['run_id'], 'manifest': event['manifest'], 'status': event['status']})
        splink = event['kind'].startswith('splink-')
        deps = COMMON | ({'tools/run_splink_cluster.py', 'bench/requirements-splink.lock'} if splink
                         else NATIVE | {'tools/run_clusters.py', 'pyproject.toml', 'requirements-local.lock'})
        if all(manifest['source_files'].get(p) == sha256(ROOT / p) for p in deps):
            compatible[event['kind']] = (event, manifest)
    index = {'status': 'partial', 'confirmation_scored': False, 'runs': {}, 'missing': [], 'failures': failures}
    lines = ['# Clustering validation measurements', '',
        'Frozen entity-disjoint partitions; confirmation remains unscored. [Protocol](CLUSTER_PLAN.md).',
        'Splink uses its separately declared blocking budget and supervised training procedure. It is a measured baseline, not an equal-candidate-budget retriever comparison.', '',
        '| Corpus | Method | Pairwise F1 [95% CI] | B-cubed F1 [95% CI] | Precision | Recall | Seconds |',
        '|---|---|---|---|---:|---:|---:|']
    for corpus in CORPORA:
        for prefix in ('splink', 'cluster'):
            key = prefix + '-' + corpus
            if key not in compatible or compatible[key][0]['status'] != 'passed':
                index['missing'].append(key)
                continue
            event, manifest = compatible[key]
            assert 'no live members' in manifest['cleanup']
            paths = {}
            for artifact in manifest['artifacts']:
                path = ROOT / artifact['path']
                assert path.is_file() and sha256(path) == artifact['sha256']
                paths[path.name] = path
            assert 'Verified OS denies non-loopback network access' in paths['stdout.txt'].read_text()
            report = json.loads(paths['report.json'].read_text())
            assert report['status'] == 'completed' and report['confirmation_scored'] is False
            archive_name = 'splink-evidence.tar.gz' if prefix == 'splink' else 'cluster-evidence.tar.gz'
            predictions = {}
            with tarfile.open(paths[archive_name], 'r:gz') as archive:
                assert archive.extractfile('report.json').read() == paths['report.json'].read_bytes()
                for path, expected in report['evidence_files'].items():
                    with archive.extractfile(path) as member:
                        assert hashlib.file_digest(member, 'sha256').hexdigest() == expected
                    if path.endswith('predictions.json'):
                        predictions[path] = json.load(archive.extractfile(path))
            if prefix == 'splink':
                assert report.get('prediction_endpoint_audit') == 'all endpoints belong to the disjoint validation partition'
                pred = predictions['predictions.json']
                assert all(a in pred['truth'] and b in pred['truth'] for a, b, _ in pred['edges'])
                assert cluster_metrics(pred['truth'], pred['clusters']) == report['metrics']
                rows = [{'method': 'Splink supervised / components', **report['metrics'], **report['uncertainty'], 'seconds': report['wall_seconds']}]
            else:
                assert report['cleanup'] == 'succeeded'
                assert {row['method'] for row in report['rows']} == {'connected_components', 'center', 'star', 'verified_merge'}
                rows = report['rows']
                for row in rows:
                    pred = predictions[row['method'] + '.predictions.json']
                    metrics = cluster_metrics(pred['truth'], pred['membership'])
                    assert all(row[name] == value for name, value in metrics.items())
                    assert row['rounds']
            for row in rows:
                pair, bc = row['pairwise_f1_95ci'], row['bcubed_f1_95ci']
                lines.append(f"| {corpus} | {row['method']} | {row['f1']:.4f} [{pair[0]:.4f}, {pair[1]:.4f}] | {row['bcubed_f1']:.4f} [{bc[0]:.4f}, {bc[1]:.4f}] | {row['precision']:.4f} | {row['recall']:.4f} | {row['seconds']:.2f} |")
            index['runs'][key] = {'run_id': event['run_id'], 'manifest': event['manifest'],
                'report': str(paths['report.json'].relative_to(ROOT)), 'report_sha256': sha256(paths['report.json'])}
    lines += ['', 'Splink seconds cover data preparation, fit, score, threshold tuning, metrics and database cleanup; Spark method seconds cover clustering and owned-table cleanup on a shared scored graph. They are different timing boundaries.', '',
        'Native method selection, incremental identity reconciliation and CLI acceptance remain pending. Historical published figures are not used as acceptance evidence.', '']
    lines += [f"- `{name}`: [{entry['run_id']}](../{entry['manifest']})." for name, entry in index['runs'].items()]
    if index['missing']:
        lines += ['', 'Missing compatible comparisons: ' + ', '.join(index['missing']) + '.']
    lines += ['', 'Retained failures:'] + [f"- [{row['run_id']}](../{row['manifest']}): {row['status']}." for row in failures]
    if not index['missing']:
        index['status'] = 'comparisons_completed_selection_pending'
    (ROOT / 'bench/CLUSTERS.md').write_text('\n'.join(lines) + '\n')
    (ROOT / 'bench/cluster_index.json').write_text(json.dumps(index, indent=2) + '\n')
    print(json.dumps({'completed': list(index['runs']), 'missing': index['missing'], 'failures': len(failures)}))


if __name__ == '__main__':
    main()
