#!/usr/bin/env python3
"""Validate and compare compact native feature trials, without promotion."""
import hashlib
import json
import tarfile

import numpy as np

from lakematch.benchmark.metrics import BOOTSTRAP_SEED, evaluate, select
from evidence import ROOT, sha256

EXPECTED = ['febrl4-all', 'febrl4-no_ssn', 'febrl4-no_ssn_dob', 'bpid', 'abt_buy', 'affiliations',
            'amazon_google', 'walmart_amazon', 'dblp_acm']
DEPS = {'tools/run_methods.py', 'tools/run_compact_features.py', 'tools/spark_event_metrics.py', 'tools/offline.sb', 'tools/offline_run.py', 'bench/PROTOCOL.md', 'bench/COMPACT_PLAN.md'}
DEPS |= {'src/lakematch/' + name + '.py' for name in ('__init__', 'config', 'runtime', 'entity',
    'candidates', 'blocking', 'features', 'feature_stats', 'matcher', 'tracking', 'composite_model',
    'similarity', 'embeddings', 'benchmark/corpora', 'benchmark/metrics')}
DEPS |= {'pyproject.toml', 'requirements-local.lock'}


def interval(values):
    ordered = sorted(values)
    return [float(ordered[int(1999 * .025)]), float(ordered[int(1999 * .975)])]


def macro(reports):
    point, draws, cost = {}, {}, {}
    for name, (report, predictions) in reports.items():
        if name == 'febrl4-no_ssn_dob':
            continue
        weight = 1 / 14 if name.startswith('febrl4-') else 1 / 7
        variants = {}
        for row in report['rows']:
            previous = variants.get(row['variant'])
            if previous is None or row['f1'] > previous['f1']:
                variants[row['variant']] = row
        totals = {}
        for variant, row in variants.items():
            prediction = predictions[variant]
            labels = {(a, b): y for a, b, y, group in prediction['labels']}
            groups = {(a, b): group for a, b, y, group in prediction['labels']}
            metrics, grouped = evaluate(select(prediction['scores'], row['threshold'], row['cardinality']), labels, groups)
            assert abs(metrics['f1'] - row['f1']) < 1e-12
            totals[variant] = grouped
            point[variant] = point.get(variant, 0.) + weight * row['f1']
            cost[variant] = cost.get(variant, 0.) + weight * sum(row[k] for k in ('feature_seconds', 'train_seconds', 'score_seconds'))
            draws.setdefault(variant, np.zeros(2000))
        keys = sorted(next(iter(totals.values())))
        assert all(set(groups) == set(keys) for groups in totals.values())
        # FEBRL variants use the same entity draws. Other corpora are independent.
        namespace = 'febrl4' if name.startswith('febrl4-') else name
        seed = int(hashlib.sha256(f'{BOOTSTRAP_SEED}/{namespace}'.encode()).hexdigest()[:16], 16)
        rng = np.random.Generator(np.random.PCG64(seed))
        counts = {variant: np.asarray([groups[k][:3] for k in keys], dtype=np.int64) for variant, groups in totals.items()}
        for start in range(0, 2000, 50):
            chosen = rng.integers(0, len(keys), size=(50, len(keys)))
            for variant, values in counts.items():
                summed = values[chosen].sum(axis=1)
                numerator = 2 * summed[:, 0]
                denominator = numerator + summed[:, 1] + summed[:, 2]
                draws[variant][start:start + 50] += weight * np.divide(numerator, denominator,
                    out=np.zeros(50), where=denominator != 0)
    reference = 'native_all'
    return {variant: {'macro_f1': point[variant], 'f1_95ci': interval(draws[variant]),
        'paired_delta_vs_native_all_95ci': interval(draws[variant] - draws[reference]),
        'paired_deltas': {other: interval(draws[variant] - draws[other]) for other in sorted(point)},
        'weighted_feature_fit_score_seconds': cost[variant]} for variant in sorted(point)}


