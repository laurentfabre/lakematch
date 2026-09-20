"""Read-only checks of the pre-confirmation snapshot, without Spark actions."""
import json
from pathlib import Path

from evidence import ROOT, sha256

EXECUTION_SOURCES = sorted((ROOT / 'src/lakematch').rglob('*.py')) + [ROOT / 'tools' / name for name in (
    'run_frozen_linkage.py', 'run_frozen_pairs.py', 'run_scale.py', 'frozen.py')]


def tree_hashes(path):
    root = Path(path)
    return {str(p.relative_to(root)): sha256(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


def load_freeze(corpus=None):
    path = ROOT / 'bench/freeze.json'
    frozen = json.loads(path.read_text())
    assert frozen['status'] == 'frozen_before_confirmation' and frozen['seed'] == 2026091901
    for name, expected in frozen['execution_sources'].items():
        assert sha256(ROOT / name) == expected, f'Frozen execution source changed: {name}'
    if corpus:
        entry = frozen['models'][corpus]
        assert sha256(ROOT / entry['selection_report']) == entry['selection_report_sha256']
        assert tree_hashes(entry['model_path']) == entry['model_files'], 'Frozen model artifacts changed'
        for item in entry['corpus_manifest']['files'].values():
            assert sha256(ROOT / item['path']) == item['sha256'], 'Frozen corpus changed'
    return frozen
