import subprocess
import sys

import pytest

from lakematch.publication import current, publish, request_digest


def test_atomic_retry_recovery_and_historical_batch_does_not_rewind(tmp_path):
    inputs = tmp_path / 'input.json'
    inputs.write_text('{"name": "synthetic"}\n')
    digest = request_digest({'records': inputs}, {'model': 'runs:/fixture/model'})
    root = tmp_path / 'published'
    assert current(root) is None and not root.exists()
    def first(path, previous):
        assert previous is None
        (path / 'crosswalk.json').write_text('["a"]')
        (path / 'events.json').write_text('["created"]')
        return {'records': 1}
    original = publish(root, 'first', digest, first)
    def interrupted(path, previous):
        assert previous['batch_id'] == 'first'
        (path / 'crosswalk.json').write_text('["a", "b"]')
        assert current(root)['batch_id'] == 'first'
        raise RuntimeError('interrupted before events and commit')
    with pytest.raises(RuntimeError, match='interrupted'):
        publish(root, 'second', digest, interrupted)
    assert current(root)['batch_id'] == 'first'
    def second(path, previous):
        assert previous['batch_id'] == 'first'
        (path / 'crosswalk.json').write_text('["a", "b"]')
        (path / 'events.json').write_text('["added"]')
        return {'records': 2}
    result = publish(root, 'second', digest, second)
    assert len(result['recovered_attempts']) == 1
    assert current(root)['batch_id'] == 'second'
    def never(*args):
        pytest.fail('A committed retry must not rerun the job or append events')
    assert publish(root, 'second', digest, never)['reused']
    assert publish(root, 'first', digest, never)['root'] == original['root']
    assert current(root)['batch_id'] == 'second'
    with pytest.raises(ValueError, match='different inputs'):
        publish(root, 'second', '0' * 64, never)
    assert len(list((root / 'attempts').iterdir())) == 2
    (root / 'attempts' / result['attempt'] / 'events.json').write_text('[]')
    with pytest.raises(ValueError, match='Published files changed'):
        current(root)


def test_input_bytes_and_contract_both_protect_batch_reuse(tmp_path):
    path = tmp_path / 'records'
    path.mkdir()
    (path / 'part.csv').write_text('a,synthetic\n')
    first = request_digest({'records': path}, {'model': 'one'})
    assert first == request_digest({'records': path}, {'model': 'one'})
    assert first != request_digest({'records': path}, {'model': 'two'})
    (path / 'part.csv').write_text('b,synthetic\n')
    assert first != request_digest({'records': path}, {'model': 'one'})


def test_process_death_before_commit_keeps_prior_snapshot(tmp_path):
    root = tmp_path / 'published'
    def write(path, previous):
        (path / 'crosswalk').write_text('complete')
        return {'records': 1}
    publish(root, 'original', '1' * 64, write)
    child = subprocess.run([sys.executable, '-c', '''
import os, sys
from lakematch.publication import publish
def interrupted(path, previous):
    (path / 'crosswalk').write_text('partial')
    os._exit(73)
publish(sys.argv[1], 'next', '2' * 64, interrupted)
''', str(root)], timeout=20)
    assert child.returncode == 73
    assert current(root)['batch_id'] == 'original'
    recovered = publish(root, 'next', '2' * 64, write)
    assert len(recovered['recovered_attempts']) == 1
    assert current(root)['batch_id'] == 'next'
