#!/usr/bin/env python3
"""Freeze selected immutable models/configs before any confirmation scoring."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from evidence import ROOT, sha256, source_digest


def main():
    index = json.loads((ROOT / 'bench/candidate_pairs_index.json').read_text())
    if index.get('status') != 'comparisons_completed' or not index.get('recommendation'):
        raise ValueError('Complete candidate selection before freezing confirmation models')
    selection = json.loads((ROOT / 'bench/selection.json').read_text())
    method = index['recommendation']
    if selection.get('selected_candidate') != method:
        raise ValueError('Candidate selection reports disagree')
    models = {}
    for corpus, entry in index['runs'].items():
        path = ROOT / entry['report']
        assert sha256(path) == entry['report_sha256']
        row = entry['best_per_method'][method]
        config = deepcopy(row['frozen_config'])
        # Table materialization uses the measured lineage-safe execution boundary.
        # It does not alter model features, candidates, scores or decisions.
        config['runtime']['materialize'] = 'table'
        assert config['features']['multi_token'] == selection['selected_multi_token']
        assert config['matcher']['estimator'] == selection['selected_estimator']
        models[corpus] = {'model': row['model'], 'config': config,
            'selection_run': entry['run_id'], 'selection_report': entry['report'],
            'selection_report_sha256': entry['report_sha256'], 'validation_f1': row['f1']}
    body = {'schema_version': 1, 'status': 'frozen_before_confirmation', 'seed': 2026091901,
        'bootstrap_seed': 2026091902, 'method': method, 'models': models,
        'candidate_index_sha256': sha256(ROOT / 'bench/candidate_pairs_index.json'),
        'confirmation_policy': 'No retraining, threshold changes or resplitting based on confirmation outcomes'}
    path = ROOT / 'bench/freeze.json'
    if path.exists() and json.loads(path.read_text()) != body:
        raise ValueError('Confirmation freeze already exists and differs; never replace it silently')
    path.write_text(json.dumps(body, indent=2) + '\n')
    print(json.dumps({'status': body['status'], 'corpora': list(models), 'sha256': sha256(path)}))


if __name__ == '__main__':
    main()
