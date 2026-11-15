import pytest
from conftest import payload


@pytest.mark.parametrize('method,path', [('get','/slots'),('post','/reset'),('post','/bookings'),('get','/bookings'),('get','/bookings/x'),('delete','/bookings/x')])
def test_authentication(app, method, path):
    with app.test_client() as c:
        assert getattr(c, method)(path).status_code == 401
        assert getattr(c, method)(path, headers={'X-API-Key':'wrong'}).status_code == 401


@pytest.mark.parametrize('body', [{}, {'slot_id':'s1','name':'Ada'}, {'slot_id':'s1','name':' ','email':'ada@example.com'}, {'slot_id':'s1','name':'Ada','email':'bad'}, {'slot_id':42,'name':'Ada','email':'a@example.com'}, []])
def test_validation(seeded, body):
    result = seeded.post('/bookings', json=body)
    assert result.status_code == 400
    assert set(result.json) == {'error'}


def test_normalization_missing_and_past(seeded):
    assert seeded.post('/bookings', json=payload('missing')).status_code == 404
    assert seeded.post('/bookings', json=payload('past')).status_code == 400
    body = payload(email=' ADA@EXAMPLE.COM ')
    body['name'] = ' Ada Obi '
    booking = seeded.post('/bookings', json=body).json
    assert booking['email'] == 'ada@example.com'
    assert booking['name'] == 'Ada Obi'


def test_bad_reset_is_atomic(seeded):
    assert seeded.post('/reset', json={'slots':[{'id':'oops'}]}).status_code == 400
    assert len(seeded.get('/slots').json['slots']) == 21
