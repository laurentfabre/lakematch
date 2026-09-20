#!/usr/bin/env python3
"""Audit candidate/classifier comparisons and select only complete macro methods."""
import hashlib
import json
import tarfile

import numpy as np

from lakematch.benchmark.metrics import evaluate, select
from evidence import ROOT, sha256
from report_linkage import DEPS as LINKAGE_DEPS
from run_candidate_pairs import CORPORA, METHODS

DEPS = LINKAGE_DEPS - {'tools/run_linkage_candidates.py', 'bench/LINKAGE_PLAN.md'}
DEPS |= {'tools/run_candidate_pairs.py', 'tools/run_methods.py', 'bench/CANDIDATE_PAIRS_PLAN.md'}


def load(event, manifest, archive_name):
    paths = {}
    for item in manifest['artifacts']:
        path = ROOT / item['path']
        assert path.is_file() and sha256(path) == item['sha256']
        paths[path.name] = path
    assert event['status'] == 'passed' and manifest['exit_code'] == 0 and 'no live members' in manifest['cleanup']
    assert 'Verified OS denies non-loopback network access' in paths['stdout.txt'].read_text()
    report = json.loads(paths['report.json'].read_text())
    assert report['status'] == 'completed' and report['cleanup'] == 'succeeded' and report['confirmation_scored'] is False
    predictions = {}
    with tarfile.open(paths[archive_name]) as archive:
        assert archive.extractfile('report.json').read() == paths['report.json'].read_bytes()
        for name, expected in report['evidence_files'].items():
            content = archive.extractfile(name).read()
            assert hashlib.sha256(content).hexdigest() == expected
            if name.endswith('.predictions.json'):
                predictions[name[:-17]] = json.loads(content)
    best = {}
    for row in report['rows']:
        payload = predictions[row['method']]
        truth = {(a, b): y for a, b, y, _ in payload['labels']}
        groups = {(a, b): group for a, b, _, group in payload['labels']}
        metric, grouped = evaluate(select(payload['scores'], row['threshold'], row['cardinality']), truth, groups)
        assert all(metric[key] == row[key] for key in metric)
        if 'validation_anchors' in payload:
            assert len(payload['validation_anchors']) == 1000
            grouped.update({key: [0, 0, 0, 0] for key in set(payload['validation_anchors']) - grouped.keys()})
        if row['method'] not in best or row['f1'] > best[row['method']][0]['f1']:
            best[row['method']] = (row, grouped)
    return report, best, paths


def macro(comparisons):
    complete = set(METHODS)
    for _, best, _ in comparisons.values():
        complete &= best.keys()
    if not complete:
        return {}
    draws = {method: np.zeros(2000) for method in complete}
    points, costs = dict.fromkeys(complete, 0.), dict.fromkeys(complete, 0.)
    for corpus, (_, best, _) in comparisons.items():
        weight = 1 / 14 if corpus.startswith('febrl4') else 1 / 7
        keys = sorted(next(iter(best.values()))[1])
        assert all(set(groups) == set(keys) for _, groups in best.values())
        seed = int(hashlib.sha256(f'2026091902/candidate_macro/{corpus}'.encode()).hexdigest()[:16], 16)
        rng = np.random.Generator(np.random.PCG64(seed))
        arrays = {method: np.asarray([best[method][1][key][:3] for key in keys]) for method in complete}
        for start in range(0, 2000, 50):
            chosen = rng.integers(0, len(keys), size=(50, len(keys)))
            for method, array in arrays.items():
                sums = array[chosen].sum(axis=1)
                denominator = 2 * sums[:, 0] + sums[:, 1] + sums[:, 2]
                draws[method][start:start + 50] += weight * np.divide(2 * sums[:, 0], denominator, out=np.zeros(50), where=denominator != 0)
        for method in complete:
            row = best[method][0]
            points[method] += weight * row['f1']
            costs[method] += weight * row['method_seconds_including_log_cleanup']
    def ci(values):
        ordered = sorted(values)
        return [float(ordered[int(1999 * .025)]), float(ordered[int(1999 * .975)])]
    return {method: {'macro_f1': points[method], 'f1_95ci': ci(draws[method]),
        'weighted_method_seconds': costs[method],
        'paired_deltas': {other: ci(draws[method] - draws[other]) for other in complete}}
        for method in sorted(complete)}


