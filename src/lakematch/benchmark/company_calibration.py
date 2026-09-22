"""Fixed-fit and grouped diagnostic helpers for the synthetic company pilot.

These functions evaluate suggestions. They cannot approve or execute a merge.
Optional numerical dependencies are imported only for fitting/resampling.
"""
from collections import Counter, defaultdict
import math

from lakematch.mastering.contracts import digest
from lakematch.mastering.probability import precision_lower_bound


def fit_logistic(features, labels, *, l2, calibration=False):
    import numpy as np
    from scipy.optimize import minimize
    from scipy.special import expit
    x, y = np.asarray(features, dtype=float), np.asarray(labels, dtype=float)
    if x.ndim != 2 or y.shape != (len(x),) or not 2 <= len(x) <= 100_000:
        raise ValueError('Bounded aligned training arrays required')
    if not np.isfinite(x).all() or not np.isfinite(y).all() or set(y) != {0., 1.}:
        raise ValueError('Fitting requires finite features and both binary classes')
    if not isinstance(l2, (int, float)) or not math.isfinite(l2) or l2 <= 0:
        raise ValueError('A positive fixed regularizer is required')
    if calibration and x.shape[1] != 1:
        raise ValueError('Platt calibration takes one logit feature')
    def objective(parameters):
        w, intercept = parameters[:-1], parameters[-1]
        z = x @ w + intercept
        loss = np.mean(np.logaddexp(0., z) - y*z) + l2 * (w @ w) / 2
        residual = expit(z) - y
        gradient = np.r_[x.T @ residual / len(y) + l2*w, residual.mean()]
        return loss, gradient
    bounds = [(0. if calibration else -1000., 1000.)] * x.shape[1] + [(-1000., 1000.)]
    result = minimize(objective, np.zeros(x.shape[1]+1), method='L-BFGS-B', jac=True, bounds=bounds,
                      options={'maxiter': 300, 'maxfun': 1000, 'maxls': 30, 'ftol': 1e-12, 'gtol': 1e-8})
    if not result.success or not np.isfinite(result.x).all():
        raise RuntimeError(f'Fixed optimizer did not converge: {result.message}')
    return {'coefficients': result.x[:-1].tolist(), 'intercept': float(result.x[-1]),
            'optimizer_iterations': int(result.nit), 'objective': float(result.fun)}


def proposed_bands(rows, reject_below, accept_at_least):
    """Apply deterministic conflict and one-to-one ambiguity vetoes to scores."""
    provisional = [r for r in rows if not r['vetoes'] and accept_at_least is not None
                   and r['probability'] >= accept_at_least]
    left, right = Counter(r['left_id'] for r in provisional), Counter(r['right_id'] for r in provisional)
    result = {}
    for r in rows:
        if r['vetoes']:
            band = 'review'
        elif accept_at_least is not None and r['probability'] >= accept_at_least:
            band = 'accept' if left[r['left_id']] == right[r['right_id']] == 1 else 'review'
        else:
            band = 'reject' if r['probability'] < reject_below else 'review'
        result[r['pair_id']] = band
    return result


def family_audit(rows, bands, *, seed):
    """Label-blind priority; no family appears at either endpoint twice."""
    accepted = sorted((r for r in rows if bands[r['pair_id']] == 'accept'),
                      key=lambda r: digest([seed, r['pair_id']]))
    audit, used = [], set()
    for row in accepted:
        families = {row['left_family'], row['right_family']}
        if used.isdisjoint(families):
            used.update(families)
            audit.append(row)
    successes = sum(r['label'] for r in audit)
    return {'decisions': len(audit), 'correct': successes, 'errors': len(audit)-successes,
            'pair_ids_sha256': digest([r['pair_id'] for r in audit]),
            'lower_95': precision_lower_bound(successes, len(audit)),
            'sampling': 'seeded greedy family-disjoint accepted edges; not pair-weighted precision'}


