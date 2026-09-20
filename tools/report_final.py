#!/usr/bin/env python3
"""Audit sealed frozen measurements and render benchmark/scale reports."""
import hashlib
import json
import tarfile

from lakematch.benchmark.metrics import bootstrap, evaluate, select
from evidence import ROOT, sha256

PAIR_CORPORA = ('bpid', 'abt_buy', 'amazon_google', 'walmart_amazon', 'dblp_acm', 'affiliations')
EXPECTED = ['frozen-linkage-all', 'frozen-linkage-no_ssn', *['frozen-pairs-' + x for x in PAIR_CORPORA],
            *['scale-' + str(n) for n in (1000, 10000, 100000, 1000000)]]


def same_metrics(actual, recorded):
    assert all(abs(value - recorded[key]) < 1e-12 for key, value in actual.items()), 'Metric reconstruction differs'


def audit_scores(report, payloads, freeze):
    entry = freeze['models'][report['corpus']]
    for key in ('entity', 'candidates', 'features', 'matcher', 'decision'):
        assert report['config'][key] == entry['config'][key], f'Frozen config changed: {key}'
    assert report['frozen_model'] == entry['model']
    assert report['manifest'] == entry['corpus_manifest']
    files = entry['corpus_manifest']['files']
    for item in files.values():
        assert sha256(ROOT / item['path']) == item['sha256']
    labels = [json.loads(line) for line in (ROOT / files['pairs']['path']).read_text().splitlines()]
    policy = report['config']['decision']
    if 'partitions' in report:
        scores = payloads['all.predictions.json']
        found = {(row['a_id'], row['b_id']) for row in scores}
        decisions = select([(row['a_id'], row['b_id'], row['p']) for row in scores],
                           policy['threshold'], policy['cardinality'])
        simple = [(row['a_id'], row['b_id'], row['cos']) for row in scores]
        records = [json.loads(line) for line in (ROOT / files['left']['path']).read_text().splitlines()]
        for split, recorded in report['partitions'].items():
            anchors = {row['rec_id'] for row in records if row['split'] == split}
            selected = {pair for pair in decisions if pair[0] in anchors}
            positives = {(row['a_id'], row['b_id']) for row in labels if row['split'] == split and row['label']}
            truth = {**dict.fromkeys(selected, 0.), **dict.fromkeys(positives, 1.)}
            metric, groups = evaluate(selected, truth, {pair: pair[0] for pair in truth})
            groups.update({key: [0, 0, 0, 0] for key in anchors - groups.keys()})
            same_metrics(metric, recorded)
            assert bootstrap(groups)['f1_95ci'] == recorded['f1_95ci']
            assert recorded['candidate_recall'] == len(positives & found) / len(positives)
            payload = payloads[split + '.predictions.json']
            assert {tuple(pair) for pair in payload['selected']} == selected
            assert {(a, b): y for a, b, y, _ in payload['labels']} == truth
            for name, row in recorded['baselines'].items():
                chosen = select(simple, row['threshold'], 'many_to_one' if name == 'nearest_neighbour' else 'one_to_one')
                chosen = {pair for pair in chosen if pair[0] in anchors}
                bt = {**dict.fromkeys(chosen, 0.), **dict.fromkeys(positives, 1.)}
                bm, bg = evaluate(chosen, bt, {pair: pair[0] for pair in bt})
                bg.update({key: [0, 0, 0, 0] for key in anchors - bg.keys()})
                same_metrics(bm, row)
                assert bootstrap(bg, groups)['paired_delta_95ci'] == row['paired_delta_95ci']
        target = .97 if report['corpus'].endswith('_all') else .96
        assert report['quality_target'] == target
        assert report['quality_passed'] == (report['partitions']['confirmation']['f1'] >= target)
        assert report['latency_passed'] == (report['process_wall_seconds'] < 60)
        assert report['acceptance_passed'] == (report['quality_passed'] and report['latency_passed'])
    else:
        payload = payloads['heldout.predictions.json']
        rows = [row for row in labels if row['split'] == report['partition']]
        truth = {(row['a_id'], row['b_id']): row['label'] for row in rows}
        groups = {(row['a_id'], row['b_id']): row['group'] for row in rows}
        assert {(a, b): y for a, b, y, _ in payload['labels']} == truth
        decisions = select(payload['scores'], policy['threshold'], policy['cardinality'])
        metric, totals = evaluate(decisions, truth, groups)
        same_metrics(metric, report['metrics'])
        assert bootstrap(totals)['f1_95ci'] == report['metrics']['f1_95ci']
        positives = {pair for pair, label in truth.items() if label}
        found = {(a, b) for a, b, _ in payload['scores']}
        assert report['candidate_recall'] == len(positives & found) / len(positives)
        for row in report['baselines'].values():
            bm, bg = evaluate(select(payload['cosine_scores'], row['threshold'], row['cardinality']), truth, groups)
            same_metrics(bm, row)
            assert bootstrap(bg, totals)['paired_delta_95ci'] == row['paired_delta_95ci']


