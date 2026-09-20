import pytest

from lakematch.benchmark.clusters import cluster_metrics


def test_cluster_metrics_penalize_splits_merges_and_include_singletons():
    truth = {'a': 'one', 'b': 'one', 'c': 'two', 'd': 'two', 'e': 'singleton'}
    result = cluster_metrics(truth, {'a': 'x', 'b': 'y', 'c': 'y', 'd': 'y', 'e': 'z'})
    assert (result['tp'], result['fp'], result['fn']) == (1, 2, 1)
    assert result['bcubed_precision'] == pytest.approx(11/15)
    assert result['bcubed_recall'] == pytest.approx(.8)
    assert cluster_metrics(truth, truth)['bcubed_f1'] == 1.
    with pytest.raises(ValueError, match='same nonempty'):
        cluster_metrics(truth, {'a': 'x'})


def test_cluster_bootstrap_contributions_reconcile_cross_entity_false_positives():
    from lakematch.benchmark.clusters import cluster_bootstrap, cluster_group_counts
    truth={'a':'one','b':'one','c':'two','d':'two','e':'singleton'}
    predicted={'a':'x','b':'y','c':'y','d':'y','e':'z'}
    groups=cluster_group_counts(truth,predicted)
    assert [sum(row[i] for row in groups.values()) for i in range(3)]==[1.,2.,1.]
    report=cluster_bootstrap(groups,groups,resamples=50)
    assert report['pairwise_delta_95ci']==report['bcubed_delta_95ci']==[0.,0.]