def select_thresholds(rows, *, accept_grid, reject_grid, audit_seed, precision_target):
    # Zero false rejects among retrieved validation positives. Retrieval misses
    # are always separately counted, never removed from end-to-end recall.
    reject = max(t for t in reject_grid if not any(r['label'] == 1 and not r['vetoes']
                                                  and r['probability'] < t for r in rows))
    table = []
    confidence = 1 - .05 / len(accept_grid)
    for threshold in accept_grid:
        bands = proposed_bands(rows, reject, threshold)
        audit = family_audit(rows, bands, seed=audit_seed)
        bound = precision_lower_bound(audit['correct'], audit['decisions'], confidence=confidence)
        table.append({'accept_at_least': threshold, 'audit': audit,
                      'simultaneous_lower_bound': bound, 'confidence_per_threshold': confidence,
                      'counts': dict(Counter(bands.values())),
                      'passes_selection': bound is not None and bound >= precision_target})
    selected = next((t['accept_at_least'] for t in table if t['passes_selection']), None)
    return {'reject_below': reject, 'accept_at_least': selected, 'selection_table': table,
            'selection_adjustment': 'Bonferroni across the predeclared accept grid',
            'automatic_execution_enabled': False}


def workload_metrics(rows, truth, bands, *, audit_seed, bootstrap_seed, bootstrap_repetitions):
    import numpy as np
    if not 1 <= bootstrap_repetitions <= 1000:
        raise ValueError('Bounded grouped resampling required')
    expected = {r['erp_key']: r for r in truth}
    if len(expected) != len(truth) or len({r['pair_id'] for r in rows}) != len(rows):
        raise ValueError('Unique truth anchors and scored pairs required')
    by_anchor = defaultdict(list)
    for r in rows:
        if r['left_id'] not in expected or r['label'] != int(r['right_id'] == expected[r['left_id']]['crm_key']):
            raise ValueError('Score labels do not match independent truth')
        by_anchor[r['left_id']].append(r)
    strata, grouped = defaultdict(Counter), defaultdict(Counter)
    for key, t in expected.items():
        candidates = by_anchor[key]
        positives = [r for r in candidates if r['label']]
        values = {'anchors': 1, 'candidates': len(candidates), 'retrieved_positives': len(positives),
                  'accepted': sum(bands[r['pair_id']] == 'accept' for r in candidates),
                  'accepted_correct': sum(bands[r['pair_id']] == 'accept' for r in positives),
                  'rejected_positives': sum(bands[r['pair_id']] == 'reject' for r in positives),
                  'review_pairs': sum(bands[r['pair_id']] == 'review' for r in candidates),
                  'review_anchors': int(not any(bands[r['pair_id']] == 'accept' for r in candidates))}
        strata[t['stratum']].update(values)
        grouped[t['family']].update(values)
    # Counter addition drops zero keys; an all-review policy must still retain
    # explicit zero accepted/rejected counts and resample successfully.
    all_keys = sorted({k for counts in grouped.values() for k in counts})
    total = {k: sum(counts[k] for counts in grouped.values()) for k in all_keys}
    def ratios(v):
        return {'candidate_recall': v['retrieved_positives']/v['anchors'],
                'acceptance_coverage': v['accepted']/v['anchors'],
                'accepted_recall': v['accepted_correct']/v['anchors'],
                'accepted_pair_precision': v['accepted_correct']/v['accepted'] if v['accepted'] else None,
                'review_anchor_rate': v['review_anchors']/v['anchors']}
    keys = sorted(total)
    matrix = np.array([[grouped[f][k] for k in keys] for f in sorted(grouped)], dtype=np.int64)
    rng, samples = np.random.default_rng(bootstrap_seed), defaultdict(list)
    for _ in range(bootstrap_repetitions):
        counts = dict(zip(keys, matrix[rng.integers(0, len(matrix), size=len(matrix))].sum(axis=0)))
        for k,v in ratios(counts).items():
            if v is not None: samples[k].append(v)
    intervals = {k: [float(x) for x in np.quantile(v, [.025, .975])] for k,v in samples.items()}
    return {**dict(total), **ratios(total), 'retrieval_misses': total['anchors']-total['retrieved_positives'],
            'accepted_errors': total['accepted']-total['accepted_correct'],
            'by_stratum': {s: {**dict(v), **ratios(v)} for s,v in sorted(strata.items())},
            'audit': family_audit(rows, bands, seed=audit_seed),
            'family_bootstrap_95': intervals, 'bootstrap_repetitions': bootstrap_repetitions,
            'bootstrap_scope': 'ERP-family grouped descriptive intervals; cross-family retrieval dependencies remain',
            'actual_route': 'review', 'automatic_execution_enabled': False}