def collect():
    freeze_path = ROOT / 'bench/freeze.json'
    freeze = json.loads(freeze_path.read_text())
    latest = {}
    for line in (ROOT / 'experiments/runs.jsonl').read_text().splitlines():
        event = json.loads(line)
        if event['kind'] in EXPECTED:
            latest[event['kind']] = event
    results, errors = {}, []
    for kind in EXPECTED:
        if kind not in latest:
            errors.append(f'{kind}: no completed experiment')
            continue
        event = latest[kind]
        manifest = json.loads((ROOT / event['manifest']).read_text())
        try:
            failed_scale = kind.startswith('scale-') and event['status'] == 'failed' and manifest['exit_code'] != 0
            assert failed_scale or (event['status'] == 'passed' and manifest['exit_code'] == 0), f"process {event['status']}"
            assert 'no live members' in manifest['cleanup']
            assert manifest['started_at'] > freeze['frozen_at'], 'Run predates model freeze'
            original_sources = all(manifest['source_files'].get(path) == expected for path, expected in freeze['execution_sources'].items())
            if not original_sources:
                from compatibility import validate
                declaration = validate(freeze)
                assert all(manifest['source_files'].get(path) == value for path, value in declaration['execution_sources'].items())
            paths = {}
            for artifact in manifest['artifacts']:
                path = ROOT / artifact['path']
                assert path.is_file() and sha256(path) == artifact['sha256'], f'Missing/changed {path}'
                paths[path.name] = path
            assert sha256(paths['freeze.json']) == sha256(freeze_path)
            if not original_sources:
                assert sha256(paths['source_compatibility.json']) == sha256(ROOT / 'bench/source_compatibility.json')
            assert 'Verified OS denies non-loopback network access' in paths['stdout.txt'].read_text()
            report = json.loads(paths['report.json'].read_text())
            if failed_scale:
                assert report['status'] == 'failed' and report.get('error')
            else:
                assert report['status'] == 'completed' and report['cleanup'] == 'succeeded'
            assert report['freeze_sha256'] == sha256(freeze_path)
            archive_name = 'scale-evidence.tar.gz' if kind.startswith('scale-') else 'frozen-evidence.tar.gz'
            payloads = {}
            with tarfile.open(paths[archive_name]) as archive:
                assert archive.extractfile('report.json').read() == paths['report.json'].read_bytes()
                for name, expected in report['evidence_files'].items():
                    content = archive.extractfile(name).read()
                    assert hashlib.sha256(content).hexdigest() == expected
                    if name.endswith('.json'):
                        payloads[name] = json.loads(content)
            if kind.startswith('scale-'):
                assert report['confirmation_scored'] is False
                assert report['candidate_budget']['join_rows_after_cap'] <= 50000000
                assert report['candidate_budget']['candidate_pairs'] <= report['records'] // 2 * 5
                assert report['spark_events']['tasks'] > 0
                if failed_scale:
                    errors.append(f'{kind}: failed; partial counters retained, no completed output or quality claim')
                else:
                    assert report['spark_events']['completed_log_directories']
                    assert report['output_files'], 'Missing published-link checksums'
            else:
                assert report['confirmation_scored'] is True
                audit_scores(report, payloads, freeze)
            results[kind] = {'run_id': event['run_id'], 'manifest': event['manifest'],
                'report_path': str(paths['report.json'].relative_to(ROOT)), 'report_sha256': sha256(paths['report.json']),
                'report': report, 'runner_status': event['status'], 'runner_wall_seconds': event['wall_seconds']}
        except (AssertionError, KeyError, ValueError, OSError, TypeError) as exc:
            errors.append(f'{kind}: {exc}')
    return results, errors


