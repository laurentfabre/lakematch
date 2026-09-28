"""Read-only SIM-3 verification. Never imports Spark or loads models for inference.

JSON checks establish internal consistency; supplying work_dir also checks saved
predictions, input labels, model files and physical plans. Generation-time source
hashes remain historical provenance: editing the checker must not relabel a run.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CORPORA = ('febrl4_half_unmatched', 'bpid', 'abt_buy', 'leipzig_affiliations')
# The feature names are the simbeat-v1 contract, independent of the live shortlist.
PREFIXES = {'token_sort_lev': 'tsl', 'padded_bigram_dice': 'pbd', 'weighted_jaccard': 'wja',
            'qgram_count_cosine': 'qcc', 'soft_tfidf_lev': 'stl', 'osa': 'osa', 'lcs_indel': 'lci'}
UDF_MARKERS = ('pythonudf', 'batchevalpython', 'arrowevalpython', 'scalaudf')
LABELS = ('chosen', 'jaro_winkler')


class AuditError(ValueError):
    """The recorded experiment or its evidence is inconsistent/incomplete."""


def require(condition, message):
    if not condition:
        raise AuditError(message)


def read(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as e:
        raise AuditError(f'Cannot read evidence {path}: {e}') from e


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    try:
        with Path(path).open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                h.update(block)
    except OSError as e:
        raise AuditError(f'Missing evidence {path}') from e
    return h.hexdigest()


def tree_hash(path):
    path = Path(path)
    files = sorted(p for p in path.rglob('*') if p.is_file() and not p.name.startswith('.'))
    require(bool(files), f'Missing/empty evidence directory {path}')
    return digest({str(p.relative_to(path)): file_hash(p) for p in files})


def sha(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None, 'Invalid SHA-256 digest')


def threshold(value):
    require(type(value) in (float, int) and math.isfinite(value) and .05 <= value <= .95,
            'Invalid calibration threshold')
    require(abs(value * 100 - round(value * 100)) < 1e-10, 'Threshold outside calibration grid')


def canonical(fs, short):
    return 'levenshtein' + ''.join(' + ' + f for f in short if f in fs)


def columns_for(columns, name, short):
    fs = name.split(' + ')[1:]
    require(name in ('levenshtein', 'jaro_winkler', 'both') or
            (len(fs) == len(set(fs)) and set(fs) <= set(short) and name == canonical(fs, short)),
            f'Invalid variant {name}')
    extras = {p: f for f, p in PREFIXES.items()}
    return [c for c in columns if
            (c.split('_', 1)[0] not in extras or extras[c.split('_', 1)[0]] in fs) and
            (not c.startswith('jw_') or name in ('jaro_winkler', 'both')) and
            (not c.startswith('lev_') or name != 'jaro_winkler')]


def score(counts):
    tp, fp, fn = np.asarray(counts).T
    denominator = 2 * tp + fp + fn
    return np.divide(2 * tp, denominator, out=np.zeros_like(denominator, dtype=float), where=denominator != 0)


def boot(counts, seed, replicates):
    rng = np.random.default_rng(seed)
    return np.array([float(score(counts[rng.integers(0, len(counts), len(counts))].sum(axis=0)))
                     for _ in range(replicates)])


def metric(r, seed, replicates):
    a = np.asarray(r['counts_by_unit'])
    require(a.ndim == 2 and a.shape[1] == 3 and a.shape[0] > 0 and a.dtype.kind in 'iu' and (a >= 0).all(),
            'Invalid per-unit confusion counts')
    require(type(r['units']) is int and len(a) == r['units'], 'Unit count mismatch')
    sha(r['unit_sha256'])
    total = a.sum(axis=0)
    require(total.tolist() == [r[k] for k in ('tp', 'fp', 'fn')], 'Confusion totals mismatch')
    require(float(score(total)) == r['f1'], 'F1 mismatch')
    tp, fp, fn = (int(x) for x in total)
    require(r['precision'] == tp / max(tp + fp, 1) and r['recall'] == tp / max(tp + fn, 1),
            'Precision/recall mismatch')
    require(np.quantile(boot(a, seed, replicates), [.025, .975]).tolist() == r['ci95'], 'Metric interval mismatch')
    threshold(r['threshold']); sha(r['model_sha256'])
    return a


def plan_checks(proofs, columns=None, path=None, stage=None):
    require(set(proofs) == {'builtins', 'jaro_winkler'}, 'Missing comparison plan')
    for label, proof in proofs.items():
        sha(proof['sha256'])
        require(proof['udf_free'] is (label == 'builtins'), f'Invalid {label} UDF declaration')
        names = proof['columns']
        require(isinstance(names, list) and bool(names) and len(names) == len(set(names)) and
                all(isinstance(n, str) and bool(n) for n in names), 'Empty/duplicate plan columns')
        require(all(n.startswith('jw_') == (label == 'jaro_winkler') for n in names), 'Wrong plan column scope')
        if columns is not None:
            require(names == [n for n in columns if n.startswith('jw_') == (label == 'jaro_winkler')],
                    'Plan columns mismatch')
        if path is not None:
            p = Path(path) / f'{stage}_{label}.plan.txt'
            require(file_hash(p) == proof['sha256'], f'Plan digest mismatch: {p}')
            text = p.read_text()
            require('Physical Plan' in text, f'Missing physical plan: {p}')
            free = not any(marker in text.lower() for marker in UDF_MARKERS)
            require(free == proof['udf_free'], f'Plan contains unexpected UDFs: {p}')


def bound_models(lock, frozen, corpus):
    require(set(frozen) == set(LABELS) and set(lock['models'][corpus]) == set(LABELS), 'Missing frozen model')
    for label in LABELS:
        m, selected = frozen[label], lock['models'][corpus][label]
        sha(m['model_sha256']); threshold(m['threshold'])
        require(selected == {k: m[k] for k in ('model_sha256', 'threshold')},
                f'VALID model/threshold differs from lock: {corpus}/{label}')


def prediction_provenance(work_dir, corpus, lock, frozen):
    bound_models(lock, frozen, corpus)
    p = Path(work_dir) / corpus
    isolated = read(Path(work_dir) / 'manifest.json')['protocol'] == 'simbeat-v2'
    names = ('pairs', 'test_candidates', 'test_pairs', 'left', 'right') if isolated else ('pairs', 'left', 'right')
    inputs = {name: tree_hash(p / name) for name in names}
    if isolated:
        inputs['heldout_release'] = file_hash(p / 'heldout_release.json')
        if corpus == 'febrl4_half_unmatched':
            inputs['test_truth'] = file_hash(p / 'test_truth.json')
    elif (p / 'linkage_truth.json').exists():
        inputs['linkage_truth'] = file_hash(p / 'linkage_truth.json')
    return {'selection_sha256': digest(lock), 'manifest_sha256': lock['manifest_sha256'],
            'models': {label: {k: frozen[label][k] for k in ('model_sha256', 'threshold', 'columns')} for label in LABELS},
            'inputs_sha256': inputs}


def load_predictions(path, expected, confirmation=None):
    """Read a bound envelope, or a legacy array ONLY with completed confirmation.

