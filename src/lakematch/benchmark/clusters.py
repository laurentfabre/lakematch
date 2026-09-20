"""Frozen public clustering tasks and linear-time pairwise/B-cubed metrics."""
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path

from .corpora import canonical, digest, rank


@dataclass
class ClusterCorpus:
    name: str
    fields: dict
    records: list
    manifest: dict

    def freeze(self, root='data/bench'):
        directory = Path(root) / self.name
        directory.mkdir(parents=True, exist_ok=True)
        content = ''.join(canonical(row) + '\n' for row in self.records)
        path = directory / 'records.jsonl'
        if path.exists() and path.read_text() != content:
            raise ValueError('Frozen cluster records differ')
        path.write_text(content)
        body = {**self.manifest, 'name': self.name, 'fields': self.fields,
                'records': len(self.records), 'record_digest': digest(self.records),
                'splits': dict(Counter(r['split'] for r in self.records)),
                'entities': len({r['truth_entity'] for r in self.records}), 'confirmation_scored': False}
        manifest = directory / 'manifest.json'
        if manifest.exists() and json.loads(manifest.read_text()) != body:
            raise ValueError('Frozen clustering manifest differs')
        manifest.write_text(json.dumps(body, indent=2) + '\n')
        return manifest


def load(name):
    import pandas as pd
    from .corpora import Components
    root = Path('data/sources/clustering')
    sources = json.loads((root / 'manifest.json').read_text())
    for item in sources['sources']:
        import hashlib
        if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Clustering source checksum mismatch')
    if name == 'febrl3':
        frame = pd.read_csv(root / 'febrl3.csv', dtype=str).fillna('')
        graph = Components()
        for a, b in json.loads((root / 'febrl3_links.json').read_text()):
            graph.union(a, b)
        assignments = {ident: graph.find(ident) for ident in frame.rec_id}
        fields = {n: {'type': 'person_name' if n in {'given_name', 'surname'} else
            'date' if n == 'date_of_birth' else 'code' if n in {'street_number', 'postcode', 'state', 'soc_sec_id'} else 'address',
            **({'date_format': 'yyyyMMdd'} if n == 'date_of_birth' else {})} for n in frame.columns if n != 'rec_id'}
    elif name == 'historical_50k':
        frame = pd.read_parquet(root / 'historical_figures_with_errors_50k.parquet').fillna('').rename(columns={'unique_id': 'rec_id'})
        frame['rec_id'] = frame.rec_id.astype(str)
        assignments = dict(zip(frame.rec_id, frame.cluster.astype(str)))
        # Avoid repeating the same names in several overlapping columns.
        fields = {'full_name': {'type': 'person_name'}, 'dob': {'type': 'date'},
                  'birth_place': {'type': 'address'}, 'postcode_fake': {'type': 'code'},
                  'gender': {'type': 'code'}, 'occupation': {'type': 'organisation'}}
    else:
        raise ValueError('Unknown clustering corpus')
    entities = sorted(set(assignments.values()), key=lambda k: rank(name + '/entities', k))
    split_of = {key: 'train' if i < int(len(entities) * .6) else 'valid' if i < int(len(entities) * .8)
                else 'confirmation' for i, key in enumerate(entities)}
    records = [{'rec_id': str(row['rec_id']), **{f: str(row[f]) for f in fields},
                'truth_entity': assignments[str(row['rec_id'])], 'split': split_of[assignments[str(row['rec_id'])]]}
               for row in frame.to_dict('records')]
    return ClusterCorpus(name, fields, records, {'sources': sources, 'split_seed': 2026091901,
        'split_method': 'SHA-256 ranked whole truth entities; floor 60/20/20; no record crosses a split',
        'evaluation_scope': 'partition-specific clustering; confirmation remains unscored'})


def cluster_metrics(truth, predicted):
    """Count contingency cells, avoiding quadratic pair enumeration."""
    if not truth or set(truth) != set(predicted):
        raise ValueError('Clustering metrics require the same nonempty record universe')
    actual, found = Counter(truth.values()), Counter(predicted.values())
    cells = Counter((truth[k], predicted[k]) for k in truth)
    choose2 = lambda n: n * (n - 1) // 2
    tp = sum(choose2(n) for n in cells.values())
    fp = sum(choose2(n) for n in found.values()) - tp
    fn = sum(choose2(n) for n in actual.values()) - tp
    from .metrics import counts
    precision = sum(n * n / found[p] for (t, p), n in cells.items()) / len(truth)
    recall = sum(n * n / actual[t] for (t, p), n in cells.items()) / len(truth)
    return {**counts(tp, fp, fn), 'bcubed_precision': precision, 'bcubed_recall': recall,
            'bcubed_f1': 2 * precision * recall / (precision + recall),
            'records': len(truth), 'truth_clusters': len(actual), 'predicted_clusters': len(found)}


def cluster_group_counts(truth, predicted):
    """Fixed-partition contributions by true entity, including half cross-entity FP.

    Resampling these contributions quantifies uncertainty in measured partitions;
    it does not refit or recluster bootstrap datasets.
    """
    if not truth or set(truth) != set(predicted):
        raise ValueError('Clustering metrics require the same nonempty record universe')
    actual, found = Counter(truth.values()), Counter(predicted.values())
    cells = Counter((truth[k], predicted[k]) for k in truth)
    groups = {key: [0., 0., n*(n-1)/2, 0., 0., n] for key, n in actual.items()}
    for (true, predicted_id), size in cells.items():
        row = groups[true]
        tp = size*(size-1)/2
        row[0] += tp
        row[1] += size*(found[predicted_id]-size)/2
        row[2] -= tp
        row[3] += size*size/found[predicted_id]
        row[4] += size*size/actual[true]
    return groups


def cluster_bootstrap(groups, reference=None, resamples=2000):
    import random
    from .metrics import BOOTSTRAP_SEED, counts
    keys = sorted(groups)
    if not keys or (reference is not None and set(keys) != set(reference)):
        raise ValueError('Cluster bootstrap requires identical nonempty true-entity groups')
    rng = random.Random(BOOTSTRAP_SEED)
    samples = {'pairwise_f1': [], 'bcubed_f1': [], 'pairwise_delta': [], 'bcubed_delta': []}
    def scores(rows, selected):
        total = [sum(rows[k][i] for k in selected) for i in range(6)]
        precision, recall = total[3]/total[5], total[4]/total[5]
        return counts(*total[:3])['f1'], 2*precision*recall/(precision+recall)
    for _ in range(resamples):
        selected = rng.choices(keys, k=len(keys))
        pairwise, bcubed = scores(groups, selected)
        samples['pairwise_f1'].append(pairwise)
        samples['bcubed_f1'].append(bcubed)
        if reference is not None:
            pair_ref, bcubed_ref = scores(reference, selected)
            samples['pairwise_delta'].append(pairwise-pair_ref)
            samples['bcubed_delta'].append(bcubed-bcubed_ref)
    def interval(rows):
        rows = sorted(rows)
        return [rows[int((len(rows)-1)*.025)],rows[int((len(rows)-1)*.975)]] if rows else None
    return {**{k+'_95ci':interval(v) for k,v in samples.items()}, 'bootstrap_seed':BOOTSTRAP_SEED,
            'bootstrap_resamples':resamples,'bootstrap_units':'true entities; fixed-partition contributions; cross-entity FP split equally'}
