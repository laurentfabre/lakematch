"""Read-only ZR-3 acceptance. Missing work is a failing gate, never a waiver."""
import json

from lakematch.config import DEFAULTS
from evidence import ROOT, sha256
from report_final import collect


def check():
    results, errors = collect()
    selection = json.loads((ROOT / 'bench/selection.json').read_text())
    freeze = json.loads((ROOT / 'bench/freeze.json').read_text())
    for section, key, chosen in (
        ('candidates', 'method', 'selected_candidate'),
        ('features', 'string_similarity', 'selected_string'),
        ('features', 'multi_token', 'selected_multi_token'),
        ('matcher', 'estimator', 'selected_estimator')):
        if DEFAULTS[section][key] != selection[chosen]:
            errors.append(f'Shipped {section}.{key} differs from validation selection')
    for kind in ('frozen-linkage-all', 'frozen-linkage-no_ssn'):
        if kind in results and not results[kind]['report']['acceptance_passed']:
            errors.append(f'{kind}: quality or startup-inclusive latency gate failed')
    for path, expected in freeze['execution_sources'].items():
        if sha256(ROOT / path) != expected:
            errors.append(f'Frozen execution evidence needs compatible-source refresh: {path}')
    # Explicitly retained outstanding clauses. These are removed only when the
    # corresponding independently audited measurements/implementation are added.
    errors.append('Fresh selected-pipeline original-FEBRL diagnostic is missing')
    errors.append('lakematch bench --all execution acceptance is missing')
    errors.append('Comparable Affiliations reference extraction remains unresolved')
    for name in ('BENCHMARKS.md', 'METHODS.md', 'SCALE.md'):
        if not (ROOT / 'bench' / name).is_file():
            errors.append(f'Missing bench/{name}')
    return errors
