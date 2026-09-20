#!/usr/bin/env python3
"""Re-run the selected clusterer, then reconcile a fixed 1% validation mutation."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import tarfile
import time

from pyspark.sql import Window, functions as F

from lakematch import candidates, clustering, entity, feature_stats, features, identity, matcher, tracking
from lakematch.benchmark.corpora import digest, rank
from lakematch.config import from_dict
from lakematch.runtime import Materializer, create_session, probe
from evidence import ROOT, sha256
from offline_run import assert_offline
from run_clusters import pair_context


def mutate(records, fields, namespace):
    """Disjoint removal/change/add-source sets, fixed before incremental scoring."""
    ordered = sorted(records, key=lambda row: rank('increment/' + namespace, row['rec_id']))
    count = max(1, len(records) // 100)
    removed = {row['rec_id'] for row in ordered[:count]}
    changes = {}
    for row in ordered[count:2 * count]:
        donor = next(other for other in ordered[3 * count:] if other['truth_entity'] != row['truth_entity']
                     and any(other[field] != row[field] for field in fields))
        changes[row['rec_id']] = {**row, **{field: donor[field] for field in fields}, 'truth_entity': donor['truth_entity']}
    additions = [{**row, 'rec_id': f"added-{i:06d}-{row['rec_id']}"}
                 for i, row in enumerate(ordered[2 * count:3 * count])]
    current = [changes.get(row['rec_id'], row) for row in records if row['rec_id'] not in removed] + additions
    assert len({row['rec_id'] for row in current}) == len(current) == len(records)
    return current, {'seed': 2026091901, 'records_before': len(records), 'records_after': len(current),
        'per_operation_count': count, 'fraction': count / len(records),
        'deleted': sorted(removed), 'changed': sorted(changes), 'added': [row['rec_id'] for row in additions],
        'changed_fields': sorted(fields), 'change_rule': 'replace complete profile with a different validation entity; preserve record ID',
        'added_rule': 'clone a validation profile with a new record ID',
        'before_digest': digest(records), 'after_digest': digest(current)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('corpus', choices=['febrl3', 'historical_50k'])
    args = parser.parse_args()
    assert_offline()
    started = time.perf_counter()
    selection = json.loads(Path('bench/cluster_index.json').read_text())
    if selection['status'] != 'comparisons_completed':
        raise ValueError('Complete and report both native clustering comparisons before identity acceptance')
    chosen = selection['recommendation']
    entry = selection['runs']['cluster-' + args.corpus]
    reference_path = ROOT / entry['report']
    if sha256(reference_path) != entry['report_sha256']:
        raise ValueError('Selected clustering evidence changed')
    reference = json.loads(reference_path.read_text())
    manifest = json.loads((ROOT / entry['manifest']).read_text())
    reference_archive = next(ROOT / item['path'] for item in manifest['artifacts'] if item['path'].endswith('cluster-evidence.tar.gz'))
    expected_hash = next(item['sha256'] for item in manifest['artifacts'] if item['path'].endswith('cluster-evidence.tar.gz'))
    assert sha256(reference_archive) == expected_hash
    with tarfile.open(reference_archive, 'r:gz') as archive:
        reference_membership = json.load(archive.extractfile(chosen + '.predictions.json'))['membership']
    root = Path('data/bench') / args.corpus
    records = [json.loads(line) for line in (root / 'records.jsonl').read_text().splitlines()]
    if digest(records) != reference['manifest']['record_digest']:
        raise ValueError('Frozen clustering corpus changed')
    original = [row for row in records if row['split'] == 'valid']
    raw = deepcopy(reference['config'])
    raw['cluster']['method'] = chosen
    config = from_dict(raw)
    current, mutation = mutate(original, config.fields, args.corpus)
    out = (Path('data/identity_increment') / args.corpus).resolve()
    out.mkdir(parents=True, exist_ok=True)
    mutation_path = out / 'mutation.json'
    if mutation_path.exists() and json.loads(mutation_path.read_text()) != mutation:
        raise ValueError('Previously frozen incremental mutation differs')
    mutation_path.write_text(json.dumps(mutation, indent=2) + '\n')
    report = {'status': 'running', 'iteration': 6, 'corpus': args.corpus, 'method': chosen,
        'comparison_run': entry['run_id'], 'model': reference['model'], 'config': config.data,
        'mutation': mutation, 'confirmation_scored': False, 'runs': [],
        'cost': {'remote_spend': 0, 'live_label_spend': 0}}
    output = out / 'report.json'
    files = {mutation_path}
    def save():
        report['evidence_files'] = {str(path.relative_to(out)): sha256(path) for path in sorted(files)}
        output.write_text(json.dumps(report, indent=2) + '\n')
    save()
    spark = create_session(config)
    try:
        capabilities = probe(spark)
        loaded = tracking.load_composite(reference['model']['model_uri'], config, out / 'loaded').unwrap_python_model()
        model = loaded.native_model(spark)
        with Materializer(spark, config, capabilities) as shared:
            vocab = None
            if 'idf_token_cosine' in config['features']['multi_token']:
                vocab = shared.materialize(spark.read.parquet(loaded.artifacts['idf']), 'idf')
            def resolve(rows, name):
                t0 = time.perf_counter()
                schema = 'rec_id string, ' + ', '.join(f'{field} string' for field in config.fields)
                raw_frame = spark.createDataFrame(rows, schema)
                fingerprints = raw_frame.select('rec_id', F.sha2(F.to_json(F.struct(
                    *[F.col(field) for field in sorted(config.fields)])), 256).alias('record_digest'))
                with Materializer(spark, config, capabilities) as work:
                    prepared = entity.prepare(raw_frame, config)
                    if vocab is not None:
                        prepared = feature_stats.attach_idf(prepared, vocab, config)
                    prepared = work.materialize(prepared, 'prepared')
                    plan = candidates.build(prepared, prepared, config)
                    budget = plan.validate_budget()
                    retrieved = work.materialize(plan.pairs, 'retrieved')
                    nonself = retrieved.filter('a_id != b_id').withColumn('nonself_rank', F.row_number().over(
                        Window.partitionBy('a_id').orderBy(F.desc('cos'), 'b_id'))).filter('nonself_rank <= 5')
                    pairs = nonself.select(F.least('a_id', 'b_id').alias('a_id'), F.greatest('a_id', 'b_id').alias('b_id')).distinct()
                    def scorer(requests):
                        comparisons = features.build(pair_context(requests, prepared, config), prepared, prepared, config)
                        return matcher.score(comparisons, model).select('a_id', 'b_id', 'p')
                    edges = work.materialize(scorer(pairs), 'scored')
                    result = clustering.resolve(prepared, edges, config, work, pair_scorer=scorer)
                    snapshot = identity.assign(result.membership.join(fingerprints, 'rec_id'), args.corpus)
                    snapshot = shared.materialize(snapshot, name, truncate=True)
                    identity.validate_snapshot(snapshot)
                    report['runs'].append({'name': name, 'budget': budget, 'rounds': result.rounds,
                        'seconds': time.perf_counter() - t0, 'records': len(rows)})
                return snapshot, fingerprints
            before, fingerprints = resolve(original, 'before')
            expected = spark.createDataFrame(sorted(reference_membership.items()), 'rec_id string, cluster string')
            expected = identity.assign(expected.join(fingerprints, 'rec_id'), args.corpus)
            columns = ['rec_id', 'mdm_id', 'canonical_key', 'record_digest']
            def equal(a, b):
                return not a.select(*columns).exceptAll(b.select(*columns)).limit(1).count() and not b.select(*columns).exceptAll(a.select(*columns)).limit(1).count()
            if not equal(before, expected):
                raise AssertionError('Unchanged input did not reproduce comparison identities')
            after, _ = resolve(current, 'after')
            journal = identity.reconcile(before, after)
            changes = shared.materialize(journal.changes, 'journal', truncate=True)
            events = shared.materialize(journal.cluster_events, 'events', truncate=True)
            if not equal(identity.replay(changes), after):
                raise AssertionError('Journal replay does not reproduce the complete new crosswalk')
            observed = {r.change: r['count'] for r in changes.groupBy('change').count().collect()}
            count = mutation['per_operation_count']
            if observed.get('added', 0) != count or observed.get('deleted', 0) != count or sum(
                    observed.get(key, 0) for key in ('changed', 'moved_and_changed')) != count:
                raise AssertionError('Recorded changes do not reconcile with the frozen mutation')
            repeated, _ = resolve(current, 'repeated')
            if not equal(after, repeated):
                raise AssertionError('Repeated incremental input changed identities')
            repeated_journal = identity.reconcile(after, repeated)
            if repeated_journal.changes.filter("change != 'unchanged'").limit(1).count() or repeated_journal.cluster_events.limit(1).count():
                raise AssertionError('Idempotent repetition emitted identity changes or cluster events')
            for name, frame in (('before', before), ('after', after), ('changes', changes), ('cluster_events', events)):
                path = out / (name + '.json')
                path.write_text(json.dumps([row.asDict(recursive=True) for row in frame.collect()]) + '\n')
                files.add(path)
            report.update(unchanged_input_stable=True, exact_journal_replay=True, incremental_repeat_idempotent=True,
                observed_changes=observed, cluster_events={r.event: r['count'] for r in events.groupBy('event').count().collect()})
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
            with tarfile.open(out / 'identity-evidence.tar.gz', 'w:gz') as archive:
                for path in sorted(files | {output}):
                    archive.add(path, arcname=str(path.relative_to(out)))


if __name__ == '__main__':
    main()
