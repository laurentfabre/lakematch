#!/usr/bin/env python3
"""Bounded validation comparison of four native Spark clustering algorithms."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tarfile
import time

from pyspark.sql import Window, functions as F

from lakematch import blocking, candidates, clustering, entity, feature_stats, features, matcher, tracking
from lakematch.benchmark.clusters import cluster_bootstrap, cluster_group_counts, cluster_metrics
from lakematch.benchmark.corpora import Components, digest
from lakematch.benchmark.metrics import counts
from lakematch.config import from_dict
from lakematch.runtime import Materializer, create_session, probe
from evidence import sha256
from offline_run import assert_offline

METHODS = ['connected_components', 'center', 'star', 'verified_merge']


def pair_context(pairs, records, config):
    """Pair-local metadata is identical for training and arbitrary representatives.

    Self-dedupe has no directional retrieval rank. Use a fixed rank/gap and
    unweighted gram cosine, independent of which other pairs were requested.
    The composite's pair-level input signature includes these three columns.
    """
    left = blocking.text_grams(records, config, 'a_id', 'lm_a')
    right = blocking.text_grams(records, config, 'b_id', 'lm_b')
    joined = pairs.select('a_id', 'b_id').join(left, 'a_id').join(right, 'b_id')
    denominator = F.sqrt(F.size('lm_a').cast('double') * F.size('lm_b'))
    return joined.select('a_id', 'b_id', F.when(denominator > 0,
        F.size(F.array_intersect('lm_a', 'lm_b')) / denominator).otherwise(0.).alias('cos'),
        F.lit(1).alias('rank'), F.lit(0.).alias('gap'))


def pair_metrics(edges, truth, threshold):
    positive_pairs = sum(n * (n - 1) // 2 for n in Counter(truth.values()).values())
    selected = [(a, b) for a, b, p in edges if p >= threshold]
    tp = sum(truth[a] == truth[b] for a, b in selected)
    return counts(tp, len(selected) - tp, positive_pairs - tp)


def threshold_for(edges, truth):
    return max((pair_metrics(edges, truth, n / 100)['f1'], n / 100) for n in range(101))[1]


def components(records, edges, threshold):
    graph = Components()
    for a, b, p in edges:
        if p >= threshold:
            graph.union(a, b)
    return {key: graph.find(key) for key in records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('corpus', choices=['febrl3', 'historical_50k'])
    parser.add_argument('--estimator', choices=['gbt', 'logistic_regression', 'random_forest'], required=True)
    args = parser.parse_args()
    assert_offline()
    started = time.perf_counter()
    root = Path('data/bench') / args.corpus
    manifest = json.loads((root / 'manifest.json').read_text())
    records = [json.loads(line) for line in (root / 'records.jsonl').read_text().splitlines()]
    if digest(records) != manifest['record_digest']:
        raise ValueError('Frozen clustering corpus changed')
    raw = {'entity': {'name': args.corpus, 'fields': manifest['fields']},
        'candidates': {'method': 'field_blocks', 'k': 6, 'max_pairs': 500000, 'max_join_rows': 50000000},
        'features': {'multi_token': ['idf_token_cosine', 'gram_overlap', 'monge_elkan_token'],
                     'embeddings': {'provider': 'none'}},
        'matcher': {'estimator': args.estimator, 'max_iter': 20, 'max_depth': 3, 'seed': 0},
        'cluster': {'method': 'connected_components', 'max_rounds': 30},
        'decision': {'threshold': .5, 'cardinality': 'unrestricted'}}
    raw['candidates']['field_blocks'] = blocking.proposed_rules(from_dict(raw))
    out = (Path('data/clusters') / args.corpus).resolve()
    out.mkdir(parents=True, exist_ok=True)
    raw['mlflow'] = {'tracking_uri': f'sqlite:///{out}/mlflow.db', 'experiment': 'zr4-clusters'}
    config = from_dict(raw)
    report = {'status': 'running', 'iteration': 3, 'corpus': args.corpus, 'manifest': manifest,
        'config': config.data, 'plan': 'bench/CLUSTER_PLAN.md', 'confirmation_scored': False,
        'scope': 'training-only model/feature IDF; entity-disjoint validation graph',
        'pair_context': 'unweighted gram cosine; rank=1; gap=0 for every training/scoring/verification pair',
        'candidate_scope': 'k=6 including self, then self removed and orientations unioned; at most five outgoing nonself neighbours',
        'rows': [], 'baselines': [], 'cost': {'remote_spend': 0, 'live_label_spend': 0}}
    output = out / 'report.json'
    files = set()
    archive = out / 'cluster-evidence.tar.gz'
    archive.unlink(missing_ok=True)
    def save():
        report['evidence_files'] = {str(p.relative_to(out)): sha256(p) for p in sorted(files)}
        output.write_text(json.dumps(report, indent=2) + '\n')
    save()
    spark = create_session(config)
    try:
        capabilities = probe(spark)
        with Materializer(spark, config, capabilities) as materializer:
            schema = 'rec_id string, ' + ', '.join(f'{field} string' for field in manifest['fields'])
            partitions = {split: [r for r in records if r['split'] == split] for split in ('train', 'valid')}
            truth = {split: {r['rec_id']: r['truth_entity'] for r in rows} for split, rows in partitions.items()}
            assert set(truth['train'].values()).isdisjoint(truth['valid'].values())
            raw_frames = {split: spark.createDataFrame(rows, schema) for split, rows in partitions.items()}
            prepared = {split: materializer.materialize(entity.prepare(frame, config), split)
                        for split, frame in raw_frames.items()}
            idf = materializer.materialize(feature_stats.fit_idf([prepared['train']], config), 'idf')
            idf_path = out / 'idf'
            idf.write.mode('overwrite').parquet(str(idf_path))
            prepared = {split: materializer.materialize(feature_stats.attach_idf(frame, idf, config), 'weighted_' + split)
                        for split, frame in prepared.items()}
            candidate_frames = {}
            report['retrieval'] = {}
            for split, frame in prepared.items():
                t0 = time.perf_counter()
                plan = candidates.build(frame, frame, config)
                budget = plan.validate_budget()
                retrieved = materializer.materialize(plan.pairs, 'retrieved_' + split)
                nonself = retrieved.filter('a_id != b_id').withColumn('nonself_rank', F.row_number().over(
                    Window.partitionBy('a_id').orderBy(F.desc('cos'), 'b_id'))).filter('nonself_rank <= 5')
                undirected = nonself.select(
                    F.least('a_id', 'b_id').alias('a_id'), F.greatest('a_id', 'b_id').alias('b_id')).distinct()
                candidate_frames[split] = materializer.materialize(pair_context(undirected, frame, config), 'pairs_' + split)
                rows = candidate_frames[split].select('a_id', 'b_id', 'cos').collect()
                covered = sum(truth[split][r.a_id] == truth[split][r.b_id] for r in rows)
                positives = sum(n * (n - 1) // 2 for n in Counter(truth[split].values()).values())
                report['retrieval'][split] = {'budget': budget, 'undirected_pairs': len(rows),
                    'true_pairs': positives, 'covered_positives': covered, 'pair_recall': covered / positives,
                    'seconds': time.perf_counter() - t0}
                if split == 'train':
                    consumed = [{'a_id': r.a_id, 'b_id': r.b_id,
                        'label': float(truth[split][r.a_id] == truth[split][r.b_id])} for r in rows]
                else:
                    simple = [(r.a_id, r.b_id, r.cos) for r in rows]
            labels = spark.createDataFrame(consumed, 'a_id string, b_id string, label double')
            t0 = time.perf_counter()
            training = materializer.materialize(features.build(candidate_frames['train'], prepared['train'], prepared['train'], config), 'training')
            model = matcher.train(training, labels, config)
            report['feature_and_fit_seconds'] = time.perf_counter() - t0
            t0 = time.perf_counter()
            validation = features.build(candidate_frames['valid'], prepared['valid'], prepared['valid'], config)
            scored = materializer.materialize(matcher.score(validation, model).select('a_id', 'b_id', 'p'), 'scored')
            edges = [(r.a_id, r.b_id, r.p) for r in scored.collect()]
            report['feature_and_score_seconds'] = time.perf_counter() - t0
            threshold = threshold_for(edges, truth['valid'])
            raw['decision']['threshold'] = threshold
            config = from_dict(raw)
            report.update(config=config.data, threshold=threshold, pair_metrics=pair_metrics(edges, truth['valid'], threshold))
            example = tracking.pair_snapshot(candidate_frames['train'].orderBy('a_id', 'b_id').limit(5),
                raw_frames['train'], raw_frames['train'], config)
            report['model'] = tracking.log_composite(model, config, labels=consumed, input_example=example,
                experiment='zr4-clusters', staging_root=out / 'staging', idf_path=str(idf_path),
                metrics={'validation_pair_f1': report['pair_metrics']['f1']})
            reference = None
            for method in METHODS:
                method_raw = deepcopy(config.data)
                method_raw['cluster']['method'] = method
                selected = from_dict(method_raw)
                print(json.dumps({'method': method, 'status': 'started', 'threshold': threshold}), flush=True)
                t0 = time.perf_counter()
                with Materializer(spark, selected, capabilities) as rounds:
                    def scorer(requests):
                        pairs = pair_context(requests, prepared['valid'], selected)
                        vectors = features.build(pairs, prepared['valid'], prepared['valid'], selected)
                        return matcher.score(vectors, model).select('a_id', 'b_id', 'p')
                    result = clustering.resolve(prepared['valid'], scored, selected, rounds, pair_scorer=scorer)
                    membership = {r.rec_id: r.cluster for r in result.membership.collect()}
                    trace = result.rounds
                elapsed = time.perf_counter() - t0
                grouped = cluster_group_counts(truth['valid'], membership)
                reference = grouped if reference is None else reference
                row = {'method': method, 'seconds': elapsed, 'rounds': trace,
                    **cluster_metrics(truth['valid'], membership), **cluster_bootstrap(grouped, reference)}
                report['rows'].append(row)
                path = out / (method + '.predictions.json')
                path.write_text(json.dumps({'membership': membership, 'truth': truth['valid'], 'groups': grouped}) + '\n')
                files.add(path)
                save()
                print(json.dumps(row), flush=True)
            # Diagnostics have the same candidate graph; no truth is used to create edges.
            nearest = {}
            for a, b, similarity in simple:
                for anchor, partner in ((a, b), (b, a)):
                    choice = (-similarity, partner)
                    nearest[anchor] = min(nearest.get(anchor, choice), choice)
            nearest_edges = [(a, choice[1], 1.) for a, choice in nearest.items()]
            for name, baseline, cutoff in (('nearest_neighbour_components', nearest_edges, 0.),
                ('cosine_threshold_components', simple, threshold_for(simple, truth['valid']))):
                membership = components(truth['valid'], baseline, cutoff)
                report['baselines'].append({'name': name, 'threshold': cutoff,
                    **cluster_metrics(truth['valid'], membership),
                    **cluster_bootstrap(cluster_group_counts(truth['valid'], membership))})
            path = out / 'edges.json'
            path.write_text(json.dumps({'edges': edges, 'cosine': simple, 'truth': truth['valid']}) + '\n')
            files.add(path)
        report.update(status='completed', cleanup='succeeded')
    except Exception as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        try:
            spark.stop()
        finally:
            report['wall_seconds_including_spark'] = time.perf_counter() - started
            save()
            with tarfile.open(archive, 'w:gz') as bundle:
                for path in sorted(files | {output}):
                    bundle.add(path, arcname=str(path.relative_to(out)))


if __name__ == '__main__':
    main()
