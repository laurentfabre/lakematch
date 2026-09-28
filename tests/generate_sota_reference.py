"""Offline fixture regeneration; optional oracle dependencies, never imported by the test suite.

Run with RapidFuzz 3.14.3 and the SciPy version recorded in fixtures/sota_reference.json.
The Spark implementation is deliberately not imported. Custom variants compose published metric
primitives; this is an independent oracle, not a claim of full RapidFuzz SoftTF-IDF equivalence.
"""
import itertools
import json
import math
from collections import Counter
from pathlib import Path

import rapidfuzz
import scipy
from rapidfuzz.distance import Indel, Levenshtein, OSA
from scipy.spatial.distance import braycurtis, cosine, jaccard


def grams(s, padded):
    if padded:
        chars = [None, *s, None]
        return Counter(zip(chars, chars[1:]))
    return Counter([('short', s)] if len(s) < 3 else [('gram', s[i:i+3]) for i in range(len(s)-2)])


def vectors(a, b):
    keys = list(dict.fromkeys([*a, *b]))
    return [a.get(k, 0) for k in keys], [b.get(k, 0) for k in keys]


def soft(a, b):
    if not a or not b:
        return -1.0
    def directed(x, y):
        nx, ny = math.hypot(*x.values()), math.hypot(*y.values())
        total = 0.0
        for token, weight in x.items():
            scores = [(Levenshtein.normalized_similarity(token, other), other) for other in sorted(y)]
            score, target = max(scores, key=lambda pair: pair[0])
            if score > 0.8:
                total += weight / nx * y[target] / ny * score
        return total
    return min(1.0, (directed(a, b)+directed(b, a))/2)


if __name__ == '__main__':
    pairs = [('CA','AC'), ('CA','ABC'), ('kitten','sitting'), ('lewenstein','levenshtein'),
             ('ab','ba'), ('abc','axc'), ('aaaa','aaa'), ('aaab','aabb'), ('a','ab'),
             ('red shoe','shoe red'), ('fuzzy was a bear','fuzzy fuzzy was a bear'),
             ('ab','ac'), ('abc','xyz'), ('東京','京東'), ('éa','aé'), ('😀ab','a😀b'),
             ('e\u0301','é'), ('^a$','a'), ('["a"]','a'), ('short:a','a'),
             ('',''), ('','a'), ('a',''), (None,'a'), ('a',None), (None,None)]
    rows = []
    for a,b in pairs:
        if not a or not b:
            scores = {k:-1.0 for k in ('osa','lcs_indel','token_sort_lev','padded_bigram_dice','qgram_count_cosine')}
        else:
            scores = {'osa': OSA.normalized_similarity(a,b), 'lcs_indel': Indel.normalized_similarity(a,b),
                      'token_sort_lev': Levenshtein.normalized_similarity(' '.join(sorted(a.split())), ' '.join(sorted(b.split())))}
            x,y = vectors(grams(a,True),grams(b,True))
            scores['padded_bigram_dice'] = 1.0-float(braycurtis(x,y))
            x,y = vectors(grams(a,False),grams(b,False))
            scores['qgram_count_cosine'] = 1.0-float(cosine(x,y))
        rows.append({'a':a,'b':b,**scores})
    strings = [''.join(p) for n in range(1,4) for p in itertools.product('ab',repeat=n)]
    exhaustive = [[a,b,OSA.normalized_similarity(a,b),Indel.normalized_similarity(a,b)] for a in strings for b in strings]
    weighted = [({'rare':3.,'common':1.},{'rare':3.}), ({'x':1.},{'y':2.}),
                ({'a':1.,'b':2.},{'a':1.,'b':2.}), ({},{'a':1.}), ({},{}), (None,{'a':1.})]
    wrows = []
    for a,b in weighted:
        if not a or not b:
            score = -1.0
        else:
            keys = list(dict.fromkeys([*a,*b]))
            score = 1.0-float(jaccard([k in a for k in keys],[k in b for k in keys],w=[a.get(k,b.get(k)) for k in keys]))
        wrows.append({'a':a,'b':b,'score':score})
    soft_pairs = [({'abcde':1.},{'abcdef':1.}), ({'cat':1.},{'cats':1.}),
                  ({'aaaaa':1.},{'aaaab':1.}), ({'aaaaaa':1.},{'baaaaa':1.,'caaaaa':3.}),
                  ({'aaaaaa':1.,'aaaaab':1.},{'aaaaaa':1.}),
                  ({'red':1.,'shoe':3.},{'red':1.,'shoe':3.}),
                  ({'shoe':3.,'red':1.},{'red':1.,'shoe':3.}), ({},{'a':1.}), ({},{}), (None,{'a':1.})]
    data = {'provenance': {
        'rapidfuzz':rapidfuzz.__version__, 'scipy':scipy.__version__,
        'osa':'RapidFuzz OSA.normalized_similarity; CA/AC distance is 1 (runtime), contrary to one docs example.',
        'lcs_indel':'RapidFuzz Indel.normalized_similarity',
        'token_sort_lev':'RapidFuzz Levenshtein.normalized_similarity on sorted duplicate-preserving tokens',
        'padded_bigram_dice':'1 - scipy.spatial.distance.braycurtis on padded multiset counts',
        'qgram_count_cosine':'1 - scipy.spatial.distance.cosine on trigram counts',
        'weighted_jaccard':'1 - scipy.spatial.distance.jaccard with Boolean vectors and common positive weights',
        'soft_tfidf_lev':'Independent composition: RapidFuzz normalized Levenshtein + math.hypot; declared strict threshold, lexical ties, symmetrization and clipping',
        'missing':'Project contract overrides mathematical empty-input values to -1',
        'sources': ['https://rapidfuzz.github.io/RapidFuzz/Usage/distance/OSA.html',
                    'https://rapidfuzz.github.io/RapidFuzz/Usage/distance/Indel.html',
                    'https://rapidfuzz.github.io/RapidFuzz/Usage/distance/Levenshtein.html',
                    'https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.braycurtis.html',
                    'https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.cosine.html',
                    'https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.jaccard.html']},
        'strings': rows, 'exhaustive_binary_dp':exhaustive, 'weighted_jaccard':wrows,
        'soft_tfidf_lev':[{'a':a,'b':b,'score':soft(a,b)} for a,b in soft_pairs]}
    target=Path(__file__).parent/'fixtures'/'sota_reference.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(f'{len(rows)} string cases, {len(exhaustive)} exhaustive DP pairs, {len(wrows)} weighted, {len(soft_pairs)} soft; {target}')
