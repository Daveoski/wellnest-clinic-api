from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from conftest import payload


def test_replay_and_mismatch(seeded):
    headers = {'Idempotency-Key':'one'}
    first = seeded.post('/bookings', json=payload(), headers=headers)
    repeat = seeded.post('/bookings', json=payload(), headers=headers)
    assert repeat.status_code == first.status_code == 201
    assert repeat.json == first.json
    assert seeded.post('/bookings', json=payload('s2'), headers=headers).status_code == 422
    assert len(seeded.get('/bookings?email=ada@example.com').json['bookings']) == 1


def test_simultaneous_retries(seeded, app):
    barrier = Barrier(5)
    def attempt(_):
        with app.test_client() as c:
            barrier.wait()
            r = c.post('/bookings', json=payload(), headers={'X-API-Key':'test-key','Idempotency-Key':'shared'})
            return r.status_code, r.json['id']
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(attempt, range(5)))
    assert len(set(results)) == 1
    assert results[0][0] == 201


def test_pages(seeded):
    for i in range(1, 6):
        assert seeded.post('/bookings', json=payload(f's{i}')).status_code == 201
    all_ids = []
    cursor = None
    for expected_count in [2, 2, 1]:
        query = dict(email='ADA@EXAMPLE.COM', limit=2)
        if cursor:
            query['cursor'] = cursor
        page = seeded.get('/bookings', query_string=query).json
        assert len(page['bookings']) == expected_count
        all_ids.extend(b['id'] for b in page['bookings'])
        cursor = page['next_cursor']
    assert cursor is None
    assert len(set(all_ids)) == 5
    for limit in ['0','51','abc','1.5']:
        assert seeded.get('/bookings', query_string={'email':'ada@example.com','limit':limit}).status_code == 400
    assert seeded.get('/bookings?email=ada@example.com&cursor=broken').status_code == 400


def test_failed_response_is_replayed(seeded):
    headers = {'Idempotency-Key':'failed'}
    a = seeded.post('/bookings', json=payload('absent'), headers=headers)
    b = seeded.post('/bookings', json=payload('absent'), headers=headers)
    assert a.status_code == b.status_code == 404
    assert a.json == b.json
