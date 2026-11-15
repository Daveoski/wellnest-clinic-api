from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from conftest import payload


def test_simultaneous_booking(seeded, app):
    barrier = Barrier(12)
    def attempt(i):
        with app.test_client() as c:
            barrier.wait()
            return c.post('/bookings', json=payload(email=f'person{i}@example.com'), headers={'X-API-Key':'test-key'}).status_code
    with ThreadPoolExecutor(max_workers=12) as pool:
        statuses = list(pool.map(attempt, range(12)))
    assert statuses.count(201) == 1
    assert statuses.count(409) == 11


def test_cancel_frees_slot(seeded):
    booking = seeded.post('/bookings', json=payload()).json
    path = '/bookings/' + booking['id']
    assert seeded.delete(path).json['status'] == 'cancelled'
    assert seeded.get(path).json['status'] == 'cancelled'
    assert seeded.delete(path).status_code == 409
    assert seeded.post('/bookings', json=payload()).status_code == 201
    assert seeded.delete('/bookings/missing').status_code == 404
