"""Synthetic access guards: no real benchmark fitting or TEST scoring."""
import builtins
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('simbeat_isolation_subject', ROOT / 'bench/simbeat.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
import simbeat_inputs as inputs
import simbeat_holdout as holdout
import simbeat_audit as audit


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True) + '\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    root = tmp_path / 'inputs'
    metadata = {'schema_version': 2, 'source_sha256': {p: 'f' * 64 for p in s.DATA_FILES}, 'corpora': {}}
    for name, kind in zip(s.CORPORA, ('linkage', 'pairs', 'pairs', 'dedupe')):
        records = {'left': [{'id': f'l{i}', 'name': f'Name {i}'} for i in range(30)],
                   'right': [{'id': f'r{i}', 'name': f'Name {i}'} for i in range(30)], 'pairs': []}
        if kind == 'dedupe':
            records['right'] = copy.deepcopy(records['left'])
        development = {'pairs': [], 'truth': [], 'units': []}
        test = {'pairs': [], 'truth': [], 'units': []}
        if kind == 'pairs':
            for i, split in enumerate(('train', 'valid', 'test')):
                row = {'l_id': f'l{i}', 'r_id': f'r{i}', 'split': split}
                records['pairs'].append(row)
                (test if split == 'test' else development)['pairs'].append({**row, 'label': 1.0})
        # Nonpair truth is empty; every candidate is a negative. All left records
        # still matter to linkage evaluation. Partitioned units are set per test.
        files = {p: save(root / name / p, data) for p, data in
                 [('records.json', records), ('development.json', development)]}
        metadata['corpora'][name] = {'name': name, 'kind': kind, 'fields': {'name': {'type': 'code'}},
                                    'files': files, 'heldout_sha256': save(root / name / 'heldout.json', test)}
    save(root / 'manifest.json', metadata)
    monkeypatch.setattr(inputs, 'DEFAULT_INPUTS', root)
    return root, metadata


def deny_outcomes(monkeypatch, root):
    """Guard actual opens as well as every eager loader, including manifest hashes."""
    raw_dirs = [s.corpora.DATA / n for n in ('febrl4', 'bpid', 'abt_buy', 'leipzig')]
    original_io, original_builtin = io.open, builtins.open

    def guard(original):
        def opened(file, *args, **kwargs):
            if isinstance(file, (str, bytes, Path)):
                path = Path(file).resolve()
                if path.name == 'heldout.json' or any(path.is_relative_to(d.resolve()) for d in raw_dirs):
                    pytest.fail(f'development opened an outcome source: {path}')
            return original(file, *args, **kwargs)
        return opened

    monkeypatch.setattr(io, 'open', guard(original_io))
    monkeypatch.setattr(builtins, 'open', guard(original_builtin))
    def forbidden(*args, **kwargs):
        pytest.fail('development called an eager corpus loader or TEST release')
    for name in s.CORPORA:
        monkeypatch.setattr(s.corpora, name, forbidden)
        monkeypatch.setitem(s.corpora.LOADERS, name, forbidden)
    monkeypatch.setattr(holdout, 'release_labels', forbidden)


def test_development_manifest_never_opens_raw_or_test_sources(bundle, tmp_path, monkeypatch):
    root, metadata = bundle
    model = tmp_path / 'embedding' / 'revision'
    model.mkdir(parents=True)
    (model / 'model.bin').write_bytes(b'synthetic model commitment')
    monkeypatch.setattr(s.embeddings, 'resolve', lambda cfg: SimpleNamespace(model='synthetic', path=str(model)))
    deny_outcomes(monkeypatch, root)
    generated = s.manifest()
    assert generated['protocol'] == 'simbeat-v2'
    assert generated['data_sha256'] == metadata['source_sha256']
    assert generated['input_bundle'] == metadata


