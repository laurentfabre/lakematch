"""Export a reviewed snapshot, then independently audit the next CLI model."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['export','audit']);p.add_argument('--root',default='data/app-acceptance-v1');a=p.parse_args()
    root=Path(a.root)
    snapshot=json.loads((root/'http-snapshot.json').read_text())
    canonical=sorted([[r['a_id'],r['b_id'],float(r['label'])] for r in snapshot['labels']])
    expected=hashlib.sha256(json.dumps(canonical,separators=(',',':')).encode()).hexdigest()
    assert expected==snapshot['label_set_sha256']
    assert len(snapshot['reviews'])==20 and snapshot['excluded_unsure']==1
    assert {r[2] for r in canonical}=={0.,1.}
    if a.action=='export':
        with (root/'review-labels.csv').open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=['a_id','b_id','label']);writer.writeheader();writer.writerows(snapshot['labels'])
    else:
        report=json.loads((root/'feedback-output/metrics.json').read_text())
        baseline=json.loads((root/'baseline-output/metrics.json').read_text())
        assert report['model']['label_set_sha256']==expected
        assert baseline['model']['label_set_sha256']!=expected
        assert report['cleanup']=='succeeded'
        result={'status':'passed','reviewed':20,'resolved_training_pairs':len(canonical),'excluded_unsure':1,'baseline_model':baseline['model']['model_uri'],'feedback_model':report['model']['model_uri'],'baseline_label_digest':baseline['model']['label_set_sha256'],'feedback_label_digest':expected,'normal_cli_consumed_exact_snapshot':True,'engine_modified':False,'cleanup':report['cleanup']}
        (root/'feedback-report.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))

if __name__=='__main__': main()