def main():
    latest, failures = {}, []
    for line in (ROOT / 'experiments/runs.jsonl').read_text().splitlines():
        event = json.loads(line)
        if not event['kind'].startswith('compact-'):
            continue
        manifest = json.loads((ROOT / event['manifest']).read_text())
        if event['status'] != 'passed':
            failures.append(event)
        if all(manifest['source_files'].get(p) == sha256(ROOT / p) for p in DEPS):
            latest[event['kind'][8:]] = (event, manifest)
    index = {'status': 'partial', 'confirmation_scored': False, 'runs': {}, 'missing': [], 'failures': failures}
    lines = ['# Compact native feature comparison', '',
        'Validation-only measurements under [COMPACT_PLAN.md](COMPACT_PLAN.md). Thresholds and policies are chosen on validation.',
        'Intervals describe sampling uncertainty; they do not correct for model, threshold or policy selection optimism.',
        'Supplied-pair tasks and full-universe FEBRL linkage have different evaluation scopes. Neither is confirmation evidence.', '']
    reports = {}
    for name in EXPECTED:
        if name not in latest or latest[name][0]['status'] != 'passed':
            index['missing'].append(name)
            continue
        event, manifest = latest[name]
        paths = {}
        for item in manifest['artifacts']:
            path = ROOT / item['path']
            assert path.is_file() and sha256(path) == item['sha256'], str(path)
            paths[path.name] = path
        report = json.loads(paths['report.json'].read_text())
        assert report['status'] == 'completed' and report['cleanup'] == 'succeeded'
        assert report['confirmation_scored'] is False and 'no live members' in manifest['cleanup']
        assert report.get('spark_metrics', {}).get('tasks', 0) > 0
        assert 'Verified OS denies non-loopback network access' in paths['stdout.txt'].read_text()
        predictions = {}
        with tarfile.open(paths['methods-evidence.tar.gz'], 'r:gz') as archive:
            assert archive.extractfile('report.json').read() == paths['report.json'].read_bytes()
            for path, digest in report['evidence_files'].items():
                with archive.extractfile(path) as member:
                    assert hashlib.file_digest(member, 'sha256').hexdigest() == digest
                if path.endswith('.predictions.json'):
                    predictions[path[:-17]] = json.load(archive.extractfile(path))
        assert len(predictions) == 3
        assert len(report['rows']) == 3 * len(report['cardinalities'])
        reports[name] = (report, predictions)
        index['runs'][name] = {'run_id': event['run_id'], 'manifest': event['manifest'],
            'report': str(paths['report.json'].relative_to(ROOT)), 'report_sha256': sha256(paths['report.json'])}
        lines += [f"## {report['corpus']}", '', f"Run [{event['run_id']}](../{event['manifest']}); scope: {report['evaluation_scope']}. "
            f"Preparation/Spark/output wall: {report['wall_seconds_including_spark']:.1f}s; complete runner wall including evidence hashing/compression and cleanup: {manifest['wall_seconds']:.1f}s.", '',
            '| Feature set | Estimator | Policy | F1 [95% CI] | Precision | Recall | Threshold | Feature/fit/score s |',
            '|---|---|---|---|---:|---:|---:|---|']
        for row in report['rows']:
            ci = row['f1_95ci']
            lines.append(f"| {row['variant']} | {row['estimator']} | {row['cardinality']} | {row['f1']:.4f} [{ci[0]:.4f}, {ci[1]:.4f}] | {row['precision']:.4f} | {row['recall']:.4f} | {row['threshold']:.2f} | {row['feature_seconds']:.2f}/{row['train_seconds']:.2f}/{row['score_seconds']:.2f} |")
        lines += ['', *[f"- Baseline {r['name']}: F1 {r['f1']:.4f}, threshold {r['threshold']:.2f}, {r['score']}." for r in report['baselines']], '']
    if not index['missing']:
        index.update(status='compact_comparison_completed', macro=macro(reports))
        best = max(index['macro'], key=lambda variant: index['macro'][variant]['macro_f1'])
        eligible = []
        for variant in ('scalar_fields', 'idf_only', 'native_all'):
            low, high = index['macro'][variant]['paired_deltas'][best]
            passes = all(max(row['f1'] for row in reports[name][0]['rows'] if row['variant'] == variant) >= floor
                         for name, floor in (('febrl4-all', .97), ('febrl4-no_ssn', .96)))
            if low <= 0 <= high and passes:
                eligible.append(variant)
        index['recommendation'] = eligible[0] if eligible else None
        index['best_point_estimate'] = best
        lines += ['## Macro validation results', '',
            'Seven equally weighted corpora; FEBRL all/SSN-hidden split one vote. The diagnostic does not vote.',
            'Within each trial, the best permitted validation policy is used. Macro intervals use 2,000 paired group resamples,',
            'PCG64 seeded by SHA-256 of bootstrap seed 2026091902 and corpus name; FEBRL variants share entity draws.', '',
            '| Configuration | Macro F1 [95% CI] | Paired change CI vs all native token features | Weighted feature/fit/score s |',
            '|---|---|---|---:|']
        for name, row in index['macro'].items():
            ci = row['f1_95ci']; delta = row['paired_delta_vs_native_all_95ci']
            lines.append(f"| {name} | {row['macro_f1']:.4f} [{ci[0]:.4f}, {ci[1]:.4f}] | [{delta[0]:+.4f}, {delta[1]:+.4f}] | {row['weighted_feature_fit_score_seconds']:.2f} |")
        lines += ['', f"Best point estimate: `{best}`. Simpler-choice recommendation: `{index['recommendation']}`.",
                  'Every candidate-to-best paired interval is retained in the structured index. This is a validation recommendation; final model freeze and latency remain pending.']
    else:
        lines += ['', 'Missing compatible completed runs: ' + ', '.join(index['missing']) + '.']
    lines += ['', 'No models were promoted by this report. Each trial links to its composite MLflow model in the structured evidence.',
        'The remaining retrieval/F1, final latency, scale and confirmation gates retain their separate requirements.']
    (ROOT / 'bench/COMPACT_FEATURES.md').write_text('\n'.join(lines) + '\n')
    (ROOT / 'bench/compact_features_index.json').write_text(json.dumps(index, indent=2) + '\n')
    print(json.dumps({'completed': list(index['runs']), 'missing': index['missing'], 'failures': len(failures)}))


if __name__ == '__main__':
    main()
