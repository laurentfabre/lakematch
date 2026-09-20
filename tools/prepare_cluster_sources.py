#!/usr/bin/env python3
"""Prepare public clustering corpora separately from offline measured runs."""
import hashlib
import json
from pathlib import Path
import urllib.request

from recordlinkage.datasets import load_febrl3


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'lakematch-public-benchmark/0.1'}), timeout=45) as response:
        return response.read()


def main():
    root = Path('data/sources/clustering')
    root.mkdir(parents=True, exist_ok=True)
    manifest = root / 'manifest.json'
    if manifest.exists():
        saved = json.loads(manifest.read_text())
        for record in saved['sources']:
            assert hashlib.sha256(Path(record['path']).read_bytes()).hexdigest() == record['sha256']
        print('Existing immutable clustering sources verified')
        return
    revision = json.loads(fetch('https://api.github.com/repos/moj-analytical-services/splink_datasets/commits/main'))['sha']
    base = f'https://raw.githubusercontent.com/moj-analytical-services/splink_datasets/{revision}'
    filename = 'historical_figures_with_errors_50k.parquet'
    body = fetch(base + '/data/' + filename)
    path = root / filename
    path.write_bytes(body)
    sources = [{'name': 'historical_50k', 'url': base + '/data/' + filename, 'revision': revision,
                'path': str(path), 'sha256': hashlib.sha256(body).hexdigest(),
                'provenance': 'Public Wikidata historical figures with introduced duplicate errors, per Splink 4.0.16 metadata',
                'license': 'MIT repository distribution; original Wikidata source CC0'}]
    for name in ('LICENSE', 'README.md'):
        try:
            body = fetch(base + '/' + name)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            continue
        destination = root / ('splink_datasets_' + name)
        destination.write_bytes(body)
    records, links = load_febrl3(return_links=True)
    path = root / 'febrl3.csv'
    records.to_csv(path, index_label='rec_id')
    truth = root / 'febrl3_links.json'
    truth.write_text(json.dumps([list(pair) for pair in links], sort_keys=True) + '\n')
    for path in (path, truth):
        sources.append({'name': path.stem, 'source': 'recordlinkage 0.16 bundled FEBRL3 synthetic data',
            'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'license': 'BSD-3-Clause distribution'})
    manifest.write_text(json.dumps({'sources': sources}, indent=2) + '\n')
    print(json.dumps({'manifest': str(manifest), 'sources': len(sources), 'splink_revision': revision}))


if __name__ == '__main__':
    main()
