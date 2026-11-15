"""Explicit demo reset. Never run this after submitting the assessment."""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
base = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else 'http://127.0.0.1:5000'
start = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0)
slots = []
for day in range(7):
    for doctor, offset in [('Dr Ade', 0), ('Dr Obi', 1)]:
        for hour in range(3):
            at = start + timedelta(days=day, hours=hour, minutes=offset * 30)
            slots.append(dict(id=f'd{day}-{offset}-{hour}', provider=doctor, start=at.isoformat(), end=(at+timedelta(minutes=30)).isoformat()))
if base == '--database':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import app
    with app.test_client() as client:
        response = client.post('/reset', json={'slots':slots}, headers={'X-API-Key':os.environ['API_KEY']})
        assert response.status_code == 200, response.json
        print(f'Seeded {len(slots)} demo slots directly in the configured database.')
else:
    req = urllib.request.Request(base + '/reset', data=json.dumps({'slots':slots}).encode(), headers={'Content-Type':'application/json', 'X-API-Key':os.environ['API_KEY']}, method='POST')
    with urllib.request.urlopen(req, timeout=60) as response:
        print(f'Seeded {len(slots)} demo slots. HTTP {response.status}')
