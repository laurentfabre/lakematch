"""Read-only ZR-4 checks over sealed comparisons, identities and publication."""
from collections import Counter
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tarfile
import xml.etree.ElementTree as ET

from lakematch.benchmark.clusters import cluster_metrics
from lakematch.config import DEFAULTS
from evidence import ROOT, sha256
from report_clusters import COMMON, NATIVE, macro
from report_identity import DEPS as IDENTITY_DEPS, audit

PUBLICATION_DEPS = NATIVE | {'src/lakematch/identity.py', 'src/lakematch/publication.py',
    'src/lakematch/cluster_job.py', 'src/lakematch/engine.py', 'src/lakematch/cli.py',
    'src/lakematch/quality/native.py', 'src/lakematch/quality/__init__.py',
    'tools/check_cluster_cli.py', 'tools/run_identity_increment.py', 'tools/offline.sb',
    'tools/offline_run.py', 'bench/PUBLICATION_PLAN.md', 'pyproject.toml', 'requirements-local.lock'}


def sealed(kind, dependencies):
    found = []
    for line in (ROOT / 'experiments/runs.jsonl').read_text().splitlines():
        event = json.loads(line)
        if event['kind'] != kind:
            continue
        manifest = json.loads((ROOT / event['manifest']).read_text())
        if all(manifest['source_files'].get(path) == sha256(ROOT / path) for path in dependencies):
            found.append((event, manifest))
    assert found, f'Missing compatible-source {kind} evidence'
    event, manifest = found[-1]
    assert event['status'] == 'passed' and manifest['exit_code'] == 0, f'{kind} failed'
    assert 'no live members' in manifest['cleanup'], f'{kind} process cleanup missing'
    paths = {}
    for artifact in manifest['artifacts']:
        path = ROOT / artifact['path']
        assert path.is_file() and sha256(path) == artifact['sha256'], f'Missing/changed {kind} artifact {path}'
        paths[path.name] = path
    return event, paths


def unpack(paths, name):
    report = json.loads(paths['report.json'].read_text())
    assert report['status'] == 'completed' and report['confirmation_scored'] is False
    assert 'Verified OS denies non-loopback network access' in paths['stdout.txt'].read_text()
    payload = {}
    with tarfile.open(paths[name]) as archive:
        assert archive.extractfile('report.json').read() == paths['report.json'].read_bytes()
        for relative, expected in report['evidence_files'].items():
            content = archive.extractfile(relative).read()
            assert hashlib.sha256(content).hexdigest() == expected
            if relative.endswith('.json'):
                payload[relative] = json.loads(content)
    return report, payload


