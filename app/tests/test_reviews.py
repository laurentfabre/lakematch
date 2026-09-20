from concurrent.futures import ThreadPoolExecutor
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from lakematch_review.backend.app import app
from lakematch_review.backend.store import SQLiteStore, pair_key
from lakematch_review.backend.models import PairOut, ReviewIn


def seed(path, n=24):
    store = SQLiteStore(path)
    for i in range(n):
        pair = PairOut(pair_id=pair_key('runs:/fixture/model', f'a{i}', f'b{i}'), a_id=f'a{i}', b_id=f'b{i}',
                       left={'name': f'Alice {i}'}, right={'name': f'Alice {i}'},
                       model_version='runs:/fixture/model', probability=.5 + i/100, threshold=.5, impact=2+i)
        store.enqueue(pair)
    store.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = str(tmp_path/'reviews.sqlite')
    monkeypatch.setenv('LAKEMATCH_REVIEW_DATABASE', path)
    monkeypatch.setenv('LAKEMATCH_REVIEW_STORE', 'sqlite')
    monkeypatch.delenv('DATABRICKS_APP_NAME', raising=False)
    seed(path)
    with TestClient(app) as client:
        yield client, path


def review_body(pair, decision='match'):
    return {'request_id':uuid4().hex, 'pair_id':pair['pair_id'], 'model_version':pair['model_version'],
            'decision':decision, 'reason':'Synthetic review: names agree.'}


def test_http_twenty_reviews_restart_snapshot_and_provenance(client):
    c, path = client
    queue = c.get('/api/queue?limit=24').json()
    assert [p['a_id'] for p in queue] == [f'a{i}' for i in range(24)]
    saved = []
    for i, pair in enumerate(queue[:20]):
        body = review_body(pair, ['match','no_match','unsure'][i%3])
        response = c.post('/api/reviews', json=body)
        assert response.status_code == 200, response.text
        row = response.json(); saved.append(row)
        assert row['user'] == 'local-reviewer' and row['reviewed_at'] and row['reason'] == body['reason']
        assert c.post('/api/reviews', json=body).json() == row
    assert len(c.get('/api/reviews').json()) == 20
    with TestClient(app) as fresh:
        assert fresh.get('/api/statistics').json()['queue_depth'] == 4
        assert fresh.get('/api/reviews').json() == saved
        snap = fresh.get('/api/training-labels').json()
        assert len(snap['labels']) == 14 and snap['excluded_unsure'] == 6
        assert snap['label_set_sha256']
        stats = fresh.get('/api/statistics').json()
        assert stats['llm_agreement'] is None and stats['quarantine'] is None and stats['evaluations'] == []
        assert fresh.get('/api/session').json()['genie_enabled'] is False


def test_reject_forged_invalid_and_stale_reviews(client):
    c, _ = client
    pair = c.get('/api/queue').json()[0]
    body = review_body(pair)
    for patch in ({'reason':' '}, {'decision':'yes'}, {'user':'someone-else'}, {'reviewed_at':'yesterday'}):
        assert c.post('/api/reviews', json={**body, **patch}).status_code == 422
    assert c.post('/api/reviews', json={**body, 'pair_id':'f'*64}).status_code == 404
    assert c.post('/api/reviews', json={**body, 'model_version':'stale'}).status_code == 409
    assert c.post('/api/reviews', json=body).status_code == 200
    assert c.post('/api/reviews', json={**body,'reason':'changed'}).status_code == 409
    assert c.post('/api/reviews', json={**body,'request_id':uuid4().hex}).status_code == 409
    assert len(c.get('/api/reviews').json()) == 1


def test_concurrent_retry_has_exactly_one_persistent_review(client):
    c, path = client
    body = ReviewIn(**review_body(c.get('/api/queue').json()[0]))
    def write(_):
        store = SQLiteStore(path)
        try: return store.review(body, 'reviewer').model_dump()
        finally: store.close()
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(write, range(8)))
    assert all(r == rows[0] for r in rows)
    assert len(c.get('/api/reviews').json()) == 1


def test_rank_llm_uncertainty_then_impact(client):
    _, path = client
    store = SQLiteStore(path)
    rows = store.query('SELECT pair_id FROM review_queue ORDER BY uncertainty LIMIT 2')
    for i, (key,) in enumerate(rows):
        store.query('UPDATE review_queue SET uncertainty=0, impact=:impact WHERE pair_id=:key', {'impact':10+i,'key':key})
    assert store.queue()[0].pair_id == rows[1][0]
    store.close()


def test_numeric_metadata_roundtrip(client):
    c, path = client
    store = SQLiteStore(path)
    store.query('INSERT INTO review_metadata VALUES (:key, :value)', {'key':'quarantine','value':json.dumps(0)})
    store.close()
    assert c.get('/api/statistics').json()['quarantine'] == 0


def test_llm_unsure_prioritizes_uncertainty_and_merge_impact(client):
    _, path = client
    store = SQLiteStore(path)
    pair = PairOut(pair_id=pair_key('runs:/fixture/model','llm-a','llm-b'), a_id='llm-a', b_id='llm-b',
                   left={'name':'Alice'}, right={'name':'Alicia'}, model_version='runs:/fixture/model',
                   probability=.99, threshold=.5, llm_decision='unsure', impact=30)
    store.enqueue(pair)
    store.enqueue(pair)
    assert store.queue()[0] == pair
    assert store.query('SELECT COUNT(*) FROM review_queue')[0][0] == 25
    store.close()


def test_local_delta_does_not_trust_forwarded_identity(monkeypatch):
    from fastapi import HTTPException
    from lakematch_review.backend.router import get_actor
    from lakematch_review.backend.core._config import AppConfig
    from lakematch_review.backend.core._headers import DatabricksAppsHeaders
    monkeypatch.delenv('DATABRICKS_APP_NAME', raising=False)
    config = AppConfig(store='delta', warehouse_id='fixture', schema_name='fixture.review')
    headers = DatabricksAppsHeaders(host=None, user_id='123', user_name='claimed-user',
                                    user_email=None, request_id=None, token=None)
    with pytest.raises(HTTPException) as error:
        get_actor(config, headers)
    assert error.value.status_code == 401


def test_deployed_app_refuses_ephemeral_sqlite(monkeypatch):
    from pydantic import ValidationError
    from lakematch_review.backend.core._config import AppConfig
    monkeypatch.setenv('DATABRICKS_APP_NAME', 'synthetic-test-app')
    with pytest.raises(ValidationError, match='durable Delta'):
        AppConfig(store='sqlite')
