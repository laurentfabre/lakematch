"""Lazy deterministic identities and complete snapshot reconciliation journals."""
from dataclasses import dataclass

from pyspark.sql import functions as F


def assign(membership, namespace):
    """Canonical key is the smallest stable record ID in each declared cluster.

    IDs are stable on unchanged membership. Removing the canonical member or
    adding a smaller ID may rekey a cluster; reconcile records that explicitly.
    Membership columns: rec_id, cluster, record_digest (raw-record fingerprint).
    """
    canonical = membership.groupBy('cluster').agg(F.min('rec_id').alias('canonical_key'))
    return membership.join(canonical, 'cluster').select('rec_id', 'record_digest', 'canonical_key',
        F.sha2(F.to_json(F.struct(F.lit(namespace).alias('namespace'), 'canonical_key')), 256).alias('mdm_id'))


@dataclass
class Reconciliation:
    changes: object
    cluster_events: object


def reconcile(previous, current):
    """Inputs are complete unique-record snapshots; validation is a job action.

    The change journal contains every record, including unchanged records, and
    enough old/new information to replay and verify the exact current crosswalk.
    Cluster events can coexist: a simultaneous merge/split is not collapsed into
    a single misleading label. Deleted/new clusters are reported separately.
    """
    fields = ['mdm_id', 'record_digest', 'canonical_key']
    old = previous.select('rec_id', *[F.col(n).alias('old_' + n) for n in fields])
    new = current.select('rec_id', *[F.col(n).alias('new_' + n) for n in fields])
    changes = old.join(new, 'rec_id', 'full').withColumn('change',
        F.when(F.col('old_mdm_id').isNull(), 'added')
         .when(F.col('new_mdm_id').isNull(), 'deleted')
         .when(~F.col('old_mdm_id').eqNullSafe(F.col('new_mdm_id')) &
               ~F.col('old_record_digest').eqNullSafe(F.col('new_record_digest')), 'moved_and_changed')
         .when(~F.col('old_mdm_id').eqNullSafe(F.col('new_mdm_id')), 'moved')
         .when(~F.col('old_record_digest').eqNullSafe(F.col('new_record_digest')), 'changed')
         .otherwise('unchanged'))
    edges = changes.filter('old_mdm_id IS NOT NULL AND new_mdm_id IS NOT NULL').select('old_mdm_id', 'new_mdm_id').distinct()
    to_new = edges.groupBy('new_mdm_id').agg(F.sort_array(F.collect_set('old_mdm_id')).alias('old_ids'))
    to_old = edges.groupBy('old_mdm_id').agg(F.sort_array(F.collect_set('new_mdm_id')).alias('new_ids'))
    merged = to_new.filter(F.size('old_ids') > 1).select(F.lit('merge').alias('event'), 'old_ids', F.array('new_mdm_id').alias('new_ids'))
    split = to_old.filter(F.size('new_ids') > 1).select(F.lit('split').alias('event'), F.array('old_mdm_id').alias('old_ids'), 'new_ids')
    rekey = (edges.join(to_new, 'new_mdm_id').join(to_old, 'old_mdm_id')
        .filter((F.size('old_ids') == 1) & (F.size('new_ids') == 1) & (F.col('old_mdm_id') != F.col('new_mdm_id')))
        .select(F.lit('rekey').alias('event'), 'old_ids', 'new_ids'))
    empty = F.array().cast('array<string>')
    retired = previous.select('mdm_id').distinct().join(edges, F.col('mdm_id') == F.col('old_mdm_id'), 'left_anti').select(
        F.lit('retired').alias('event'), F.array('mdm_id').alias('old_ids'), empty.alias('new_ids'))
    created = current.select('mdm_id').distinct().join(edges, F.col('mdm_id') == F.col('new_mdm_id'), 'left_anti').select(
        F.lit('created').alias('event'), empty.alias('old_ids'), F.array('mdm_id').alias('new_ids'))
    events = merged.unionByName(split).unionByName(rekey).unionByName(retired).unionByName(created)
    return Reconciliation(changes, events)


def replay(changes):
    return changes.filter('new_mdm_id IS NOT NULL').select('rec_id', F.col('new_mdm_id').alias('mdm_id'),
        F.col('new_record_digest').alias('record_digest'), F.col('new_canonical_key').alias('canonical_key'))


def validate_snapshot(frame):
    """Fail early in the job; never silently deduplicate conflicting crosswalks."""
    for name in ('rec_id', 'mdm_id', 'record_digest', 'canonical_key'):
        if frame.filter(F.col(name).isNull() | (F.length(name) == 0)).limit(1).count():
            raise ValueError('Identity snapshots require nonempty keys and fingerprints')
    if frame.groupBy('rec_id').count().filter('count != 1').limit(1).count():
        raise ValueError('Identity snapshot contains duplicate record IDs')
