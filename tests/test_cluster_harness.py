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
