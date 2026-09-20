import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from report_compatibility import compare_scores


def test_replay_allows_order_and_roundoff_without_changed_links():
    before = [('a', 'b', .9), ('a', 'c', .2)]
    after = [('a', 'c', .2), ('a', 'b', .9 + 1e-14)]
    assert compare_scores(before, after, .5, 'one_to_one') < 1e-12


@pytest.mark.parametrize('after,reason', [
    ([('a', 'c', .9)], 'Candidate pair identities'),
    ([('a', 'b', .9), ('a', 'b', .9)], 'Duplicate'),
    ([('a', 'b', float('nan'))], 'Nonfinite'),
    ([('a', 'b', .89)], 'delta'),
])
def test_replay_rejects_changed_or_invalid_scores(after, reason):
    with pytest.raises(AssertionError, match=reason):
        compare_scores([('a', 'b', .9)], after, .5, 'one_to_one')


def test_replay_rejects_threshold_crossing_even_within_numeric_tolerance():
    with pytest.raises(AssertionError, match='Link decisions'):
        compare_scores([('a', 'b', .5 - 1e-14)], [('a', 'b', .5 + 1e-14)], .5, 'one_to_one')
