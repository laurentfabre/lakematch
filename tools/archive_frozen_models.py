#!/usr/bin/env python3
"""Keep the exact frozen model snapshots outside MLflow's temporary downloads."""
import json
import shutil
import tarfile

from evidence import ROOT, sha256
from frozen import tree_hashes


def main():
    freeze = json.loads((ROOT / 'bench/freeze.json').read_text())
    root = ROOT / 'data/frozen_models'
    root.mkdir(parents=True, exist_ok=True)
    index = {'freeze_sha256': sha256(ROOT / 'bench/freeze.json'), 'models': {}}
    for corpus, entry in freeze['models'].items():
        assert tree_hashes(entry['model_path']) == entry['model_files']
        target = root / corpus
        if not target.exists():
            shutil.copytree(entry['model_path'], target, ignore=shutil.ignore_patterns('__pycache__'))
        assert tree_hashes(target) == entry['model_files']
        archive = root / (corpus + '.tar.gz')
        if not archive.exists():
            with tarfile.open(archive, 'w:gz') as bundle:
                for name in entry['model_files']:
                    bundle.add(target / name, arcname=name)
        index['models'][corpus] = {'path': str(target.relative_to(ROOT)),
            'archive': str(archive.relative_to(ROOT)), 'archive_sha256': sha256(archive),
            'files': len(entry['model_files']), 'model_uri': entry['model']['model_uri']}
    (ROOT / 'bench/frozen_artifacts.json').write_text(json.dumps(index, indent=2) + '\n')
    print(json.dumps({'archived_models': len(index['models'])}))


if __name__ == '__main__':
    main()