@pytest.mark.parametrize('name', s.CORPORA)
def test_prepare_and_evaluate_do_not_open_outcomes(bundle, tmp_path, monkeypatch, spark, name):
    root, metadata = bundle
    work = tmp_path / 'work'
    save(work / 'manifest.json', {'protocol': 'simbeat-v2', 'input_bundle': metadata})
    # Assign all linkage units using the same production partition expression.
    if name == 'febrl4_half_unmatched':
        units = spark.createDataFrame([(f'l{i}',) for i in range(30)], 'l_id string')
        dev_units = [r.l_id for r in units.withColumn('split', s.bucket('l_id')).filter("split != 'test'").collect()]
        metadata['corpora'][name]['files']['development.json'] = save(
            root / name / 'development.json', {'pairs': [], 'truth': [], 'units': dev_units})
        save(root / 'manifest.json', metadata)
        save(work / 'manifest.json', {'protocol': 'simbeat-v2', 'input_bundle': metadata})
    deny_outcomes(monkeypatch, root)
    monkeypatch.setattr(s, 'Runtime', lambda cfg: SimpleNamespace(spark=spark, close=lambda **kw: None))
    monkeypatch.setattr(s, 'entity_sides', lambda rt, cfg, left, right: (left, right))
    monkeypatch.setattr(s.candidates, 'generate', lambda L, R, cfg: L.selectExpr('id as l_id').crossJoin(
        R.selectExpr('id as r_id')).selectExpr('l_id', 'r_id', '1.0 as cand_score', '1 as cand_rank', '0.0 as cand_gap'))
    def comparison(rt, c, work, pairs, L, R, *args, **kwargs):
        assert pairs.filter("part = 'test'").count() == 0
        return pairs.withColumn('lev_name', s.F.lit(1.0)), ['lev_name'], {}
    monkeypatch.setattr(s, 'pair_table', comparison)
    s.prepare(work, name)
    dev = spark.read.parquet(str(work / name / 'development'))
    test = spark.read.parquet(str(work / name / 'test_candidates'))
    assert dev.filter("part = 'test'").count() == 0
    assert 'label' not in test.columns and test.count() > 0
    class FitBoundary(Exception):
        pass
    def never_fit(*args, **kwargs):
        raise FitBoundary
    monkeypatch.setattr(s.matcher, 'train', never_fit)
    with pytest.raises(FitBoundary):
        s.evaluate(work, name, ['levenshtein'])


def test_selection_never_opens_outcomes(bundle, tmp_path, monkeypatch):
    root, metadata = bundle
    work = tmp_path / 'work'
    monkeypatch.setattr(s, 'RESULT', tmp_path / 'absent-result.json')
    monkeypatch.setattr(s, 'manifest', lambda: {'protocol': 'simbeat-v2', 'input_bundle': metadata})
    class ConfirmationBoundary(Exception):
        pass
    def child(work, action, corpus, variants=()):
        if action == 'confirm':
            assert s.read(work / 'selection.json')['selected_on'] == 'validation'
            raise ConfirmationBoundary
        if action == 'evaluate':
            for variant in variants:
                save(s.metric_path(work, corpus, variant), {'f1': .8, 'model_sha256': 'a' * 64, 'threshold': .5})
    monkeypatch.setattr(s, 'child', child)
    deny_outcomes(monkeypatch, root)
    with pytest.raises(ConfirmationBoundary):
        s.run(work)
    lock = s.read(work / 'selection.json')
    assert lock['chosen_variant'] == 'levenshtein'
    assert not lock['forward_selection'][0]['accepted']


