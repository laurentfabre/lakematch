# Databricks notebook source
"""Stage owned public snapshots and prove quality parity before SDP inference."""
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys
import time

source_root = Path(dbutils.widgets.get('source_root'))
sys.path.insert(0, str(source_root))
from lakematch.config import from_dict

root = Path(dbutils.widgets.get('input_root'))
schema = dbutils.widgets.get('schema')
if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*', schema):
    raise ValueError('Expected an explicitly owned catalog.schema')
manifest = json.loads((root / 'manifest.json').read_text())
for name, expected in manifest['files'].items():
    with (root / name).open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected, f'Staged input changed: {name}'
started = time.perf_counter()
spark.sql(f'ALTER SCHEMA {schema} DISABLE PREDICTIVE OPTIMIZATION').collect()
quality = runpy.run_path(str(source_root.parent / 'integration/check_dqx.py'))['check'](spark)
tables = {}
for variant in ('all', 'no_ssn'):
    config = from_dict(json.loads((root / variant / 'config.json').read_text()))
    record_schema = 'rec_id string, ' + ', '.join(field + ' string' for field in config.fields)
    for side in ('left', 'right'):
        frame = spark.read.schema(record_schema).json(str(root / variant / (side + '.jsonl')))
        name = f'{schema}.lm_input_{variant}_{side}'
        (frame.write.format('delta').option('delta.enableRowTracking', 'true')
            .mode('overwrite').saveAsTable(name))
        tables[name] = spark.table(name).count()
report = {'status': 'completed', 'quality': quality, 'input_tables': tables,
    'freeze_sha256': manifest['freeze_sha256'], 'seconds': time.perf_counter() - started}
(root / 'prepare-report.json').write_text(json.dumps(report, indent=2) + '\n')
dbutils.notebook.exit(json.dumps(report))
