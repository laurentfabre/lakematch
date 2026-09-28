"""Resume control-flow checks: saved predictions only, inference is forbidden."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('simbeat_resume_subject', ROOT / 'bench/simbeat.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
import simbeat_audit as a

WORK = ROOT / 'data/runs/simbeat'


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


@pytest.fixture
def cache(tmp_path, monkeypatch):
    if not WORK.is_dir():
        pytest.skip('local benchmark artifacts are required')
    work = tmp_path / 'work'
    work.mkdir()
    name = 'abt_buy'
    for child in WORK.iterdir():
        if child.name != name:
            (work / child.name).symlink_to(child, target_is_directory=child.is_dir())
    p = work / name
    p.mkdir()
    for child in (WORK / name).iterdir():
        if child.name not in ('confirmation.json', 'test_predictions.json'):
            (p / child.name).symlink_to(child, target_is_directory=child.is_dir())
    recorded = s.read(WORK / name / 'confirmation.json')
    rows = s.read(WORK / name / 'test_predictions.json')
    lock = s.read(work / 'selection.json')
    frozen = {label: s.read(s.metric_path(work, name, v)) for label, v in
              [('chosen', lock['chosen_variant']), ('jaro_winkler', 'jaro_winkler')]}
    expected = a.prediction_provenance(work, name, lock, frozen)

    def forbidden(*args, **kwargs):
        pytest.fail('resume attempted corpus loading, fitting, Runtime or model inference')

    monkeypatch.setattr(s, 'Runtime', forbidden)
    monkeypatch.setattr(s.corpora, name, forbidden)
    monkeypatch.setattr(s.matcher, 'train', forbidden)
    monkeypatch.setattr(s.matcher, 'score', forbidden)
    monkeypatch.setattr(s.PipelineModel, 'load', forbidden)
    return work, p, rows, recorded, expected


def test_resume_rejects_legacy_orphan_before_spark(cache):
    work, p, rows, _, _ = cache
    save(p / 'test_predictions.json', rows)
    with pytest.raises(a.AuditError, match='Unbound legacy'):
        s.confirm(work, 'abt_buy')
    assert not (p / 'confirmation.json').exists()


def test_resume_rejects_stale_envelope_before_spark(cache):
    work, p, rows, recorded, expected = cache
    stale = copy.deepcopy(expected)
    stale['inputs_sha256']['pairs'] = '0' * 64
    save(p / 'test_predictions.json', {'schema_version': 1, 'provenance': stale, 'plan': recorded['plan'], 'rows': rows})
    with pytest.raises(a.AuditError, match='Stale prediction'):
        s.confirm(work, 'abt_buy')
    assert not (p / 'confirmation.json').exists()


def test_bound_envelope_resume_finishes_from_cache_without_inference(cache):
    work, p, rows, recorded, expected = cache
    path = p / 'test_predictions.json'
    save(path, {'schema_version': 1, 'provenance': expected, 'plan': recorded['plan'], 'rows': rows})
    before = path.read_bytes()
    s.confirm(work, 'abt_buy')
    completed = s.read(p / 'confirmation.json')
    assert path.read_bytes() == before
    assert completed['chosen'] == recorded['chosen']
    assert completed['jaro_winkler'] == recorded['jaro_winkler']
    assert completed['selection_sha256'] == recorded['selection_sha256']
    # A second resume must validate and return without touching either file.
    confirmation_before = (p / 'confirmation.json').read_bytes()
    s.confirm(work, 'abt_buy')
    assert (p / 'confirmation.json').read_bytes() == confirmation_before
    assert path.read_bytes() == before


def test_completed_confirmation_is_checked_before_early_return(cache):
    work, p, _, recorded, _ = cache
    (p / 'test_predictions.json').symlink_to(WORK / 'abt_buy/test_predictions.json')
    recorded['chosen']['threshold'] = .95
    save(p / 'confirmation.json', recorded)
    with pytest.raises(a.AuditError, match='Confirmed model'):
        s.confirm(work, 'abt_buy')


def test_completed_historical_run_only_audits(cache, monkeypatch):
    work, _, _, _, _ = cache
    # Exercise the fast path without copying the 12 MB artifact or invoking Spark.
    data = s.read(s.RESULT)
    data['meta']['work_dir'] = str(work)
    result_path = work.parent / 'result.json'
    save(result_path, data)
    monkeypatch.setattr(s, 'RESULT', result_path)
    seen = []
    monkeypatch.setattr(s, 'audit', lambda result, root: seen.append((result['verdict'], root)))
    monkeypatch.setattr(s, 'manifest', lambda: pytest.fail('historical run attempted new execution manifest'))
    before = result_path.read_bytes()
    s.run(work)
    assert seen == [('not_beaten', work)]
    assert result_path.read_bytes() == before


@pytest.mark.parametrize('change', ['label', 'probability', 'id'])
def test_rehashed_predictions_must_reproduce_input_labels_and_counts(cache, change):
    work, p, rows, recorded, _ = cache
    row = rows[0]
    if change == 'label':
        row['label'] = 1.0 - row['label']
    elif change == 'probability':
        row['p_chosen'] = 0.0 if row['p_chosen'] >= recorded['chosen']['threshold'] else 1.0
    else:
        row['l_id'] = 'not-a-test-record'
    path = p / 'test_predictions.json'
    save(path, rows)
    recorded['predictions_sha256'] = a.file_hash(path)
    save(p / 'confirmation.json', recorded)
    with pytest.raises(a.AuditError, match='pair IDs/labels|reproduce recorded counts'):
        s.confirm(work, 'abt_buy')


@pytest.mark.parametrize('change', ['missing', 'udf'])
def test_actual_test_plan_is_required_and_inspected_even_after_rehash(cache, change):
    work, p, _, recorded, _ = cache
    (p / 'test_predictions.json').symlink_to(WORK / 'abt_buy/test_predictions.json')
    plan = p / 'test_builtins.plan.txt'
    text = plan.read_text()
    plan.unlink()  # Remove the fixture symlink, never modify its canonical target.
    if change == 'udf':
        plan.write_text(text + '\nArrowEvalPython\n')
        recorded['plan']['builtins']['sha256'] = a.file_hash(plan)
    save(p / 'confirmation.json', recorded)
    with pytest.raises(a.AuditError, match='Missing evidence|unexpected UDF'):
        s.confirm(work, 'abt_buy')


def test_uncached_confirmation_rejects_changed_code_before_spark(cache, monkeypatch):
    work, p, _, _, _ = cache
    stale = copy.deepcopy(s.read(work / "manifest.json"))
    stale["source_sha256"] = {"changed.py": "0" * 64}
    monkeypatch.setattr(s, "manifest", lambda: stale)
    with pytest.raises(a.AuditError, match="Live manifest differs"):
        s.confirm(work, "abt_buy")
    assert not (p / "test_predictions.json").exists()
    assert not (p / "confirmation.json").exists()


def test_uncached_confirmation_rejects_nonwinning_selection_before_spark(cache, monkeypatch):
    work, p, _, _, _ = cache
    lock = copy.deepcopy(s.read(work / 'selection.json'))
    lock['chosen_families'] = []
    lock['chosen_variant'] = 'levenshtein'
    for corpus in s.CORPORA:
        row = s.read(s.metric_path(work, corpus, 'levenshtein'))
        lock['models'][corpus]['chosen'] = {k: row[k] for k in ('model_sha256', 'threshold')}
    (work / 'selection.json').unlink()
    save(work / 'selection.json', lock)
    monkeypatch.setattr(s, 'manifest', lambda: s.read(work / 'manifest.json'))
    with pytest.raises(a.AuditError, match='Chosen families mismatch'):
        s.confirm(work, 'abt_buy')
    assert not (p / 'test_predictions.json').exists()
    assert not (p / 'confirmation.json').exists()