@pytest.fixture
def frozen(bundle, tmp_path):
    root, metadata = bundle
    work = tmp_path / 'frozen'
    manifest = {'protocol': 'simbeat-v2', 'input_bundle': metadata, 'shortlist': ['padded_bigram_dice'],
                'seed': 0, 'bootstrap_replicates': 1000}
    variants = ['levenshtein', 'jaro_winkler', 'both', 'levenshtein + padded_bigram_dice']
    valid = {}
    metric = {**s.metrics(['unit'], np.array([[1, 0, 0]])), 'counts_by_unit': [[1, 0, 0]], 'threshold': .5}
    for variant in variants:
        valid[variant] = {}
        for corpus in s.CORPORA:
            path = work / corpus / 'models' / s.key(variant)
            columns = ['jw_name'] if variant == 'jaro_winkler' else ['lev_name']
            save(path / 'stages/0_VectorAssembler/metadata/part-00000', {
                'class': 'org.apache.spark.ml.feature.VectorAssembler', 'paramMap': {'inputCols': columns}})
            valid[variant][corpus] = {**metric, 'columns': columns, 'model_sha256': audit.tree_hash(path)}
    valid['chosen'] = valid['levenshtein']
    lock = {'manifest_sha256': audit.digest(manifest), 'selected_on': 'validation', 'chosen_variant': 'levenshtein',
            'chosen_families': [], 'variants': variants, 'forward_selection': [{
                'base': 'levenshtein', 'base_mean_f1': 1.0, 'options': {variants[-1]: 1.0},
                'best': variants[-1], 'gain': 0.0, 'accepted': False}],
            'models': {c: {label: {k: valid['levenshtein' if label == 'chosen' else label][c][k]
                                  for k in ('model_sha256', 'threshold')} for label in audit.LABELS} for c in s.CORPORA}}
    save(work / 'manifest.json', manifest)
    save(work / 'selection.json', lock)
    return root, work, manifest, lock, valid


def test_release_reads_sealed_payload_once_and_resume_zero_times(frozen, monkeypatch):
    root, work, manifest, lock, valid = frozen
    original = io.open
    reads = []
    def counted(file, *args, **kwargs):
        if Path(file).name == 'heldout.json':
            reads.append(str(file))
        return original(file, *args, **kwargs)
    monkeypatch.setattr(io, 'open', counted)
    first = holdout.release_labels(work, 'bpid', lock, manifest, valid)
    assert len(reads) == 1 and first['pairs'][0]['split'] == 'test'
    assert holdout.release_labels(work, 'bpid', lock, manifest, valid) == first
    assert len(reads) == 1


@pytest.mark.parametrize('corruption', ['missing_lock', 'wrong_winner', 'changed_model', 'sealed_bytes', 'stale_release'])
def test_release_rejects_corruption_without_inference(frozen, monkeypatch, corruption):
    root, work, manifest, lock, valid = frozen
    if corruption == 'missing_lock':
        (work / 'selection.json').unlink()
    elif corruption == 'wrong_winner':
        lock['chosen_families'] = ['padded_bigram_dice']
        lock['chosen_variant'] = 'levenshtein + padded_bigram_dice'
        save(work / 'selection.json', lock)
    elif corruption == 'changed_model':
        path = work / 'bpid/models' / s.key('levenshtein') / 'corruption'
        path.write_bytes(b'changed')
    elif corruption == 'sealed_bytes':
        (root / 'bpid/heldout.json').write_text('{}')
        # Public validation is intentionally independent of sealed content.
        assert inputs.public_manifest() == manifest['input_bundle']
    else:
        holdout.release_labels(work, 'bpid', lock, manifest, valid)
        path = work / 'bpid/heldout_release.json'
        data = s.read(path); data['selection_sha256'] = '0' * 64; save(path, data)
    if corruption not in ('sealed_bytes', 'stale_release'):
        original = io.open
        def guarded(file, *args, **kwargs):
            assert Path(file).name != 'heldout.json', 'opened TEST before validating selection/models'
            return original(file, *args, **kwargs)
        monkeypatch.setattr(io, 'open', guarded)
    with pytest.raises(audit.AuditError):
        holdout.release_labels(work, 'bpid', lock, manifest, valid)


