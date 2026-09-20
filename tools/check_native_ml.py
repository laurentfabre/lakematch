#!/usr/bin/env python3
"""Job-only export and validation equivalence before SDP uses native state."""
import argparse
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import time

from pyspark.sql import functions as F

from lakematch import blocking, entity, feature_stats, features, matcher, native_ml, tracking
from lakematch.benchmark.corpora import febrl4
from lakematch.config import from_dict
from lakematch.runtime import Materializer, create_session, probe
from evidence import ROOT, sha256
from offline_run import assert_offline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('variant', choices=['all', 'no_ssn'])
    args = parser.parse_args()
    assert_offline()
    started = time.perf_counter()
    corpus = febrl4(args.variant)
    freeze = json.loads((ROOT / 'bench/freeze.json').read_text())
    entry = freeze['models'][corpus.name]
    config = from_dict(entry['config'])
    out = ROOT / 'data/native_ml' / args.variant
    out.mkdir(parents=True, exist_ok=True)
    report = {'status': 'running', 'corpus': corpus.name, 'freeze_sha256': sha256(ROOT / 'bench/freeze.json'),
        'scope': 'validation records only; exact retriever keys, ordered candidates and scores; no threshold tuning',
        'confirmation_scored': False, 'model': entry['model']}
    spark = create_session(config)
    try:
        loaded = tracking.load_composite(entry['model']['model_uri'], config).unwrap_python_model()
        native = loaded.native_model(spark)
        retriever = blocking.load_state(loaded.artifacts['retriever'])
        from pyspark.ml.feature import HashingTF
        from lakematch.murmur3 import hash_utf8
        terms = ['', 'a', 'ab', 'abc', 'abcd', 'abcde', 'abcdefg', 'Éli', '王', '王明', '🙂', "O'Brien", 'e\u0301', 'abc🙂王']
        hasher = HashingTF(numFeatures=config['candidates']['num_hash_features'])
        expected_indices = {term: hasher.indexOf(term) for term in terms}
        actual_indices = {row.term: row['index'] for row in spark.createDataFrame([(term,) for term in terms], 'term string')
            .select('term', F.pmod(hash_utf8(F.col('term')), F.lit(config['candidates']['num_hash_features'])).alias('index')).collect()}
        report['hash_indices'] = [{'term': term, 'expected': expected_indices[term], 'actual': actual_indices[term]} for term in terms]
        assert actual_indices == expected_indices, 'UTF-8 byte-tail hashing differs from MLlib'
        report['hash_edge_cases'] = len(terms)
        state = {'gbt': native_ml.export_gbt(spark, loaded.artifacts['pipeline'], features.feature_order(config)),
                 'minhash': native_ml.export_minhash(spark, Path(loaded.artifacts['retriever']) / 'lsh', config)}
        (out / 'native-state.json').write_text(json.dumps(state, indent=2) + '\n')
        schema = 'rec_id string, ' + ', '.join(field + ' string' for field in corpus.fields)
        with Materializer(spark, config, probe(spark)) as work:
            vocab = work.materialize(spark.read.parquet(loaded.artifacts['idf']), 'idf')
            prepared = [work.materialize(feature_stats.attach_idf(entity.prepare(spark.createDataFrame(
                [row for row in rows if row['split'] == 'valid'], schema), config), vocab, config), side)
                for side, rows in [('left', corpus.left), ('right', corpus.right)]]
            from pyspark.ml.functions import vector_to_array
            checked_records = 0
            for frame in prepared:
                old = retriever['model'].transform(blocking.hashed_records(frame, config)).select(
                    'rec_id', F.posexplode('lm_hashes').alias('rule', 'bucket')).select(
                        'rec_id', 'rule', vector_to_array('bucket')[0].cast('long').cast('string').alias('key'))
                new = native_ml.minhash_keys(frame, state['minhash'], 'rec_id')
                assert not old.exceptAll(new).limit(1).count() and not new.exceptAll(old).limit(1).count(), 'MinHash key mismatch'
                checked_records += frame.count()
            old_plan = blocking.build_alternative(*prepared, config, state=retriever)
            new_plan = native_ml.minhash_candidates(*prepared, config, state['minhash'])
            old_pairs = work.materialize(old_plan.pairs, 'old_pairs')
            new_pairs = work.materialize(new_plan.pairs, 'new_pairs')
            assert not old_pairs.exceptAll(new_pairs).limit(1).count() and not new_pairs.exceptAll(old_pairs).limit(1).count()
            vectors = work.materialize(features.build(old_pairs, *prepared, config), 'vectors')
            expected = matcher.score(vectors, native).select('a_id', 'b_id', F.col('p').alias('expected_p'))
            actual = native_ml.score_gbt(vectors, state['gbt']).select('a_id', 'b_id', 'p')
            observed = actual.join(expected, ['a_id', 'b_id']).agg(F.count('*').alias('pairs'),
                F.max(F.abs(F.col('p') - F.col('expected_p'))).alias('max_delta')).first()
            assert observed.pairs > 0 and observed.max_delta < 1e-12
            plan_text = StringIO()
            with redirect_stdout(plan_text):
                native_ml.score_gbt(features.build(new_plan.pairs, *prepared, config), state['gbt']).explain(mode='extended')
            assert not any(token in plan_text.getvalue() for token in ('PythonUDF', 'BatchEvalPython', 'ArrowEvalPython'))
            (out / 'native.plan.txt').write_text(plan_text.getvalue())
            report.update(records=checked_records, pairs=observed.pairs, maximum_probability_difference=observed.max_delta,
                exact_minhash_keys=True, exact_ordered_candidates=True, native_plan=True,
                candidate_budget=new_plan.validate_budget())
        report.update(status='completed', cleanup='succeeded')
    except Exception as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        spark.stop()
        report['wall_seconds_including_spark'] = time.perf_counter() - started
        report['evidence_files'] = {p.name: sha256(p) for p in [out / 'native-state.json', out / 'native.plan.txt'] if p.exists()}
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
