import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app


@pytest.fixture
def app(tmp_path):
    return create_app(os.environ.get('TEST_DATABASE_URL') or 'sqlite:///' + str(tmp_path / 'test.db'), 'test-key', 'test-secret')


@pytest.fixture
def client(app):
    client = app.test_client()
    client.environ_base['HTTP_X_API_KEY'] = 'test-key'
    return client


@pytest.fixture
def seeded(client):
    slots = [dict(id=f's{i}', provider='Dr Ade' if i % 2 else 'Dr Obi', start=f'2099-12-{i:02}T09:00:00Z', end=f'2099-12-{i:02}T09:30:00Z') for i in range(1, 21)]
    slots.append(dict(id='past', provider='Dr Ade', start='2000-01-01T09:00:00Z', end='2000-01-01T09:30:00Z'))
    assert client.post('/reset', json={'slots': slots}).status_code == 200
    return client


def payload(slot='s1', email='ada@example.com'):
    return dict(slot_id=slot, name='Ada Obi', email=email)