Never bless an orphan legacy cache with a new lock. Caller must also validate
rows against inputs and plans before accepting a completed confirmation.
"""
    payload = read(path)
    if confirmation is not None:
        require(file_hash(path) == confirmation['predictions_sha256'], 'Prediction digest mismatch')
        require(confirmation['selection_sha256'] == expected['selection_sha256'], 'Prediction selection mismatch')
        for label in LABELS:
            require(all(confirmation[label][k] == expected['models'][label][k]
                        for k in ('model_sha256', 'threshold')), 'Prediction model/threshold mismatch')
    if isinstance(payload, list):
        require(confirmation is not None, 'Unbound legacy predictions: completed confirmation required; refusing rescore')
        rows, plan = payload, confirmation['plan']
    else:
        require(isinstance(payload, dict) and payload.get('schema_version') == 1, 'Unsupported prediction envelope')
        require(payload.get('provenance') == expected, 'Stale prediction provenance')
        rows, plan = payload['rows'], payload['plan']
        if confirmation is not None:
            require(plan == confirmation['plan'], 'Prediction plan mismatch')
    require(isinstance(rows, list) and bool(rows), 'Missing prediction rows')
    return rows, plan


def counts_from_predictions(rows, thresholds, linkage=None):
    keys = [(r['l_id'], r['r_id']) for r in rows]
    require(len(keys) == len(set(keys)), 'Duplicate prediction pair')
    require(all(isinstance(k, str) and bool(k) for pair in keys for k in pair), 'Invalid pair ID')
    for r in rows:
        require(r['label'] in (0, 1), 'Invalid prediction label')
        for label in LABELS:
            v = r['p_' + label]
            require(type(v) in (float, int) and math.isfinite(v) and 0 <= v <= 1, 'Invalid probability')
    out = {}
    for label in LABELS:
        t, prob = thresholds[label], 'p_' + label
        if linkage is None:
            ordered = sorted(rows, key=lambda r: (r['l_id'], r['r_id']))
            units = [[r['l_id'], r['r_id']] for r in ordered]
            a = np.array([[int(r[prob] >= t and r['label'] == 1), int(r[prob] >= t and r['label'] == 0),
                           int(r[prob] < t and r['label'] == 1)] for r in ordered])
        else:
            units = linkage['units']
            require(len(units) == len(set(units)) and set(r['l_id'] for r in rows) <= set(units), 'Linkage units mismatch')
            truth = set(map(tuple, linkage['truth']))
            require(len(truth) == len(linkage['truth']) and all(a in set(units) for a, b in truth), 'Invalid linkage truth')
            left = {}
            for r in sorted(rows, key=lambda r: (-r[prob], r['r_id'], r['l_id'])):
                if r[prob] >= t:
                    left.setdefault(r['l_id'], r)
            right = {}
            for r in sorted(left.values(), key=lambda r: (-r[prob], r['l_id'], r['r_id'])):
                right.setdefault(r['r_id'], r)
            selected = {(r['l_id'], r['r_id']) for r in right.values()}
            counts = {u: [0, 0, 0] for u in units}
            for pair in selected | truth:
                counts[pair[0]][0 if pair in selected & truth else 1 if pair in selected else 2] += 1
            a = np.array([counts[u] for u in units])
        out[label] = (units, a)
    return out


def prediction_counts(work_dir, corpus, rows, frozen):
    import pyarrow.parquet as pq
    p = Path(work_dir) / corpus
    manifest = read(Path(work_dir) / 'manifest.json')
    isolated = manifest['protocol'] == 'simbeat-v2'
    pairs = pq.read_table(p / ('test_pairs' if isolated else 'pairs'), columns=['l_id', 'r_id', 'label', 'part']).to_pylist()
    if isolated:
        from simbeat_holdout import verify_release
        lock = read(Path(work_dir) / 'selection.json')
        payload = verify_release(read(p / 'heldout_release.json'), corpus, lock, manifest)
        candidates = pq.read_table(p / 'test_candidates')
        require('label' not in candidates.column_names, 'TEST candidates contain labels')
        ids = [(r['l_id'], r['r_id']) for r in candidates.to_pylist()]
        require(len(ids) == len(set(ids)) and all(r['part'] == 'test' for r in candidates.to_pylist()),
                'Invalid TEST candidate partitions')
        require(set(ids) == {(r['l_id'], r['r_id']) for r in pairs} and all(r['part'] == 'test' for r in pairs),
                'TEST candidate coverage mismatch')
        kind = manifest['input_bundle']['corpora'][corpus]['kind']
        outcomes = {(r['l_id'], r['r_id']): r['label'] for r in payload['pairs']}
        positive = set(map(tuple, payload['truth']))
        expected_labels = {pair: outcomes[pair] if kind == 'pairs' else float(pair in positive) for pair in ids}
        require({(r['l_id'], r['r_id']): r['label'] for r in pairs} == expected_labels, 'Released TEST labels mismatch')
        for name in ('pairs', 'development'):
            dev = pq.read_table(p / name, columns=['part']).to_pylist()
            require(all(r['part'] in ('fit', 'thr', 'valid') for r in dev), 'TEST leaked into development cache')
        if corpus == 'febrl4_half_unmatched':
            require(read(p / 'test_truth.json') == {'test': {'units': payload['units'], 'truth': payload['truth']}},
                    'Released TEST truth mismatch')
    expected = {(r['l_id'], r['r_id']): r['label'] for r in pairs if r['part'] == 'test'}
    require(len(expected) == sum(r['part'] == 'test' for r in pairs), 'Duplicate TEST pair')
    require({(r['l_id'], r['r_id']): r['label'] for r in rows} == expected, 'TEST pair IDs/labels mismatch')
    linkage = read(p / ('test_truth.json' if isolated else 'linkage_truth.json'))['test'] if corpus == 'febrl4_half_unmatched' else None
    return counts_from_predictions(rows, {label: frozen[label]['threshold'] for label in LABELS}, linkage)


def model_check(path, metric_row):
    path = Path(path)
    require(tree_hash(path) == metric_row['model_sha256'], f'Model digest mismatch: {path}')
    metadata = list(path.glob('stages/0_*/metadata/part-*'))
    require(len(metadata) == 1, f'Missing VectorAssembler metadata: {path}')
    m = read(metadata[0])
    require(m['class'] == 'org.apache.spark.ml.feature.VectorAssembler' and
            m['paramMap']['inputCols'] == metric_row['columns'], 'Model feature columns mismatch')


def audit_confirmation(corpus, confirmation, lock, frozen, prepared, work_dir=None, *, seed=0, replicates=1000):
    bound_models(lock, frozen, corpus)
    require(confirmation['selection_sha256'] == digest(lock), 'Confirmation selection mismatch')
    sha(confirmation['predictions_sha256'])
    # TEST contains both baselines and only the chosen extras. Relative column order is preserved.
    chosen_fields = set(frozen['chosen']['columns']) | set(frozen['jaro_winkler']['columns'])
    test_columns = [n for n in prepared['columns'] if n in chosen_fields]
    plan_checks(confirmation['plan'], test_columns, Path(work_dir) / corpus if work_dir else None, 'test')
    for label in LABELS:
        r = confirmation[label]
        require(all(r[k] == frozen[label][k] for k in ('model_sha256', 'threshold')), 'Confirmed model is not VALID model')
        metric(r, seed, replicates)
    require(confirmation['chosen']['unit_sha256'] == confirmation['jaro_winkler']['unit_sha256'], 'Unpaired TEST units')
    if work_dir is not None:
        p = Path(work_dir) / corpus
        expected = prediction_provenance(work_dir, corpus, lock, frozen)
        rows, _ = load_predictions(p / 'test_predictions.json', expected, confirmation)
        recalc = prediction_counts(work_dir, corpus, rows, frozen)
        for label, (units, a) in recalc.items():
            require(digest(units) == confirmation[label]['unit_sha256'] and
                    a.tolist() == confirmation[label]['counts_by_unit'], 'Predictions do not reproduce recorded counts')
            v = lock['chosen_variant'] if label == 'chosen' else 'jaro_winkler'
            model_check(p / 'models' / hashlib.sha256(v.encode()).hexdigest()[:16], frozen[label])
    return True


def audit_selection(manifest, lock, valid):
    """Replay frozen VALID selection before allowing any new TEST inference."""
    short = manifest['shortlist']
    require(isinstance(short, list) and bool(short) and len(short) == len(set(short)) and set(short) <= set(PREFIXES),
            'Invalid recorded shortlist')
    require(lock['selected_on'] == 'validation', 'Selection must use validation')
    require(digest(manifest) == lock['manifest_sha256'], 'Lock manifest mismatch')
    require(set(lock['models']) == set(CORPORA), 'Corpus coverage mismatch')
    for table in valid.values():
        require(set(table) == set(CORPORA), 'VALID corpus coverage mismatch')
    current = []
    names = ['levenshtein', 'jaro_winkler', 'both'] + [canonical([f], short) for f in short]
    trace = lock['forward_selection']
    require(isinstance(trace, list) and bool(trace), 'Selection trace mismatch')
    avg = lambda v: sum(valid[v][c]['f1'] for c in CORPORA) / len(CORPORA)
    for i, step in enumerate(trace):
        options = [canonical(current + [f], short) for f in short if f not in current]
        require(bool(options), 'Selection continues after exhaustion')
        for v in options:
            if v not in names:
                names.append(v)
        means = {v: avg(v) for v in options}
        best = max(options, key=means.get)
        base = canonical(current, short)
        accepted = means[best] > avg(base)
        expected = {'base': base, 'base_mean_f1': avg(base), 'options': means, 'best': best,
                    'gain': means[best] - avg(base), 'accepted': accepted}
        require(step == expected, 'Greedy selection mismatch')
        if not accepted:
            require(i == len(trace) - 1, 'Selection continues after rejection')
            break
        current = best.split(' + ')[1:]
    require(len(current) == len(short) or trace[-1]['accepted'] is False, 'Incomplete greedy search')
    chosen = canonical(current, short)
    require(lock['chosen_families'] == current, 'Chosen families mismatch')
    require(lock['chosen_variant'] == chosen, 'Chosen variant mismatch')
    require(lock['variants'] == names and set(valid) == set(names + ['chosen']), 'Variant coverage mismatch')
    require(valid['chosen'] == valid[chosen], 'Chosen VALID row mismatch')
    for table in valid.values():
        for row in table.values():
            metric(row, manifest['seed'], manifest['bootstrap_replicates'])
    for c in CORPORA:
        bound_models(lock, {label: valid[chosen if label == 'chosen' else label][c] for label in LABELS}, c)
    return names, chosen


def _audit(d, work_dir):
    m, lock, valid = d['meta']['manifest'], d['selection_lock'], d['valid']
    require(m['protocol'] in ('simbeat-v1', 'simbeat-v2'), 'Unsupported benchmark protocol')
    short = m['shortlist']
    require(isinstance(short, list) and bool(short) and len(short) == len(set(short)) and set(short) <= set(PREFIXES),
            'Invalid recorded shortlist')
    seed, reps = m['seed'], m['bootstrap_replicates']
    require(type(seed) is int and type(reps) is int and seed == 0 and reps == 1000, 'Unsupported bootstrap protocol')
    require(d['selected_on'] == lock['selected_on'] == 'validation', 'Selection must use validation')
    require(digest(m) == lock['manifest_sha256'] and digest(lock) == d['meta']['selection_sha256'], 'Lock digest mismatch')
    for table in (d['prepared'], d['confirmation'], lock['models']):
        require(set(table) == set(CORPORA), 'Corpus coverage mismatch')
    for table in valid.values():
        require(set(table) == set(CORPORA), 'VALID corpus coverage mismatch')
    require(d['forward_selection'] == lock['forward_selection'], 'Selection trace mismatch')
    require(d['chosen_families'] == lock['chosen_families'], 'Chosen families mismatch')
    require(d['chosen_variant'] == lock['chosen_variant'], 'Chosen variant mismatch')
    names, chosen = audit_selection(m, lock, valid)
    avg = lambda v: sum(valid[v][c]['f1'] for c in CORPORA) / len(CORPORA)
    for c in CORPORA:
        prep = d['prepared'][c]
        columns = prep['columns']
        require(isinstance(columns, list) and bool(columns) and len(columns) == len(set(columns)), 'Invalid prepared columns')
        plan_checks(prep['plan'], columns, Path(work_dir) / c if work_dir else None, 'valid')
        for v in names:
            r = valid[v][c]
            require(r['variant'] == v and r['columns'] == columns_for(columns, v, short), 'Variant feature columns mismatch')
            builtin = v not in ('jaro_winkler', 'both')
            require(r['plan_udf_free'] is builtin, 'VALID UDF declaration mismatch')
            require(r['plan_sha256'] == prep['plan']['builtins' if builtin else 'jaro_winkler']['sha256'], 'VALID plan mismatch')
            if work_dir is not None:
                p = Path(work_dir) / c
                k = hashlib.sha256(v.encode()).hexdigest()[:16]
                require(read(p / 'valid' / (k + '.json')) == r, 'Saved VALID result mismatch')
                model_check(p / 'models' / k, r)
        frozen = {label: valid[chosen if label == 'chosen' else label][c] for label in LABELS}
        cf = d['confirmation'][c]
        audit_confirmation(c, cf, lock, frozen, prep, work_dir, seed=seed, replicates=reps)
        if work_dir is not None:
            p = Path(work_dir) / c
            require(read(p / 'prepared.json') == prep and read(p / 'confirmation.json') == cf, 'Saved corpus evidence mismatch')
    test = d['test']
    require(set(test) == {'chosen', 'jaro_winkler', 'delta_mean_f1', 'delta_ci95'}, 'TEST summary schema mismatch')
    boots = {}
    for label in LABELS:
        per = {c: d['confirmation'][c][label] for c in CORPORA}
        mean = sum(per[c]['f1'] for c in CORPORA) / len(CORPORA)
        boots[label] = np.mean([boot(np.array(per[c]['counts_by_unit']), seed + i, reps) for i, c in enumerate(CORPORA)], axis=0)
        expected = {'corpora': per, 'mean_f1': mean, 'mean_ci95': np.quantile(boots[label], [.025, .975]).tolist()}
        require(test[label] == expected, 'TEST summary mismatch')
    require(test['delta_mean_f1'] == test['chosen']['mean_f1'] - test['jaro_winkler']['mean_f1'], 'TEST difference mismatch')
    require(test['delta_ci95'] == np.quantile(boots['chosen'] - boots['jaro_winkler'], [.025, .975]).tolist(), 'Paired interval mismatch')
    checks = {'valid_mean_improves_jw': avg('chosen') > avg('jaro_winkler'),
              'abt_buy_not_below_jw': valid['chosen']['abt_buy']['f1'] >= valid['jaro_winkler']['abt_buy']['f1'],
              'all_within_0_005_of_lev': all(valid['chosen'][c]['f1'] >= valid['levenshtein'][c]['f1'] - .005 for c in CORPORA),
              'test_mean_not_below_jw': test['chosen']['mean_f1'] >= test['jaro_winkler']['mean_f1']}
    require(d['verdict_checks'] == checks and d['verdict'] == ('beaten' if all(checks.values()) else 'not_beaten'), 'Verdict mismatch')
    if work_dir is not None:
        work_dir = Path(work_dir)
        require(read(work_dir / 'selection.json') == lock and read(work_dir / 'manifest.json') == m, 'Saved run identity mismatch')
        if m['protocol'] == 'simbeat-v2':
            import simbeat_inputs as staged
            require(staged.public_manifest() == m['input_bundle'], 'Staged public evidence mismatch')
            require(m['data_sha256'] == m['input_bundle']['source_sha256'], 'Provisioning source provenance mismatch')
        for rel, h in (m['data_sha256'].items() if m['protocol'] == 'simbeat-v1' else []):
            sha(h)
            path = (ROOT / 'data' / rel).resolve()
            require(path.is_relative_to((ROOT / 'data').resolve()), 'Unsafe data evidence path')
            require(file_hash(path) == h, f'Corpus source digest mismatch: {rel}')
    return True


def audit(d, work_dir=None):
    """Reject inconsistent JSON, and optionally verify all locally saved evidence.

Uses recorded selection order; does not consult today's research catalogue.
Assertions are deliberately avoided so checks remain enabled under python -O.
"""
    try:
        return _audit(d, work_dir)
    except AuditError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, OSError, AttributeError) as e:
        raise AuditError(f'Malformed or missing SIM-3 evidence: {e}') from e
