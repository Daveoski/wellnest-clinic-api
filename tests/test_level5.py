from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from sqlalchemy import text
from conftest import payload


def test_failed_attempts_normalization_isolation_and_expiry(seeded, app):
    for _ in range(5):
        assert seeded.post('/bookings', json=payload('absent', ' ADA@EXAMPLE.COM ')).status_code == 404
    response = seeded.post('/bookings', json=payload())
    assert response.status_code == 429
    assert 1 <= int(response.headers['Retry-After']) <= 60
    assert seeded.post('/bookings', json=payload(email='other@example.com')).status_code == 201
    with app.extensions['db_engine'].begin() as conn:
        conn.execute(text('UPDATE attempts SET attempted_at=attempted_at-61'))
    assert seeded.post('/bookings', json=payload('s2')).status_code == 201


def test_simultaneous_rate_limit(seeded, app):
    barrier = Barrier(10)
    def attempt(_):
        with app.test_client() as c:
            barrier.wait()
            return c.post('/bookings', json=payload('absent'), headers={'X-API-Key':'test-key'}).status_code
    with ThreadPoolExecutor(max_workers=10) as pool:
        codes = list(pool.map(attempt, range(10)))
    assert codes.count(404) == 5
    assert codes.count(429) == 5
