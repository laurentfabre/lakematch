#!/usr/bin/env python3
"""Stage public frozen inputs/SQL state locally; never uploads or mutates models."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

from evidence import ROOT, sha256
from frozen import tree_hashes
from report_serverless_adapters import check


def main():
    freeze_path = ROOT / 'bench/freeze.json'
    freeze = json.loads(freeze_path.read_text())
    verified = check()
    root = ROOT / 'data/serverless_frozen'
    root.mkdir(parents=True, exist_ok=True)
    for variant in ('all', 'no_ssn'):
        entry = freeze['models']['febrl4_half_' + variant]
        native = ROOT / 'data/native_ml' / variant
        measured = verified['native-ml-' + variant]
        parity = measured['report']
        assert parity['status'] == 'completed' and parity['maximum_probability_difference'] < 1e-12
        assert parity['exact_minhash_keys'] and parity['exact_ordered_candidates']
        target = root / variant
        target.mkdir(exist_ok=True)
        for side in ('left', 'right'):
            item = entry['corpus_manifest']['files'][side]
            assert sha256(ROOT / item['path']) == item['sha256']
            rows = [json.loads(line) for line in (ROOT / item['path']).read_text().splitlines()]
            for ident in ('', 'lakematch-seeded-duplicate', 'lakematch-seeded-duplicate'):
                rows.append({'rec_id': ident, 'split': 'quality_fixture', **dict.fromkeys(entry['config']['entity']['fields'], '')})
            (target / (side + '.jsonl')).write_text(''.join(json.dumps(row) + '\n' for row in rows))
        shutil.copy2(ROOT / entry['corpus_manifest']['files']['pairs']['path'], target / 'pairs.jsonl')
        shutil.copy2(ROOT / measured['artifacts']['native-state.json'], target / 'native-state.json')
        shutil.copy2(ROOT / 'data/frozen_linkage' / ('febrl4_half_' + variant) / 'report.json', target / 'reference.json')
        archived = ROOT / 'data/frozen_models' / ('febrl4_half_' + variant)
        assert tree_hashes(archived) == entry['model_files'], 'Archived frozen model changed'
        import yaml
        mlmodel = yaml.safe_load((archived / 'MLmodel').read_text())
        idf = archived / mlmodel['flavors']['python_function']['artifacts']['idf']['path']
        shutil.copytree(idf, target / 'idf', dirs_exist_ok=True)
        raw = deepcopy(entry['config'])
        raw.update(profile='databricks')
        raw['runtime'].update(mode='serverless', cli_profile='fevm-gdpr2', materialize='table')
        raw['storage'].update(catalog='gdpr2_catalog', scratch_schema='gdpr2_catalog.lakematch_20260919')
        raw['quality']['engine'] = 'dqx'
        raw['paid_features'].update(app=True, genie=True)
        # No mutable registry resolution: pipeline state is derived from the frozen model.
        (target / 'config.json').write_text(json.dumps(raw, indent=2) + '\n')
    manifest = {'freeze_sha256': sha256(freeze_path), 'profile': 'fevm-gdpr2',
        'adapter_runs': {kind: entry['run_id'] for kind, entry in verified.items()},
        'source': 'public synthetic FEBRL4 plus three seeded bad-ID rows per side',
        'files': {str(p.relative_to(root)): sha256(p) for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'manifest.json'}}
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'root': str(root), 'files': len(manifest['files'])}))


if __name__ == '__main__':
    main()