def main():
    latest, failures = {}, []
    for line in (ROOT / 'experiments/runs.jsonl').read_text().splitlines():
        event = json.loads(line)
        linkage = event['kind'] in {'linkage-all', 'linkage-no_ssn'}
        if not linkage and not event['kind'].startswith('candidate-pairs-'):
            continue
        manifest = json.loads((ROOT / event['manifest']).read_text())
        if event['status'] != 'passed':
            failures.append(event)
        deps = LINKAGE_DEPS if linkage else DEPS
        if all(manifest['source_files'].get(path) == sha256(ROOT / path) for path in deps):
            key = 'febrl4_half_' + event['kind'][8:] if linkage else event['kind'][16:]
            latest[key] = (event, manifest)
    expected = ['febrl4_half_all', 'febrl4_half_no_ssn', *CORPORA]
    index = {'status': 'partial', 'confirmation_scored': False, 'runs': {}, 'missing': [], 'failures': failures}
    comparisons = {}
    lines = ['# Candidate selection across seven corpora', '',
        'FEBRL is closed-world linkage. Other rows are retrieval-filtered supplied-pair validation: unknown pairs remain unknown and missing positives remain false negatives. Official shared-record caveats remain in each corpus manifest.',
        'All methods use k=5, at most 100,000 final pairs and 50 million retained join rows. [Plan](CANDIDATE_PAIRS_PLAN.md).', '',
        '| Corpus | Method | Validation F1 | Recall@5 | Policy | Threshold | Status |',
        '|---|---|---:|---:|---|---:|---|']
    for corpus in expected:
        if corpus not in latest or latest[corpus][0]['status'] != 'passed':
            index['missing'].append(corpus)
            continue
        event, manifest = latest[corpus]
        name = 'linkage-evidence.tar.gz' if corpus.startswith('febrl4') else 'candidate-pairs-evidence.tar.gz'
        report, best, paths = load(event, manifest, name)
        comparisons[corpus] = (report, best, paths)
        index['runs'][corpus] = {'run_id': event['run_id'], 'manifest': event['manifest'],
            'report': str(paths['report.json'].relative_to(ROOT)), 'report_sha256': sha256(paths['report.json']),
            'best_per_method': {method: row for method, (row, _) in best.items()}}
        for method in METHODS:
            if method in best:
                row = best[method][0]
                lines.append(f"| {corpus} | {method} | {row['f1']:.4f} | {row['candidate_recall']:.4f} | {row['cardinality']} | {row['threshold']:.2f} | completed |")
            else:
                outcome = next(row for row in report['outcomes'] if row['method'] == method)
                lines.append(f"| {corpus} | {method} | — | — | — | — | {outcome['status']}: {outcome['reason']} |")
    if not index['missing']:
        summary = macro(comparisons)
        index.update(status='comparisons_completed', macro=summary,
            ineligible_methods=sorted(set(METHODS) - summary.keys()))
        gated = [method for method in summary if comparisons['febrl4_half_all'][1][method][0]['f1'] >= .97
                 and comparisons['febrl4_half_no_ssn'][1][method][0]['f1'] >= .96]
        if gated:
            best = max(gated, key=lambda method: summary[method]['macro_f1'])
            indistinguishable = [method for method in gated if summary[method]['paired_deltas'][best][0] <= 0 <= summary[method]['paired_deltas'][best][1]]
            complexity = {'field_blocks': 0, 'gram_topk': 0, 'learned_blocker': 1, 'minhash_lsh': 1, 'union': 2}
            selected = min(indistinguishable, key=lambda method: (complexity[method], summary[method]['weighted_method_seconds']))
            index['recommendation'] = selected
            lines += ['', f'Complete feasible macro comparison selects `{selected}` under the predeclared paired-interval and simpler-method rule.',
                'The intervals describe validation selection, not an equivalence test or untouched confirmation result.', '',
                '| Method | Macro F1 [95% CI] | Paired change CI vs best | Weighted method s |', '|---|---|---|---:|']
            for method, row in summary.items():
                low, high = row['paired_deltas'][best]
                lines.append(f"| {method} | {row['macro_f1']:.4f} {row['f1_95ci']} | [{low:+.4f}, {high:+.4f}] | {row['weighted_method_seconds']:.2f} |")
            if len(summary) == 1:
                lines += ['', f'`{selected}` is the only complete feasible method. This is a feasibility-based selection, not evidence of statistical superiority over the unavailable alternatives. A self-comparison interval of [0, 0] has no comparative meaning.']
            selection_path = ROOT / 'bench/selection.json'
            selection = json.loads(selection_path.read_text())
            selection.update(candidate_selection='selected on validation; pending latency and frozen confirmation',
                selected_candidate=selected, candidate_macro_evidence=summary,
                candidate_ineligible_methods=index['ineligible_methods'])
            selection_path.write_text(json.dumps(selection, indent=2) + '\n')
        else:
            index['status'] = 'no_complete_feasible_winner'
            lines += ['', 'No method has complete feasible evidence and both FEBRL validation gates; no default selected.']
    else:
        lines += ['', 'Missing compatible completed comparisons: ' + ', '.join(index['missing']) + '.']
    lines += ['', 'Macro gives each corpus one vote; FEBRL all/SSN-hidden split its vote. Paired intervals use 2,000 namespaced PCG64 group draws, seed derived from 2026091902/candidate_macro/corpus. Infeasible methods are not assigned zero and no corpus is omitted to make their macro complete.', '',
        'This selection used no confirmation scores and promoted no model. Subsequent held-out measurements are reported in BENCHMARKS.md. Shared-session stage costs do not establish the local 60-second gate.']
    lines += ['', *[f"- `{name}`: [{row['run_id']}](../{row['manifest']})." for name, row in index['runs'].items()]]
    (ROOT / 'bench/CANDIDATES.md').write_text('\n'.join(lines) + '\n')
    (ROOT / 'bench/candidate_pairs_index.json').write_text(json.dumps(index, indent=2) + '\n')
    print(json.dumps({'completed': list(index['runs']), 'missing': index['missing'], 'recommendation': index.get('recommendation')}))


if __name__ == '__main__':
    main()
