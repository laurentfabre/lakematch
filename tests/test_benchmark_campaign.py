import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from benchmark_campaign import scale_retry_blocker


def test_failed_million_tier_blocks_automatic_repeat_with_original_evidence(tmp_path):
    ledger = tmp_path / 'runs.jsonl'
    events = [
        {'kind': 'scale-1000000', 'status': 'failed', 'run_id': 'failed-million', 'manifest': 'retained.json'},
        {'kind': 'scale-100000', 'status': 'passed', 'run_id': 'later-small', 'manifest': 'small.json'},
    ]
    ledger.write_text('\n'.join(map(json.dumps, events)))
    blocked = scale_retry_blocker(ledger)
    assert blocked['retained_run_id'] == 'failed-million'
    assert blocked['manifest'] == 'retained.json'


def test_new_campaign_does_not_invent_a_scale_failure(tmp_path):
    ledger = tmp_path / 'runs.jsonl'
    ledger.write_text('')
    assert scale_retry_blocker(ledger) is None
