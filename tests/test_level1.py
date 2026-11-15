from conftest import payload


def test_list_book_lookup_and_persistence(seeded, app):
    slots = seeded.get('/slots').json['slots']
    assert slots[0]['id'] == 'past'
    assert all(s['available'] for s in slots)
    assert all(s['provider'] == 'Dr Ade' for s in seeded.get('/slots?provider=Dr+Ade').json['slots'])
    response = seeded.post('/bookings', json=payload())
    assert response.status_code == 201
    booking = response.json
    assert booking['status'] == 'confirmed'
    with app.test_client() as another:
        assert another.get('/bookings/' + booking['id'], headers={'X-API-Key': 'test-key'}).json == booking
    assert not next(s for s in seeded.get('/slots').json['slots'] if s['id'] == 's1')['available']
    assert seeded.get('/bookings/missing').status_code == 404


def test_reset_removes_bookings(seeded):
    booking = seeded.post('/bookings', json=payload()).json
    assert seeded.post('/reset', json={'slots': []}).status_code == 200
    assert seeded.get('/slots').json == {'slots': []}
    assert seeded.get('/bookings/' + booking['id']).status_code == 404
