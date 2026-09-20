"""Separate, hash-bound declaration for replaying the original model freeze.

A declaration permits a measured replay; it does not establish compatibility.
Only the independent replay audit can establish that the outputs agree.
"""
from datetime import datetime, timezone
import json

from evidence import ROOT, sha256

DECLARATION = ROOT / 'bench/source_compatibility.json'
REVIEWED = {
    'src/lakematch/config.py': 'Validation-selected defaults; DQX accepted. Full frozen configs override defaults.',
    'src/lakematch/cli.py': 'Benchmark command dispatch; run/train/cluster retain their command contracts.',
    'src/lakematch/features.py': 'Remove unrelated global integration guard; feature expressions unchanged.',
    'src/lakematch/quality/__init__.py': 'Lazy dispatcher selects the unchanged native implementation for frozen configs.',
    'tools/frozen.py': 'Permit exactly this separately declared source snapshot for a measured compatibility replay.',
}
EXTRA_TOOLS = ('compatibility.py', 'run_compatibility.py', 'report_compatibility.py',
               'run_original_febrl.py', 'benchmark_campaign.py')


def current_sources(freeze):
    paths = set(freeze['execution_sources'])
    paths.update(str(path.relative_to(ROOT)) for path in (ROOT / 'src/lakematch').rglob('*.py'))
    paths.update('tools/' + name for name in EXTRA_TOOLS if (ROOT / 'tools' / name).exists())
    return {name: sha256(ROOT / name) for name in sorted(paths)}


def original_sources(freeze):
    archived = json.loads((ROOT / 'bench/frozen_sources.json').read_text())
    assert archived['freeze_sha256'] == sha256(ROOT / 'bench/freeze.json')
    assert archived['files'] == freeze['execution_sources']
    assert sha256(ROOT / archived['archive']) == archived['archive_sha256']
    for name, expected in archived['files'].items():
        assert sha256(ROOT / archived['path'] / name) == expected, f'Changed original source: {name}'
    return archived


def validate(freeze):
    declaration = json.loads(DECLARATION.read_text())
    assert declaration['status'] == 'declared_for_replay'
    assert declaration['freeze_sha256'] == sha256(ROOT / 'bench/freeze.json')
    original_sources(freeze)
    assert declaration['execution_sources'] == current_sources(freeze), 'Source changed after replay declaration'
    changed = {path for path, expected in freeze['execution_sources'].items()
               if declaration['execution_sources'][path] != expected}
    assert set(declaration['reviewed_differences']) == changed
    assert changed <= REVIEWED.keys(), 'Undeclared semantic change requires a new review'
    assert declaration['plan_sha256'] == sha256(ROOT / 'bench/ACCEPTANCE_PLAN.md')
    return declaration


def declare():
    if DECLARATION.exists():
        raise FileExistsError('Keep the existing declaration; never overwrite replay provenance')
    freeze = json.loads((ROOT / 'bench/freeze.json').read_text())
    original_sources(freeze)
    sources = current_sources(freeze)
    changed = {path for path, expected in freeze['execution_sources'].items() if sources[path] != expected}
    assert changed <= REVIEWED.keys(), f'Unreviewed changes: {changed - REVIEWED.keys()}'
    declaration = {'status': 'declared_for_replay', 'declared_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'execution compatibility only; no model, threshold, data, seed or confirmation-policy changes',
        'freeze_sha256': sha256(ROOT / 'bench/freeze.json'),
        'plan_sha256': sha256(ROOT / 'bench/ACCEPTANCE_PLAN.md'),
        'execution_sources': sources,
        'reviewed_differences': {path: REVIEWED[path] for path in sorted(changed)},
        'added_sources': sorted(set(sources) - freeze['execution_sources'].keys())}
    DECLARATION.write_text(json.dumps(declaration, indent=2) + '\n')
    validate(freeze)
    print(json.dumps({'declaration': str(DECLARATION), 'changed': sorted(changed)}))


if __name__ == '__main__':
    declare()
