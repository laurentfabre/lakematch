import pytest

from lakematch.identity import assign, reconcile, replay, validate_snapshot


def snapshot(spark, rows):
    return assign(spark.createDataFrame(rows, 'rec_id string, cluster string, record_digest string'), 'fixture')


def test_stable_identity_and_exact_merge_split_change_delete_replay(spark):
    old_rows = [('a','one','A'),('b','one','B'),('c','two','C'),('d','two','D'),('e','retire','E')]
    old = snapshot(spark, old_rows)
    assert old.orderBy('rec_id').collect() == snapshot(spark, list(reversed(old_rows))).orderBy('rec_id').collect()
    new = snapshot(spark, [('a','new','A2'),('b','new','B'),('c','new','C'),('d','other','D'),('f','create','F')])
    validate_snapshot(old)
    validate_snapshot(new)
    result = reconcile(old, new)
    journal = {r.rec_id: r.change for r in result.changes.collect()}
    assert journal == {'a':'changed','b':'unchanged','c':'moved','d':'moved','e':'deleted','f':'added'}
    assert {r.event for r in result.cluster_events.collect()} == {'merge','split','retired','created'}
    columns = ['rec_id','mdm_id','record_digest','canonical_key']
    assert replay(result.changes).select(*columns).orderBy('rec_id').collect() == new.select(*columns).orderBy('rec_id').collect()
    with pytest.raises(ValueError, match='duplicate'):
        validate_snapshot(old.unionByName(old))


def test_canonical_member_removal_is_a_rekey(spark):
    result = reconcile(snapshot(spark,[('a','one','A'),('b','one','B')]), snapshot(spark,[('b','one','B')]))
    assert [r.event for r in result.cluster_events.collect()] == ['rekey']
