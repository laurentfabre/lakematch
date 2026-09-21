"""New synthetic app fixture; it never reads frozen benchmark confirmation data."""
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'app/src'))


def csv_write(path, rows, fields):
    with path.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def prepare(root):
    import yaml
    root.mkdir(parents=True, exist_ok=True)
    left, right, truth = [], [], []
    for group in range(10):
        for offset, name in enumerate(('Alice Meadows', 'Zachary Winters')):
            index = group * 2 + offset
            left.append(dict(rec_id=f'a{index:02}', name=f'{name} {group}', code=f'G{group:02}'))
            right.append(dict(rec_id=f'b{index:02}', name=f'{name} {group}', code=f'G{group:02}'))
        for a in range(group*2, group*2+2):
            for b in range(group*2, group*2+2):
                truth.append(dict(a_id=f'a{a:02}', b_id=f'b{b:02}', label=int(a==b)))
    csv_write(root/'left.csv', left, ['rec_id','name','code'])
    csv_write(root/'right.csv', right, ['rec_id','name','code'])
    csv_write(root/'baseline-labels.csv', truth[:8], ['a_id','b_id','label'])
    csv_write(root/'validation-labels.csv', truth[-8:], ['a_id','b_id','label'])
    (root/'truth.json').write_text(json.dumps(truth, indent=2)+'\n')
    config = dict(profile='laptop', entity=dict(name='app_synthetic_feedback', fields={'name':{'type':'person_name'}, 'code':{'type':'code'}}),
                  candidates=dict(method='field_blocks', field_blocks=[['code']], k=2, max_pairs=100, max_join_rows=1000),
                  features=dict(multi_token=[], embeddings=dict(provider='none')),
                  matcher=dict(estimator='gbt', max_iter=4, max_depth=2),
                  decision=dict(threshold=.5, cardinality='unrestricted'),
                  input=dict(left=str(root/'left.csv'), right=str(root/'right.csv'), labels=str(root/'baseline-labels.csv'), validation_labels=str(root/'validation-labels.csv')),
                  mlflow=dict(tracking_uri='sqlite:///'+str(root/'mlflow.db'), experiment='app-feedback'),
                  model=dict(path=str(root/'baseline-model')), output=dict(root=str(root/'baseline-output')))
    (root/'baseline.yaml').write_text(yaml.safe_dump(config))
    config['input']['labels'] = str(root/'review-labels.csv')
    config['model']['path'] = str(root/'feedback-model')
    config['output']['root'] = str(root/'feedback-output')
    (root/'feedback.yaml').write_text(yaml.safe_dump(config))


def seed(root, database):
    import pandas as pd
    from lakematch_review.backend.models import PairOut
    from lakematch_review.backend.store import SQLiteStore, pair_key
    report = json.loads((root/'baseline-output/metrics.json').read_text())
    scores = pd.read_parquet(root/'baseline-output/scores')
    model = report['model']['model_uri']
    records = {side:{r['rec_id']:{k:v for k,v in r.items() if k!='rec_id'} for r in csv.DictReader((root/f'{side}.csv').open())} for side in ['left','right']}
    truth = json.loads((root/'truth.json').read_text())[8:32]
    lookup = {(r.a_id,r.b_id):r.p for r in scores.itertuples()}
    pairs = [PairOut(pair_id=pair_key(model, r['a_id'],r['b_id']), a_id=r['a_id'],b_id=r['b_id'],
                     left=records['left'][r['a_id']],right=records['right'][r['b_id']], probability=lookup[(r['a_id'],r['b_id'])],
                     threshold=.5,model_version=model) for r in truth]
    store = SQLiteStore(database)
    if store.query('SELECT COUNT(*) FROM review_queue')[0][0]:
        raise ValueError('Refuse to overwrite an existing review batch')
    for pair in pairs:
        store.enqueue(pair)
    evaluation = report['model']['evaluation']
    metadata = {'quarantine':sum(report['quarantine'].values()), 'evaluations':[dict(model_version=model,precision=evaluation['pairwise_precision'],recall=evaluation['pairwise_recall'],sample_size=8,context='synthetic record-disjoint validation')]}
    for key, value in metadata.items():
        store.set_metadata(key, value)
    store.close()
    (root/'queue.json').write_text(json.dumps([p.model_dump() for p in pairs],indent=2)+'\n')
    (root/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['prepare','seed']); p.add_argument('--root',default='data/app-acceptance-v1'); p.add_argument('--database',default='app/data/review.sqlite'); a=p.parse_args()
    root=(ROOT/a.root).resolve()
    if a.action=='prepare': prepare(root)
    else: seed(root, str((ROOT/a.database).resolve()))