def render(results, errors):
    lines = ['# Frozen benchmark measurements', '',
        'Models, thresholds, retrieval state and data were frozen before scoring. [Freeze](freeze.json); [plan](FINAL_PLAN.md).',
        'FEBRL is closed-world linkage after global cardinality. Other rows score only supplied held-out pairs after full-universe retrieval; unknown pairs remain unknown and missing positives count as false negatives. Shared-record caveats remain in each manifest.', '',
        '| Corpus / partition | Precision | Recall | F1 [95% CI] | Recall@5 | Wall s | NN F1 | Cosine F1 | Gate |',
        '|---|---:|---:|---|---:|---:|---:|---:|---|']
    hot_notes = []
    for kind, entry in results.items():
        if kind.startswith('scale-'):
            continue
        report = entry['report']
        linkage = 'partitions' in report
        rows = report['partitions'] if linkage else {report['partition']: report['metrics']}
        for split, row in rows.items():
            baseline = row['baselines'] if linkage else report['baselines']
            recall = row['candidate_recall'] if linkage else report['candidate_recall']
            seconds = report['process_wall_seconds'] if linkage else report['wall_seconds_including_spark']
            gate = ('pass' if report['acceptance_passed'] else 'FAIL') if linkage and split == 'confirmation' else 'diagnostic'
            ci = row['f1_95ci']
            lines.append(f"| {report['corpus']} / {split} | {row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} [{ci[0]:.4f}, {ci[1]:.4f}] | {recall:.4f} | {seconds:.2f} | {baseline['nearest_neighbour']['f1']:.4f} | {baseline['cosine_threshold']['f1']:.4f} | {gate} |")
    lines += ['', 'FEBRL wall time includes a fresh normal CLI process, imports, Spark startup, model reload, outputs and cleanup. Supplied-pair wall time includes Spark startup/cleanup and evaluation/reporting in the experiment process. Baseline timing is shared; no independent baseline latency claim.',
        'Each sealed report includes confusion counts, paired baseline-minus-model intervals, candidate/classifier loss, and positive-link missingness, Unicode and multi-value slices. Empty slices establish no coverage. The differing-name slice is a proxy for name corruption, not an annotation of typo causes.', '',
        'Live Jev requests/tokens/spend and remote compute spend for these offline runs are zero. Local hardware cost is unpriced. Earlier FEVM billing remains unreconciled, not zero.', '',
        'Reference figures are historical or published, with different splits, retrieval scopes and selection protocols. They are not acceptance evidence or head-to-head comparisons:', '',
        '| Corpus | Reference F1 | Provenance / limitation |', '|---|---|---|',
        '| FEBRL half-unmatched | Zingg 0.841–0.862; prototype 0.96–0.98 | Historical 2026-09-19, exposed corpus/removal outcomes |',
        '| FEBRL original | Nearest neighbour 1.000; Zingg 0.853–0.858 | Historical; fresh selected-pipeline original diagnostic still required |',
        '| BPID | Published best 0.788; Jev zero-shot 0.813 | EMNLP 2024 Industry / historical private split; not this disjoint confirmation |',
        '| Abt-Buy | Magellan 0.436; Ditto 0.893 | Mudgal 2018 / Li 2021, supplied-pair tasks |',
        '| Amazon-Google | Magellan 0.491; Ditto 0.756 | Same; original duplicates/conflicts resolved differently |',
        '| Walmart-Amazon | Magellan 0.719; Ditto 0.868 | Same; original supplied-pair splits |',
        '| DBLP-ACM | Magellan 0.984; Ditto 0.990 | Same; original supplied-pair splits |',
        '| FEBRL3 | Measured Splink 0.9979; verified merge 1.0000 | Training-only, entity-disjoint validation; [clustering evidence](CLUSTERS.md) |',
        '| historical_50k | Measured Splink 0.8580; verified merge 0.9392 | 10,082-record validation graph; not full 50k confirmation |',
        '| Leipzig Affiliations | Web URL overlap 0.832; Soft TF-IDF with location 0.442 | Aumueller/Rahm 2009, Table 3; different dataset version and web features; [extraction and caveats](AFFILIATIONS_REFERENCE.md) |',
        '| Synthetic scale | No accuracy reference target | [Measured bounded-work ladder](SCALE.md) |', '',
        'References and original provenance: [historical controlled benchmark](../spec/bench/README.md), [brief](../spec/BRIEF.md#benchmarks-and-known-tests).', '',
        'Method selection: [candidates](CANDIDATES.md), [classifiers](CLASSIFIERS.md), [compact features](COMPACT_FEATURES.md), [clustering](CLUSTERS.md). No held-out result is used to revise a model or threshold. Validation-selected package defaults are adopted; final execution compatibility and phase acceptance are checked separately. Frozen benchmark models and thresholds are unchanged; the separate synthetic UC acceptance model is tracked in MODELS.md.', '',
        'Evidence:', '', *[f"- `{kind}`: [{entry['run_id']}](../{entry['manifest']})." for kind, entry in results.items()]]
    try:
        from report_original import collect as collect_original
        original = collect_original()
        row = original['report']
        lines += ['', '## Original FEBRL diagnostic', '',
            f"Frozen selected model F1 {row['metrics']['f1']:.6f}, candidate recall {row['candidate_recall']:.6f}, "
            f"fresh CLI wall time {row['process_wall_seconds']:.2f}s. "
            f"Independent nearest-neighbour-only F1 {row['nearest_neighbour']['f1']:.6f}. "
            f"[{original['run_id']}](../{original['manifest']}).",
            row['exposure'] + '. This is not new holdout acceptance.']
    except (AssertionError, KeyError, OSError, TypeError, ValueError):
        lines += ['', 'Fresh original-FEBRL diagnostic is pending compatible, sealed execution evidence.']
    if errors:
        lines += ['', 'Incomplete or failed evidence:', '', *['- ' + error for error in errors]]
    (ROOT / 'bench/BENCHMARKS.md').write_text('\n'.join(lines) + '\n')
    scale = ['# Synthetic scale measurements', '',
        'Exact duplicates with unique SHA-256 codes; separate 400-record training namespace. These results measure native work and cap-induced loss, not realistic corruption accuracy. Unchanged local[2], default JVM memory, k=5, four hash tables, cap 400, 50-million retained join rows. [Plan](FINAL_PLAN.md).', '',
        '| Total records | Join rows before cap | After cap | Candidate pairs | Recall@5 | F1 | Wall s | Records/s | Shuffle read/write bytes | Max/median task ms ratio |',
        '|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|']
    for kind, entry in results.items():
        if not kind.startswith('scale-'):
            continue
        r = entry['report']; b = r['candidate_budget']; e = r['spark_events']
        if entry['runner_status'] != 'passed':
            scale.append(f"| {r['records']} | {b['join_rows_before_cap']} | {b['join_rows_after_cap']} | {b['candidate_pairs']} | unavailable | unavailable | {entry['runner_wall_seconds']:.2f} (failed) | unavailable | {e['total_shuffle_read_bytes']} / {e['total_shuffle_write_bytes']} | {e['maximum_to_median_task_duration']:.2f} |")
            hot_notes.append('The million-record run failed during candidate-table materialization with Java heap exhaustion. '
                'Its join counters and completed-task shuffle are partial observations. F1, candidate recall and successful throughput '
                'were not measured. Spark table cleanup also failed after the JVM failure; the runner verified termination '
                'of the owned process group. Memory and candidate budgets were not increased.')
            continue
        scale.append(f"| {r['records']} | {b['join_rows_before_cap']} | {b['join_rows_after_cap']} | {b['candidate_pairs']} | {r['candidate_recall']:.4f} | {r['metrics']['f1']:.4f} | {r['wall_seconds_including_spark']:.2f} | {r['records_per_second_including_fit_log_startup_cleanup']:.1f} | {e['total_shuffle_read_bytes']} / {e['total_shuffle_write_bytes']} | {e['maximum_to_median_task_duration']:.2f} |")
        if 'hot_key_case' in r:
            hot = r['hot_key_case']; hb = hot['candidate_budget']
            hot_notes.append(f"Hot-key fixture: {hot['records']} indistinguishable records; pre-cap join rows {hb['join_rows_before_cap']}, post-cap {hb['join_rows_after_cap']}, recall {hot['candidate_recall']:.4f}. Dropping nonselective buckets bounds work at the expense of recall.")
    scale += ['', *hot_notes, '', 'Wall/throughput includes training, model logging, generation, retrieval, scoring, output and Spark cleanup. Shuffle includes all task attempts; peak execution memory is per task, not process RSS. Raw event logs and output checksums are sealed. Local publication crash/retry evidence is [separate](PUBLICATION.md); remote fixture recovery evidence is tracked separately in [SERVERLESS.md](SERVERLESS.md).', '',
        *['- ' + error for error in errors if error.startswith('scale-')]]
    (ROOT / 'bench/SCALE.md').write_text('\n'.join(scale) + '\n')


def main():
    results, errors = collect()
    render(results, errors)
    body = {'status': 'complete_measurements' if not errors else 'partial',
        'freeze_sha256': sha256(ROOT / 'bench/freeze.json'), 'errors': errors,
        'runs': {kind: {key: value for key, value in entry.items() if key != 'report'} for kind, entry in results.items()},
        'febrl_acceptance': {kind: entry['report']['acceptance_passed'] for kind, entry in results.items() if kind.startswith('frozen-linkage-')}}
    (ROOT / 'bench/final_index.json').write_text(json.dumps(body, indent=2) + '\n')
    print(json.dumps(body))


if __name__ == '__main__':
    main()
