#!/usr/bin/env python3
"""Validate and summarize the frozen closed-world retrieval/scoring comparison."""
import hashlib
import json
import tarfile

from lakematch.benchmark.metrics import evaluate, select
from evidence import ROOT, sha256

DEPS = {'src/lakematch/' + name + '.py' for name in ('config', 'runtime', 'entity', 'candidates',
    'blocking', 'features', 'feature_stats', 'matcher', 'tracking', 'composite_model', 'similarity',
    'embeddings', 'benchmark/corpora', 'benchmark/metrics')}
DEPS |= {'tools/run_linkage_candidates.py', 'tools/offline.sb', 'tools/offline_run.py',
         'bench/LINKAGE_PLAN.md', 'bench/PROTOCOL.md', 'pyproject.toml', 'requirements-local.lock'}


def main():
    compatible, failures = {}, []
    for line in (ROOT / 'experiments/runs.jsonl').read_text().splitlines():
        event = json.loads(line)
        if not event['kind'].startswith('linkage-'):
            continue
        manifest = json.loads((ROOT / event['manifest']).read_text())
        if event['status'] != 'passed':
            failures.append(event)
        if all(manifest['source_files'].get(path) == sha256(ROOT / path) for path in DEPS):
            compatible[event['kind'][8:]] = (event, manifest)
    index = {'status': 'partial', 'confirmation_scored': False, 'runs': {}, 'missing': [], 'failures': failures}
    lines = ['# Retrieval and classifier validation', '',
        'Closed-world FEBRL half-unmatched tasks under [LINKAGE_PLAN.md](LINKAGE_PLAN.md). Confirmation is unscored.',
        'All methods retrieve the complete 5,000-left / 2,500-right universe. Training pairs have both endpoints in training; only validation anchors receive classifier scores.',
        'Intervals are conditional on the validation-selected threshold and policy; they do not adjust for selection optimism.', '',
        '| Variant | Retriever | Policy | F1 [95% CI] | Recall@5 | Threshold | Retrieval s | Feature/fit s |',
        '|---|---|---|---|---:|---:|---:|---:|']
    for variant in ('all', 'no_ssn', 'no_ssn_dob'):
        if variant not in compatible or compatible[variant][0]['status'] != 'passed':
            index['missing'].append(variant)
            continue
        event, manifest = compatible[variant]
        paths = {}
        for artifact in manifest['artifacts']:
            path = ROOT / artifact['path']
            assert path.is_file() and sha256(path) == artifact['sha256']
            paths[path.name] = path
        report = json.loads(paths['report.json'].read_text())
        assert report['status'] == 'completed' and report['cleanup'] == 'succeeded'
        assert report['confirmation_scored'] is False and 'no live members' in manifest['cleanup']
        assert 'Verified OS denies non-loopback network access' in paths['stdout.txt'].read_text()
        predictions = {}
        with tarfile.open(paths['linkage-evidence.tar.gz'], 'r:gz') as archive:
            assert archive.extractfile('report.json').read() == paths['report.json'].read_bytes()
            for path, expected in report['evidence_files'].items():
                with archive.extractfile(path) as member:
                    assert hashlib.file_digest(member, 'sha256').hexdigest() == expected
                if path.endswith('.predictions.json'):
                    predictions[path[:-17]] = json.load(archive.extractfile(path))
        assert len(predictions) == 5 and len(report['rows']) == 15
        for row in report['rows']:
            prediction = predictions[row['method']]
            assert len(prediction['validation_anchors']) == 1000
            assert all(a in prediction['validation_anchors'] for a, _, _ in prediction['scores'])
            labels = {(a, b): y for a, b, y, _ in prediction['labels']}
            groups = {(a, b): group for a, b, _, group in prediction['labels']}
            metric, _ = evaluate(select(prediction['scores'], row['threshold'], row['cardinality']), labels, groups)
            assert abs(metric['f1'] - row['f1']) < 1e-12
            low, high = row['f1_95ci']
            lines.append(f"| {variant} | {row['method']} | {row['cardinality']} | {row['f1']:.4f} [{low:.4f}, {high:.4f}] | {row['candidate_recall']:.4f} | {row['threshold']:.2f} | {row['retrieval_seconds']:.2f} | {row['feature_fit_seconds']:.2f} |")
        index['runs'][variant] = {'run_id': event['run_id'], 'manifest': event['manifest'],
            'report': str(paths['report.json'].relative_to(ROOT)), 'report_sha256': sha256(paths['report.json'])}
    if not index['missing']:
        index['status'] = 'comparison_completed_selection_pending'
    lines += ['', 'Stage costs share Spark startup and preparation; these measurements do not establish the 60-second end-to-end gate.',
        'The seven-corpus retrieval findings and classifier/feature macro comparison remain necessary to choose general defaults. No default or model is promoted by this report.', '']
    lines += [f"- `{name}`: [{row['run_id']}](../{row['manifest']})." for name, row in index['runs'].items()]
    if index['missing']:
        lines += ['', 'Missing compatible runs: ' + ', '.join(index['missing']) + '.']
    (ROOT / 'bench/LINKAGE.md').write_text('\n'.join(lines) + '\n')
    (ROOT / 'bench/linkage_index.json').write_text(json.dumps(index, indent=2) + '\n')
    print(json.dumps({'completed': list(index['runs']), 'missing': index['missing'], 'failures': len(failures)}))


if __name__ == '__main__':
    main()
