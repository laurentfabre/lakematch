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
    changed = [path for path, expected in freeze['execution_sources'].items() if sha256(ROOT / path) != expected]
    if changed:
        from report_compatibility import collect as collect_compatibility
        _, compatibility_errors = collect_compatibility()
        errors.extend('Frozen execution compatibility: ' + error for error in compatibility_errors)
    try:
        from frozen import load_freeze
        for corpus in freeze['models']:
            load_freeze(corpus)
    except (AssertionError, KeyError, OSError, ValueError) as exc:
        errors.append(f'Frozen model/source/corpus integrity: {exc}')
    # Explicitly retained outstanding clauses. These are removed only when the
    # corresponding independently audited measurements/implementation are added.
    try:
        from report_original import collect as collect_original
        collect_original()
    except (AssertionError, KeyError, OSError, TypeError, ValueError) as exc:
        errors.append(f'Original-FEBRL diagnostic: {exc}')
    errors.append('lakematch bench --all execution acceptance is missing')
    try:
        reference = json.loads((ROOT / 'bench/affiliations_reference.json').read_text())
        assert reference['status'] == 'extracted_with_comparability_limits'
        assert reference['comparability'] and reference['results'] and reference['sources']
        assert all(sha256(ROOT / path) == expected for path, expected in reference['evidence_files'].items())
        assert (ROOT / 'bench/AFFILIATIONS_REFERENCE.md').is_file()
    except (AssertionError, KeyError, OSError, ValueError) as exc:
        errors.append(f'Affiliations published reference missing or changed: {exc}')
    for name in ('BENCHMARKS.md', 'METHODS.md', 'SCALE.md'):
        if not (ROOT / 'bench' / name).is_file():
            errors.append(f'Missing bench/{name}')
    return errors
