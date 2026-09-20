#!/usr/bin/env python3
"""One supervised Splink/DuckDB baseline on frozen clustering partitions."""
import argparse
from collections import Counter
import importlib.metadata
import json
from pathlib import Path
import re
import sys
import time
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import duckdb
import pandas as pd
from splink import DuckDBAPI, Linker, SettingsCreator, block_on
import splink.comparison_library as cl

from lakematch.benchmark.clusters import cluster_bootstrap, cluster_group_counts, cluster_metrics
from lakematch.benchmark.corpora import Components, digest
from offline_run import assert_offline


def normalized(value):
    value = ''.join(c if unicodedata.category(c)[0] in 'LN' else ' ' for c in str(value).lower())
    return ' '.join(value.split()) or None


def partition(records, edges, threshold):
    graph = Components()
    for a, b, probability in edges:
        if probability >= threshold:
            graph.union(a, b)
    return {key: graph.find(key) for key in records}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('corpus',choices=['febrl3','historical_50k'])
    args=parser.parse_args()
    assert_offline()
    started=time.perf_counter()
    root=Path('data/bench')/args.corpus
    manifest=json.loads((root/'manifest.json').read_text())
    records=[json.loads(line) for line in (root/'records.jsonl').read_text().splitlines()]
    if digest(records)!=manifest['record_digest']:
        raise ValueError('Frozen clustering records changed')
    fields=manifest['fields']
    def frame(split):
        rows=[]
        for record in records:
            if record['split']!=split:
                continue
            row={'unique_id':record['rec_id'], **{name:normalized(record[name]) for name in fields}}
            name=row.get('surname') or row.get('full_name') or ''
            row['block_name']=name.split()[-1][:4] if name else None
            date=record.get('date_of_birth',record.get('dob',''))
            row['block_year']=date[:4] if re.match(r'^\d{4}',date) else None
            row['block_postcode']=row.get('postcode') or row.get('postcode_fake')
            if split=='train':
                row['truth_entity']=record['truth_entity']
            rows.append(row)
        return pd.DataFrame(rows)
    train,valid=frame('train'),frame('valid')
    truth={r['rec_id']:r['truth_entity'] for r in records if r['split']=='valid'}
    assert set(train.unique_id).isdisjoint(valid.unique_id)
    counts=Counter(train.truth_entity)
    prior=sum(n*(n-1)/2 for n in counts.values())/(len(train)*(len(train)-1)/2)
    if sum(n*(n-1)/2 for n in counts.values())>1_000_000:
        raise ValueError('Supervised positive-pair training budget exceeded')
    out=Path('data/splink')/args.corpus
    out.mkdir(parents=True,exist_ok=True)
    report={'status':'running','corpus':args.corpus,'manifest':manifest,'confirmation_scored':False,
        'versions':{p:importlib.metadata.version(p) for p in ('splink','duckdb','pandas')},
        'scope':'training-only supervised m/prior and sampled u; disjoint validation connected components',
        'max_random_u_pairs':1_000_000,'seed':0,'max_validation_pairs':1_000_000,'max_prejoin_rows':5_000_000,
        'cost':{'remote_spend':0,'live_label_spend':0}}
    connection=duckdb.connect(':memory:')
    connection.execute("SET threads=2")
    connection.execute("SET memory_limit='2GB'")
    try:
        connection.register('validation_budget',valid)
        join_rows=0
        for key in ('block_name','block_year','block_postcode'):
            join_rows+=connection.execute(f'SELECT COALESCE(SUM(n*(n-1)/2),0) FROM (SELECT COUNT(*) n FROM validation_budget WHERE {key} IS NOT NULL GROUP BY {key})').fetchone()[0]
        report['prejoin_rows_upper_bound']=join_rows
        if join_rows>report['max_prejoin_rows']:
            raise ValueError('Splink blocking join budget exceeded')
        comparisons=[cl.ExactMatch(name) if spec['type']=='code' else cl.LevenshteinAtThresholds(name,[1,2]) for name,spec in fields.items()]
        settings=SettingsCreator(link_type='dedupe_only',comparisons=comparisons,
            blocking_rules_to_generate_predictions=[block_on(n) for n in ('block_name','block_year','block_postcode')],
            probability_two_random_records_match=prior,retain_matching_columns=False)
        db= DuckDBAPI(connection)
        linker=Linker(train,settings,db_api=db,input_table_aliases='training')
        fit_start=time.perf_counter()
        linker.training.estimate_u_using_random_sampling(max_pairs=1_000_000,seed=0)
        linker.training.estimate_m_from_label_column('truth_entity')
        frozen=linker.misc.save_model_to_json(str(out/'model.json'),overwrite=True)
        report['fit_seconds']=time.perf_counter()-fit_start
        # Fresh Linker, fresh table alias, frozen parameters. No validation truth enters it.
        scoring=Linker(valid,frozen,db_api=db,input_table_aliases='validation')
        score_start=time.perf_counter()
        predictions=scoring.inference.predict(threshold_match_probability=0.).as_pandas_dataframe()
        if len(predictions)>report['max_validation_pairs']:
            raise ValueError('Splink final-pair budget exceeded')
        edges=[(str(r.unique_id_l),str(r.unique_id_r),float(r.match_probability)) for r in predictions.itertuples()]
        report['scoring_seconds']=time.perf_counter()-score_start
        positive_pairs=sum(n*(n-1)//2 for n in Counter(truth.values()).values())
        report['candidate_recall']=sum(truth[a]==truth[b] for a,b,_ in edges)/positive_pairs
        options=[]
        for cutoff in range(101):
            threshold=cutoff/100
            labels=partition(truth,edges,threshold)
            result=cluster_metrics(truth,labels)
            options.append((result['f1'],threshold,result,labels))
        _,threshold,metrics,labels=max(options,key=lambda row:(row[0],row[1]))
        report.update(metrics=metrics,threshold=threshold,candidate_pairs=len(edges),
            uncertainty=cluster_bootstrap(cluster_group_counts(truth,labels)),
            status='completed',cleanup='DuckDB connection closed in finally')
        (out/'predictions.json').write_text(json.dumps({'edges':edges,'truth':truth,'clusters':labels})+'\n')
    except Exception as exc:
        report.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        connection.close()
        report['wall_seconds']=time.perf_counter()-started
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','corpus','metrics','threshold','candidate_recall','wall_seconds')}))


if __name__=='__main__':
    main()
