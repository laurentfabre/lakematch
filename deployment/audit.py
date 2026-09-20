# Databricks notebook source
"""Audit frozen full-universe inference, quality and native/remote parity."""
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, dbutils.widgets.get('source_root'))
from lakematch.benchmark.metrics import evaluate

root = Path(dbutils.widgets.get('input_root'))
schema = dbutils.widgets.get('schema')
if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*', schema):
    raise ValueError('Expected an explicitly owned catalog.schema')
report = {'status': 'running', 'scope': 'frozen local model, remote native SQL inference; no retraining',
    'quality_engine': dbutils.widgets.get('quality_engine'), 'variants': {}}
for variant in ('all', 'no_ssn'):
    reference = json.loads((root / variant / 'reference.json').read_text())
    links = {(row.a_id, row.b_id) for row in spark.table(f'{schema}.lm_links_{variant}').select('a_id', 'b_id').collect()}
    candidates = {(row.a_id, row.b_id) for row in spark.table(f'{schema}.lm_candidates_{variant}').select('a_id', 'b_id').collect()}
    assert len(candidates) <= 100000
    quarantine = {side: spark.table(f'{schema}.lm_quarantine_{variant}_{side}').count() for side in ('left', 'right')}
    assert quarantine == {'left': 3, 'right': 3}, 'Seeded quarantine differs'
    row = {'quarantine': quarantine, 'candidate_pairs': len(candidates), 'links': len(links), 'partitions': {}}
    labels = [json.loads(line) for line in (root / variant / 'pairs.jsonl').read_text().splitlines()]
    records = [json.loads(line) for line in (root / variant / 'left.jsonl').read_text().splitlines()]
    for split in ('valid', 'confirmation'):
        anchors = {item['rec_id'] for item in records if item.get('split') == split}
        selected = {pair for pair in links if pair[0] in anchors}
        positives = {(item['a_id'], item['b_id']) for item in labels if item['split'] == split and item['label']}
        truth = {**dict.fromkeys(selected, 0.), **dict.fromkeys(positives, 1.)}
        metrics, _ = evaluate(selected, truth, {pair: pair[0] for pair in truth})
        delta = abs(metrics['f1'] - reference['partitions'][split]['f1'])
        row['partitions'][split] = {**metrics, 'absolute_f1_delta_from_local': delta,
            'candidate_recall': len(positives & candidates) / len(positives)}
        assert delta <= .01, f'{variant}/{split} remote parity failed'
    report['variants'][variant] = row
report['status'] = 'completed'
(root / ('audit-' + report['quality_engine'] + '.json')).write_text(json.dumps(report, indent=2) + '\n')
dbutils.notebook.exit(json.dumps(report))
