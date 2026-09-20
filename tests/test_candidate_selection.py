import sys
from pathlib import Path


def test_macro_never_drops_a_corpus_to_rank_an_unavailable_method():
    sys.path.insert(0, str(Path('tools').resolve()))
    from report_candidate_pairs import macro
    comparisons = {}
    corpora = ['febrl4_half_all', 'febrl4_half_no_ssn', 'bpid', 'abt_buy',
               'amazon_google', 'walmart_amazon', 'dblp_acm', 'affiliations']
    for corpus in corpora:
        best = {'field_blocks': ({'f1': .8, 'method_seconds_including_log_cleanup': 2.}, {'a': [4, 1, 1, 0]})}
        if corpus != 'bpid':
            best['gram_topk'] = ({'f1': 1., 'method_seconds_including_log_cleanup': 1.}, {'a': [5, 0, 0, 1]})
        comparisons[corpus] = ({}, best, {})
    result = macro(comparisons)
    assert set(result) == {'field_blocks'}
    assert abs(result['field_blocks']['macro_f1'] - .8) < 1e-12
    assert result['field_blocks']['paired_deltas']['field_blocks'] == [0., 0.]
