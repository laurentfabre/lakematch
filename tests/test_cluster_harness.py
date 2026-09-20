import importlib.util
from pathlib import Path
import sys


def test_threshold_includes_missing_positive_pairs_and_never_invents_negatives():
    sys.path.insert(0, str(Path('tools').resolve()))
    spec = importlib.util.spec_from_file_location('cluster_harness', 'tools/run_clusters.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    truth = {'a': 'x', 'b': 'x', 'c': 'x', 'd': 'y'}
    edges = [('a', 'b', .9), ('a', 'd', .4)]
    metrics = module.pair_metrics(edges, truth, .5)
    assert (metrics['tp'], metrics['fp'], metrics['fn']) == (1, 0, 2)
    assert module.threshold_for(edges, truth) == .9
    assert module.cluster_metrics(truth, module.components(truth, edges, .5))['fn'] == 2


def test_increment_mutates_exact_disjoint_counts_and_is_deterministic():
    sys.path.insert(0, str(Path('tools').resolve()))
    spec = importlib.util.spec_from_file_location('identity_harness', 'tools/run_identity_increment.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = [{'rec_id': str(i), 'name': f'person {i // 2}', 'truth_entity': str(i // 2), 'split': 'valid'} for i in range(100)]
    changed, manifest = module.mutate(original, ['name'], 'synthetic')
    repeated, repeated_manifest = module.mutate(original, ['name'], 'synthetic')
    assert (changed, manifest) == (repeated, repeated_manifest)
    assert manifest['per_operation_count'] == 1
    assert set(manifest['deleted']).isdisjoint(manifest['changed'])
    before, after = [{row['rec_id']: row['name'] for row in rows} for rows in (original, changed)]
    assert len(before.keys() - after.keys()) == len(after.keys() - before.keys()) == 1
    assert sum(before[key] != after[key] for key in before.keys() & after.keys()) == 1
    assert all(row['name'] == f'person {int(row["rec_id"]) // 2}' for row in original)
