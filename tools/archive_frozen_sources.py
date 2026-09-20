#!/usr/bin/env python3
"""Preserve the exact pre-confirmation implementation before additive changes."""
import json
import shutil
import tarfile

from evidence import ROOT, sha256


def main():
    freeze_path = ROOT / 'bench/freeze.json'
    freeze = json.loads(freeze_path.read_text())
    destination = ROOT / 'data/frozen_sources'
    for name, expected in freeze['execution_sources'].items():
        source = ROOT / name
        assert sha256(source) == expected, f'Frozen source already changed: {name}'
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert sha256(target) == expected, f'Archived source changed: {name}'
        else:
            shutil.copy2(source, target)
    archive_path = ROOT / 'data/frozen_sources.tar.gz'
    with tarfile.open(archive_path, 'w:gz') as archive:
        for name in freeze['execution_sources']:
            archive.add(destination / name, arcname=name)
    report = {'freeze_sha256': sha256(freeze_path), 'files': freeze['execution_sources'],
        'path': 'data/frozen_sources', 'archive': str(archive_path.relative_to(ROOT)),
        'archive_sha256': sha256(archive_path)}
    (ROOT / 'bench/frozen_sources.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'files': len(report['files']), 'archive_sha256': report['archive_sha256']}))


if __name__ == '__main__':
    main()
