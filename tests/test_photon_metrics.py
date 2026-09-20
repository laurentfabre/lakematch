from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from report_photon import summarize


def query(ident, total, photon, task='12'):
    return {'query_id': ident, 'status': 'FINISHED',
            'query_source': {'job_info': {'job_task_run_id': task}},
            'metrics': {'task_total_time_ms': total, 'photon_total_time_ms': photon}}


def test_photon_share_weights_by_task_time_and_handles_zero_time():
    rows = [query('a', 100, 90), query('b', 900, 90), query('c', 0, 0, '13')]
    result = summarize(rows, {'12': 'pipeline', '13': 'audit'})
    assert result['pipeline']['photon_task_time_share'] == .18
    assert result['audit']['photon_task_time_share'] is None


@pytest.mark.parametrize('rows,reason', [
    ([query('a', 100, 90), query('a', 100, 90)], 'Duplicate'),
    ([query('a', 100, 90, 'unrelated')], 'not assigned'),
    ([query('a', 100, None)], 'Invalid'),
    ([query('a', 100, 101)], 'Invalid'),
])
def test_photon_evidence_rejects_double_counting_unowned_or_missing_metrics(rows, reason):
    with pytest.raises(AssertionError, match=reason):
        summarize(rows, {'12': 'pipeline'})
