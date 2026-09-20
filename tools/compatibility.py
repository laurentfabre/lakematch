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
               'run_original_febrl.py', 'report_original.py', 'benchmark_campaign.py',
               'cluster_sweep.py', 'run_clusters.py', 'report_cluster_replay.py')
REVIEWED_ADDITIONS = {
    'src/lakematch/benchmark/campaign.py': 'Dispatch the explicit benchmark CLI into the repository runner.',
    'src/lakematch/delta_publication.py': 'Job-only remote publication adapter; not imported by local frozen inference.',
    'src/lakematch/murmur3.py': 'Native SQL hash adapter used only by declared serverless inference.',
    'src/lakematch/native_ml.py': 'Exported SQL model adapter used only by declared serverless inference.',
    'src/lakematch/quality/dqx.py': 'Optional lazy DQX adapter; frozen local configs select native quality.',
    'src/lakematch/quality/rules.py': 'Shared seeded rules for the optional DQX adapter.',
    'tools/benchmark_campaign.py': 'Bounded orchestration; retained failed scale tier blocks automatic repetition.',
    'tools/compatibility.py': 'Hash-bound declaration, independent of the unchanged model freeze.',
    'tools/report_compatibility.py': 'Audit original versus replayed pairs, metadata, probabilities and decisions.',
    'tools/run_compatibility.py': 'Sequential replay with independent audit after each corpus.',
    'tools/run_original_febrl.py': 'Exposed original-corpus diagnostic using the frozen model and gram baseline.',
    'tools/report_original.py': 'Independently reconstruct original-corpus diagnostic metrics.',
    'tools/cluster_sweep.py': 'Forward the explicit replay mode into sequential clustering experiments.',
    'tools/run_clusters.py': 'Replay original clustering models, IDF and thresholds without refitting; compare edges and memberships.',
    'tools/report_cluster_replay.py': 'Independently audit exact clustering memberships and model identity.',
}


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
    additions = declaration['execution_sources'].keys() - freeze['execution_sources'].keys()
    assert set(declaration['reviewed_additions']) == additions
    assert additions <= REVIEWED_ADDITIONS.keys(), 'Unreviewed added execution source'
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
    additions = sources.keys() - freeze['execution_sources'].keys()
    assert additions <= REVIEWED_ADDITIONS.keys(), f'Unreviewed additions: {additions - REVIEWED_ADDITIONS.keys()}'
    declaration = {'status': 'declared_for_replay', 'declared_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'execution compatibility only; no model, threshold, data, seed or confirmation-policy changes',
        'freeze_sha256': sha256(ROOT / 'bench/freeze.json'),
        'plan_sha256': sha256(ROOT / 'bench/ACCEPTANCE_PLAN.md'),
        'execution_sources': sources,
        'reviewed_differences': {path: REVIEWED[path] for path in sorted(changed)},
        'reviewed_additions': {path: REVIEWED_ADDITIONS[path] for path in sorted(additions)}}
    DECLARATION.write_text(json.dumps(declaration, indent=2) + '\n')
    validate(freeze)
    print(json.dumps({'declaration': str(DECLARATION), 'changed': sorted(changed)}))


if __name__ == '__main__':
    declare()