def check():
    errors, comparisons, identities = [], {}, {}
    for corpus in ('febrl3', 'historical_50k'):
        try:
            event, paths = sealed('cluster-' + corpus, COMMON | NATIVE | {'tools/run_clusters.py', 'pyproject.toml', 'requirements-local.lock'})
            report, payload = unpack(paths, 'cluster-evidence.tar.gz')
            if 'replay_reference' in report:
                from report_cluster_replay import audit as audit_replay
                audit_replay(report, payload)
            assert report['cleanup'] == 'succeeded'
            assert {row['method'] for row in report['rows']} == {'connected_components', 'center', 'star', 'verified_merge'}
            for row in report['rows']:
                pred = payload[row['method'] + '.predictions.json']
                assert all(row[key] == value for key, value in cluster_metrics(pred['truth'], pred['membership']).items())
                assert 0 < len(row['rounds']) <= report['config']['cluster']['max_rounds']
                assert row['bootstrap_resamples'] == 2000 and row['bootstrap_seed'] == 2026091902
            comparisons[corpus] = (report, payload)
            identity_event, identity_paths = sealed('identity-' + corpus, IDENTITY_DEPS)
            identity_report, identity_payload = unpack(identity_paths, 'identity-evidence.tar.gz')
            assert identity_report['comparison_run'] == event['run_id']
            assert identity_report['cleanup'] == 'succeeded'
            assert all(identity_report[key] is True for key in ('unchanged_input_stable', 'exact_journal_replay', 'incremental_repeat_idempotent'))
            audit(identity_payload, identity_report)
            identities[corpus] = (identity_event, identity_report, identity_payload)
            _, baseline_paths = sealed('splink-' + corpus, COMMON | {'tools/run_splink_cluster.py', 'bench/requirements-splink.lock'})
            baseline, predictions = unpack(baseline_paths, 'splink-evidence.tar.gz')
            assert baseline['prediction_endpoint_audit'] == 'all endpoints belong to the disjoint validation partition'
            pred = predictions['predictions.json']
            assert all(a in pred['truth'] and b in pred['truth'] for a, b, _ in pred['edges'])
            assert cluster_metrics(pred['truth'], pred['clusters']) == baseline['metrics']
        except (AssertionError, KeyError, OSError, ValueError, TypeError) as exc:
            errors.append(f'{corpus}: {exc}')
    if len(comparisons) == 2:
        summary = macro(comparisons)
        best = max(summary, key=lambda key: summary[key]['pairwise_f1'])
        eligible = [method for method, row in summary.items() if row['paired_deltas'][best][0] <= 0 <= row['paired_deltas'][best][1]]
        selected = min(eligible, key=lambda method: (method != 'connected_components', summary[method]['mean_seconds']))
        if DEFAULTS['cluster']['method'] != selected:
            errors.append('Shipped cluster method differs from the measured selection')
        observed_rounds = max(len(row['rounds']) for report, _ in comparisons.values() for row in report['rows'] if row['method'] == selected)
        if DEFAULTS['cluster']['max_rounds'] < observed_rounds:
            errors.append('Shipped cluster round bound is below measured convergence')
    try:
        _, paths = sealed('cluster-cli', PUBLICATION_DEPS)
        report = json.loads(paths['report.json'].read_text())
        assert report['status'] == 'completed' and report['cleanup'] == 'succeeded' and report['commits'] == 3
        assert report['confirmation_scored'] is False
        assert all(report[key] is True for key in ('crosswalk_equivalence', 'incremental_repeat_idempotent', 'historical_retry_does_not_rewind'))
        assert report['identity_reference_run'] == identities['febrl3'][0]['run_id']
        assert [row['reused'] for row in report['cli_runs']] == [False, False, True, False, True]
        assert 'Verified OS denies non-loopback network access' in paths['stdout.txt'].read_text()
        import pyarrow.parquet as pq
        with tarfile.open(paths['publication-evidence.tar.gz']) as archive:
            assert archive.extractfile('report.json').read() == paths['report.json'].read_bytes()
            snapshots = {}
            for name, publication in report['publications'].items():
                tables = {}
                for relative, expected in publication['files'].items():
                    content = archive.extractfile(name + '/' + relative).read()
                    assert hashlib.sha256(content).hexdigest() == expected
                    if relative.endswith('.parquet'):
                        tables.setdefault(relative.split('/')[0], []).extend(pq.read_table(BytesIO(content)).to_pylist())
                snapshots[name] = tables
            def canonical(rows):
                return Counter(json.dumps(row, sort_keys=True) for row in rows)
            reference = identities['febrl3'][2]
            assert canonical(snapshots['original']['crosswalk']) == canonical(reference['before.json'])
            assert canonical(snapshots['incremental']['crosswalk']) == canonical(reference['after.json'])
            assert canonical(snapshots['incremental']['changes']) == canonical(reference['changes.json'])
            assert canonical(snapshots['incremental']['cluster_events']) == canonical(reference['cluster_events.json'])
            assert canonical(snapshots['unchanged']['crosswalk']) == canonical(reference['after.json'])
            assert snapshots['unchanged']['cluster_events'] == []
            assert {row['change'] for row in snapshots['unchanged']['changes']} == {'unchanged'}
    except (AssertionError, KeyError, OSError, ValueError, TypeError) as exc:
        errors.append(f'CLI publication: {exc}')
    try:
        _, paths = sealed('publication-recovery-tests', {'src/lakematch/publication.py', 'tests/test_publication.py'})
        tree = ET.parse(paths['publication-tests.xml'])
        assert len(tree.findall('.//testcase')) == 3
        assert not any(tree.findall('.//' + name) for name in ('failure', 'error', 'skipped'))
    except (AssertionError, KeyError, OSError, ET.ParseError) as exc:
        errors.append(f'Publication process recovery: {exc}')
    return errors