@pytest.mark.parametrize('corruption', [None, 'relabelled_pairs', 'labelled_candidates', 'test_in_development'])
def test_v2_audit_binds_synthetic_predictions_to_released_labels(frozen, corruption):
    import pyarrow as pa
    import pyarrow.parquet as pq
    root, work, manifest, lock, valid = frozen
    payload = holdout.release_labels(work, 'bpid', lock, manifest, valid)
    p = work / 'bpid'
    def parquet(name, rows):
        (p / name).mkdir(exist_ok=True)
        pq.write_table(pa.Table.from_pylist(rows), p / name / 'part-0.parquet')
    pair = {'l_id': 'l2', 'r_id': 'r2', 'part': 'test'}
    parquet('test_candidates', [{**pair, **({'label': 1.0} if corruption == 'labelled_candidates' else {})}])
    labelled = {**pair, 'label': 0.0 if corruption == 'relabelled_pairs' else payload['pairs'][0]['label']}
    parquet('test_pairs', [labelled])
    dev = {'l_id': 'l0', 'r_id': 'r0', 'part': 'valid', 'label': 1.0}
    parquet('pairs', [dev])
    parquet('development', [dev if corruption != 'test_in_development' else labelled])
    for side in ('left', 'right'):
        parquet(side, [{'id': 'synthetic', 'name': 'record'}])
    # These are declared fixture probabilities, never outputs of model scoring.
    rows = [{**labelled, 'p_chosen': .9, 'p_jaro_winkler': .9}]
    frozen_models = {label: valid['levenshtein' if label == 'chosen' else label]['bpid'] for label in audit.LABELS}
    if corruption:
        with pytest.raises(audit.AuditError):
            audit.prediction_counts(work, 'bpid', rows, frozen_models)
    else:
        result = audit.prediction_counts(work, 'bpid', rows, frozen_models)
        assert result['chosen'][1].tolist() == [[1, 0, 0]]
        provenance = audit.prediction_provenance(work, 'bpid', lock, frozen_models)
        assert {'test_candidates', 'test_pairs', 'heldout_release'} <= set(provenance['inputs_sha256'])


def test_historical_report_renders_identically():
    from render_simbeat import render_report
    original = s.read(ROOT / 'bench/results/simbeat.json')
    assert render_report(original) == (ROOT / 'bench/SIMBEAT.md').read_text()


def test_new_run_outputs_cannot_replace_historical_paths(bundle, tmp_path, monkeypatch):
    # Exercise only output routing, reusing fixture metrics and forbidding workers.
    root, metadata = bundle
    original = s.read(ROOT / 'bench/results/simbeat.json')
    work = tmp_path / 'new-run'
    manifest = {**original['meta']['manifest'], 'protocol': 'simbeat-v2', 'input_bundle': metadata}
    lock = copy.deepcopy(original['selection_lock'])
    lock['manifest_sha256'] = s.digest(manifest)
    save(work / 'manifest.json', manifest)
    save(work / 'selection.json', lock)
    for corpus in s.CORPORA:
        save(work / corpus / 'confirmation.json', original['confirmation'][corpus])
        save(work / corpus / 'prepared.json', original['prepared'][corpus])
    historical = tmp_path / 'historical.json'
    save(historical, {'meta': {'work_dir': '/a-different-historical-run'}})
    before = historical.read_bytes()
    monkeypatch.setattr(s, 'RESULT', historical)
    monkeypatch.setattr(s, 'manifest', lambda: manifest)
    monkeypatch.setattr(s, 'child', lambda *args, **kwargs: None)
    monkeypatch.setattr(s, 'load_valid', lambda *args: copy.deepcopy(original['valid']))
    monkeypatch.setattr(s, 'audit', lambda *args: True)
    outputs = []
    monkeypatch.setattr(s, 'render', lambda result, destination: outputs.append(destination))
    s.run(work)
    assert (work / 'result.json').is_file()
    assert outputs == [work / 'report.md']
    assert historical.read_bytes() == before


def test_v2_report_targets_its_own_result_and_quotes_paths(tmp_path):
    import shlex
    from render_simbeat import render_report
    d = s.read(ROOT / 'bench/results/simbeat.json')
    d['meta']['manifest']['protocol'] = 'simbeat-v2'
    work = tmp_path / 'run with spaces'
    d['meta']['work_dir'] = str(work)
    report = render_report(d)
    for action in ('audit', 'render'):
        line = next(line for line in report.splitlines() if line.startswith(f'python bench/simbeat.py {action}'))
        assert shlex.split(line) == ['python', 'bench/simbeat.py', action, '--work-dir', str(work),
                                     '--result', str(work / 'result.json')]
    assert '[result.json](result.json)' in report
    assert '[results/simbeat.json]' not in report
