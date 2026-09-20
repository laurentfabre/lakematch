"""Fingerprint the isolated app without generated output, caches or secrets."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def hashes():
    paths=[p for directory in ['src','acceptance','tests'] for p in (ROOT/'app'/directory).rglob('*') if p.is_file() and p.suffix in {'.py','.ts','.tsx','.css','.html','.mjs'} and not any(part in {'__pycache__','__dist__'} for part in p.parts) and p.name not in {'_version.py','_metadata.py'}]
    paths += [ROOT/'app'/f for f in ['pyproject.toml','uv.lock','package.json','bun.lock','app.yml','databricks.yml']]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}

if __name__=='__main__':
    target=ROOT/'data/app-acceptance-v1/app-source.json'
    target.write_text(json.dumps(hashes(),indent=2)+'\n')
    print(target)
