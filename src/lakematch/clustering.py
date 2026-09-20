"""Deterministic job-time clustering with native Spark rounds and bounded work.

Center uses mean incident match probability; star uses incident edge count.
Both select simultaneous local-maximal centers, assign their neighbours by
center priority, remove assigned vertices, and repeat. Verified merge scores all
cross-products of each cluster's minimum/maximum-ID representatives each round.
"""
from dataclasses import dataclass

from pyspark.sql import Window, functions as F


class ConvergenceError(RuntimeError):
    def __init__(self, message, *, rounds=None):
        super().__init__(message)
        self.rounds = rounds or []


@dataclass
class ClusterResult:
    membership: object
    rounds: list
    method: str


def _bounded(frame, maximum, description):
    count = frame.limit(maximum + 1).count()
    if count > maximum:
        raise ValueError(f'{description} exceeds the configured job budget ({maximum})')
    return count


def _directions(edges):
    return edges.select(F.col('a_id').alias('src'), F.col('b_id').alias('dst'), 'p').unionByName(
        edges.select(F.col('b_id').alias('src'), F.col('a_id').alias('dst'), 'p'))


def resolve(vertices, edges, config, materializer, *, pair_scorer=None):
    """Call only from a job task. pair_scorer maps a_id/b_id to a_id/b_id/p.

    max_pairs bounds vertices, scored edges and verification pairs separately.
    A max_rounds failure is explicit; partial convergence is never published.
    """
    def materialize(frame, name):
        return materializer.materialize(frame, name, truncate=True)
    method = config['cluster']['method']
    limit = config['candidates']['max_pairs']
    threshold = config['decision']['threshold']
    if threshold == 'from_validation':
        raise ValueError('Clustering needs a frozen validation threshold')
    if method == 'verified_merge' and pair_scorer is None:
        raise ValueError('Verified merge requires a representative-pair scoring callback')
    ids = vertices.select('rec_id')
    if ids.filter(F.col('rec_id').isNull() | (F.length('rec_id') == 0)).limit(1).count():
        raise ValueError('Clustering requires nonempty record IDs')
    if ids.groupBy('rec_id').count().filter('count != 1').limit(1).count():
        raise ValueError('Clustering requires unique record IDs')
    size = _bounded(ids, limit, 'Vertex count')
    # Center/star reuse the remaining-vertex relation many times in one round.
    # A cached, feature-enriched input still carries its full logical lineage;
    # truncate the ID-only relation before any of those self-joins.
    ids = materialize(ids, 'cluster_vertices')
    valid = edges.filter(F.col('p').isNotNull() & ~F.isnan('p') & F.col('p').between(0., 1.) & (F.col('p') >= threshold))
    graph = valid.select(F.least('a_id', 'b_id').alias('a_id'), F.greatest('a_id', 'b_id').alias('b_id'), 'p')
    graph = graph.filter('a_id != b_id').groupBy('a_id', 'b_id').agg(F.max('p').alias('p'))
    for endpoint in ('a_id', 'b_id'):
        if graph.select(F.col(endpoint).alias('rec_id')).join(ids, 'rec_id', 'left_anti').limit(1).count():
            raise ValueError('Cluster edge references an unknown vertex')
    _bounded(graph, limit, 'Edge count')
    graph = materialize(graph, 'cluster_edges')
    labels = materialize(ids.withColumn('cluster', F.col('rec_id')), 'cluster_initial')
    trace = []
    if not size:
        return ClusterResult(labels, trace, method)
    directed = materialize(_directions(graph), 'cluster_directions')
    remaining, assigned = ids, None
    for iteration in range(1, config['cluster']['max_rounds'] + 1):
        if method == 'connected_components':
            messages = directed.join(labels, F.col('src') == F.col('rec_id')).select(F.col('dst').alias('rec_id'), 'cluster')
            updated = labels.unionByName(messages).groupBy('rec_id').agg(F.min('cluster').alias('cluster'))
            # Every label is a vertex in the same connected component. Following
            # that vertex's new label shortcuts long chains without collecting
            # the graph or changing the minimum-ID fixed point.
            parents = updated.select(F.col('rec_id').alias('parent_id'), F.col('cluster').alias('ancestor'))
            updated = updated.join(parents, F.col('cluster') == F.col('parent_id')).select(
                'rec_id', F.least('cluster', 'ancestor').alias('cluster'))
            updated = materialize(updated, f'components_round_{iteration}')
            changed = labels.withColumnRenamed('cluster', 'old_cluster').join(updated, 'rec_id').filter('old_cluster != cluster').count()
            trace.append({'round': iteration, 'changed_vertices': changed})
            labels = updated
            if not changed:
                return ClusterResult(labels, trace, method)
        elif method in {'center', 'star'}:
            active = directed.join(remaining.select(F.col('rec_id').alias('src')), 'src', 'semi').join(
                remaining.select(F.col('rec_id').alias('dst')), 'dst', 'semi')
            priority = remaining.join(active.groupBy('src').agg(F.count('*').alias('degree'), F.avg('p').alias('mean')),
                remaining.rec_id == F.col('src'), 'left').drop('src').fillna(0, ['degree', 'mean'])
            priority = priority.withColumn('priority', F.col('mean') if method == 'center' else F.col('degree'))
            competitors = active.select('src', 'dst').join(priority.select(F.col('rec_id').alias('src'), F.col('priority').alias('own')), 'src').join(
                priority.select(F.col('rec_id').alias('dst'), F.col('priority').alias('other')), 'dst')
            dominated = competitors.filter((F.col('other') > F.col('own')) | ((F.col('other') == F.col('own')) & (F.col('dst') < F.col('src'))))
            centers = priority.join(dominated.select(F.col('src').alias('rec_id')).distinct(), 'rec_id', 'left_anti')
            choices = active.join(centers.select(F.col('rec_id').alias('src'), 'priority'), 'src').select(
                F.col('dst').alias('rec_id'), F.col('src').alias('cluster'), 'priority').unionByName(
                centers.select('rec_id', F.col('rec_id').alias('cluster'), 'priority'))
            selected = choices.withColumn('choice', F.row_number().over(Window.partitionBy('rec_id').orderBy(F.desc('priority'), 'cluster'))).filter('choice = 1').select('rec_id', 'cluster')
            selected = materialize(selected, f'centers_round_{iteration}')
            count = selected.count()
            if not count:
                raise ConvergenceError('Center selection made no progress')
            assigned = selected if assigned is None else assigned.unionByName(selected)
            remaining = materialize(remaining.join(selected.select('rec_id'), 'rec_id', 'left_anti'), f'remaining_round_{iteration}')
            pending = remaining.count()
            trace.append({'round': iteration, 'assigned_vertices': count, 'remaining_vertices': pending})
            if not pending:
                return ClusterResult(assigned, trace, method)
        elif method == 'verified_merge':
            cluster_edges = graph.join(labels.select(F.col('rec_id').alias('a_id'), F.col('cluster').alias('ca')), 'a_id').join(
                labels.select(F.col('rec_id').alias('b_id'), F.col('cluster').alias('cb')), 'b_id')
            proposed = cluster_edges.filter('ca != cb').select(F.least('ca', 'cb').alias('ca'), F.greatest('ca', 'cb').alias('cb'), 'p').groupBy('ca', 'cb').agg(F.max('p').alias('p'))
            proposed = materialize(proposed, f'proposed_round_{iteration}')
            proposed_count = proposed.count()
            if not proposed_count:
                trace.append({'round': iteration, 'proposals': 0, 'merges': 0})
                return ClusterResult(labels, trace, method)
            reps = labels.groupBy('cluster').agg(F.array_distinct(F.array(F.min('rec_id'), F.max('rec_id'))).alias('representatives'))
            requests = proposed.join(reps.select(F.col('cluster').alias('ca'), F.col('representatives').alias('ra')), 'ca').join(
                reps.select(F.col('cluster').alias('cb'), F.col('representatives').alias('rb')), 'cb').select('ca', 'cb', F.explode('ra').alias('a_id'), 'rb').select('ca', 'cb', 'a_id', F.explode('rb').alias('b_id'))
            request_pairs = requests.select(F.least('a_id', 'b_id').alias('a_id'), F.greatest('a_id', 'b_id').alias('b_id')).distinct()
            verified_count = _bounded(request_pairs, limit, 'Representative verification pairs')
            scores = pair_scorer(request_pairs)
            if scores.groupBy('a_id', 'b_id').count().filter('count != 1').limit(1).count():
                raise ValueError('Representative scorer returned duplicate pairs')
            requests = requests.select('ca', 'cb', F.least('a_id', 'b_id').alias('a_id'), F.greatest('a_id', 'b_id').alias('b_id'))
            checks = requests.join(scores.select('a_id', 'b_id', F.col('p').alias('verified_p')), ['a_id', 'b_id'], 'left')
            accepted = checks.groupBy('ca', 'cb').agg(F.min(F.coalesce(
                ~F.isnan('verified_p') & F.col('verified_p').between(threshold, 1.), F.lit(False))).alias('accepted'))
            accepted = materialize(proposed.join(accepted.filter('accepted'), ['ca', 'cb']), f'accepted_round_{iteration}')
            accepted_count = accepted.count()
            options = accepted.select(F.col('ca').alias('src'), F.col('cb').alias('dst'), 'p').unionByName(
                accepted.select(F.col('cb').alias('src'), F.col('ca').alias('dst'), 'p'))
            best = options.withColumn('choice', F.row_number().over(Window.partitionBy('src').orderBy(F.desc('p'), 'dst'))).filter('choice = 1').select('src', 'dst')
            reverse = best.select(F.col('src').alias('rdst'), F.col('dst').alias('rsrc'))
            mutual = best.join(reverse, (F.col('src') == F.col('rsrc')) & (F.col('dst') == F.col('rdst'))).filter('src < dst').select(
                F.col('dst').alias('cluster'), F.col('src').alias('merged_cluster'))
            mutual = materialize(mutual, f'merged_round_{iteration}')
            merges = mutual.count()
            trace.append({'round': iteration, 'proposals': proposed_count, 'verification_pairs': verified_count,
                          'vetoed_proposals': proposed_count - accepted_count, 'merges': merges})
            if not merges:
                if accepted_count:
                    raise ConvergenceError('Accepted symmetric edges produced no mutual merge')
                return ClusterResult(labels, trace, method)
            labels = materialize(labels.join(mutual, 'cluster', 'left').select('rec_id',
                F.coalesce('merged_cluster', 'cluster').alias('cluster')), f'verified_round_{iteration}')
        else:
            raise ValueError('Unknown clustering method')
    raise ConvergenceError(f'{method} did not converge within {config["cluster"]["max_rounds"]} rounds', rounds=trace)
