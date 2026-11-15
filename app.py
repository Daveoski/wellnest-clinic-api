"""Clinic assessment API. All durable state lives in the configured database."""
import base64
import hashlib
import hmac
import json
import math
import os
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from werkzeug.exceptions import HTTPException

load_dotenv()


def create_app(database_url=None, api_key=None, cursor_secret=None):
    app = Flask(__name__, static_folder='static')
    app.config['MAX_CONTENT_LENGTH'] = 64 * 1024
    key = api_key or os.environ.get('API_KEY')
    if not key:
        raise RuntimeError('Set API_KEY before starting the application')
    url = database_url or os.environ.get('DATABASE_URL')
    if not url:
        raise RuntimeError('Set DATABASE_URL; use SQLite only for local development')
    if url.startswith(('postgres://', 'postgresql://')):
        url = 'postgresql+psycopg://' + url.split('://', 1)[1]
    engine = create_engine(url, poolclass=NullPool, connect_args={'timeout': 30} if url.startswith('sqlite') else {})
    secret = (cursor_secret or os.environ.get('CURSOR_SECRET') or key).encode()
    postgres = engine.dialect.name == 'postgresql'

    @contextmanager
    def transaction():
        # Shared database lock also coordinates reset with in-flight writes.
        # SQLite's write transaction provides the same local-test guarantee.
        with engine.connect() as conn:
            try:
                if postgres:
                    conn.execute(text('SELECT pg_advisory_xact_lock(73190421)'))
                else:
                    conn.exec_driver_sql('BEGIN IMMEDIATE')
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    with transaction() as conn:
        for statement in [
            'CREATE TABLE IF NOT EXISTS slots (id TEXT PRIMARY KEY, provider TEXT NOT NULL, start TEXT NOT NULL, "end" TEXT NOT NULL)',
            "CREATE TABLE IF NOT EXISTS bookings (id TEXT PRIMARY KEY, slot_id TEXT NOT NULL REFERENCES slots(id), name TEXT NOT NULL, email TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('confirmed','cancelled')), created_at TEXT NOT NULL)",
            "CREATE UNIQUE INDEX IF NOT EXISTS one_confirmed_booking ON bookings(slot_id) WHERE status='confirmed'",
            'CREATE INDEX IF NOT EXISTS booking_pages ON bookings(email,created_at,id)',
            'CREATE TABLE IF NOT EXISTS idempotency (key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, status INTEGER NOT NULL, body TEXT NOT NULL)',
            'CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, email TEXT NOT NULL, attempted_at DOUBLE PRECISION NOT NULL)',
            'CREATE INDEX IF NOT EXISTS attempt_window ON attempts(email,attempted_at)',
        ]:
            conn.execute(text(statement))
    app.extensions['db_engine'] = engine

    def error(message, status):
        return jsonify(error=message), status

    @app.before_request
    def authenticate():
        if request.path == '/' or request.path.startswith('/static/'):
            return
        if not hmac.compare_digest(request.headers.get('X-API-Key', ''), key):
            return error('invalid API key', 401)

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        return response

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return error(exc.description, exc.code)

    @app.errorhandler(Exception)
    def unexpected_error(exc):
        app.logger.exception('Request failed')
        return error('internal server error', 500)

    def now():
        return datetime.now(timezone.utc)

    def timestamp(value):
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('timezone required')
        return parsed.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')

    def rows(conn, sql, params=None):
        return [dict(row) for row in conn.execute(text(sql), params or {}).mappings()]

    @app.get('/')
    def homepage():
        return send_from_directory('static', 'index.html')

    @app.post('/reset')
    def reset():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get('slots'), list):
            return error('slots must be an array', 400)
        slots = []
        try:
            for slot in body['slots']:
                if not isinstance(slot, dict) or any(not isinstance(slot.get(k), str) or not slot[k].strip() for k in ('id', 'provider', 'start', 'end')):
                    raise ValueError()
                item = {k: slot[k] for k in ('id', 'provider', 'start', 'end')}
                item['start'], item['end'] = timestamp(item['start']), timestamp(item['end'])
                if item['end'] <= item['start']:
                    raise ValueError()
                slots.append(item)
            if len({s['id'] for s in slots}) != len(slots):
                raise ValueError()
        except (ValueError, TypeError):
            return error('invalid slots', 400)
        with transaction() as conn:
            for table in ('idempotency', 'attempts', 'bookings', 'slots'):
                conn.execute(text(f'DELETE FROM {table}'))
            for slot in slots:
                conn.execute(text('INSERT INTO slots(id,provider,start,"end") VALUES (:id,:provider,:start,:end)'), slot)
        return jsonify(ok=True)

    @app.get('/slots')
    def slots():
        sql = "SELECT s.*, NOT EXISTS(SELECT 1 FROM bookings b WHERE b.slot_id=s.id AND b.status='confirmed') AS available FROM slots s"
        params = {}
        if 'provider' in request.args:
            sql += ' WHERE s.provider=:provider'
            params['provider'] = request.args['provider']
        with engine.connect() as conn:
            result = rows(conn, sql + ' ORDER BY s.start,s.id', params)
        for slot in result:
            slot['available'] = bool(slot['available'])
        return jsonify(slots=result)

    @app.post('/bookings')
    def book():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return error('a JSON object is required', 400)
        email = body.get('email', '')
        email = email.strip().lower() if isinstance(email, str) else ''
        fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        idem = request.headers.get('Idempotency-Key')
        with transaction() as conn:
            current = now().timestamp()
            conn.execute(text('DELETE FROM attempts WHERE attempted_at <= :cutoff'), {'cutoff': current - 60})
            if email:
                recent = rows(conn, 'SELECT attempted_at FROM attempts WHERE email=:email ORDER BY attempted_at', {'email': email})
                if len(recent) >= 5:
                    response = jsonify(error='too many booking attempts')
                    response.status_code = 429
                    response.headers['Retry-After'] = str(max(1, math.ceil(recent[0]['attempted_at'] + 60 - current)))
                    return response
                conn.execute(text('INSERT INTO attempts VALUES (:id,:email,:time)'), {'id': str(uuid.uuid4()), 'email': email, 'time': current})
            if idem:
                cached = rows(conn, 'SELECT * FROM idempotency WHERE key=:key', {'key': idem})
                if cached:
                    if cached[0]['fingerprint'] != fingerprint:
                        return error('idempotency key reused with different body', 422)
                    return jsonify(json.loads(cached[0]['body'])), cached[0]['status']

            def finish(payload, status):
                if idem:
                    conn.execute(text('INSERT INTO idempotency VALUES (:key,:fingerprint,:status,:body)'), {'key': idem, 'fingerprint': fingerprint, 'status': status, 'body': json.dumps(payload)})
                return jsonify(payload), status

            if any(not isinstance(body.get(k), str) or not body[k].strip() for k in ('slot_id', 'name', 'email')):
                return finish({'error': 'slot_id, name and email are required'}, 400)
            if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+', email):
                return finish({'error': 'invalid email'}, 400)
            slot = rows(conn, 'SELECT * FROM slots WHERE id=:id', {'id': body['slot_id']})
            if not slot:
                return finish({'error': 'slot not found'}, 404)
            if slot[0]['start'] <= now().isoformat(timespec='microseconds').replace('+00:00', 'Z'):
                return finish({'error': 'slot has already started'}, 400)
            if rows(conn, "SELECT id FROM bookings WHERE slot_id=:id AND status='confirmed'", {'id': body['slot_id']}):
                return finish({'error': 'slot already booked'}, 409)
            booking = dict(id=str(uuid.uuid4()), slot_id=body['slot_id'], name=body['name'].strip(), email=email, status='confirmed', created_at=now().isoformat(timespec='microseconds').replace('+00:00', 'Z'))
            conn.execute(text('INSERT INTO bookings VALUES (:id,:slot_id,:name,:email,:status,:created_at)'), booking)
            return finish(booking, 201)

    @app.get('/bookings/<booking_id>')
    def lookup(booking_id):
        with engine.connect() as conn:
            found = rows(conn, 'SELECT * FROM bookings WHERE id=:id', {'id': booking_id})
        return jsonify(found[0]) if found else error('booking not found', 404)

    @app.delete('/bookings/<booking_id>')
    def cancel(booking_id):
        with transaction() as conn:
            found = rows(conn, 'SELECT * FROM bookings WHERE id=:id', {'id': booking_id})
            if not found:
                return error('booking not found', 404)
            if found[0]['status'] == 'cancelled':
                return error('booking already cancelled', 409)
            conn.execute(text("UPDATE bookings SET status='cancelled' WHERE id=:id"), {'id': booking_id})
            found[0]['status'] = 'cancelled'
        return jsonify(found[0])

    @app.get('/bookings')
    def history():
        email = request.args.get('email', '').strip().lower()
        try:
            limit = int(request.args.get('limit', '10'))
            if not email or not 1 <= limit <= 50:
                raise ValueError()
            params = {'email': email, 'limit': limit + 1}
            sql = 'SELECT * FROM bookings WHERE email=:email'
            if 'cursor' in request.args:
                token, signature = request.args['cursor'].split('.')
                expected = hmac.new(secret, token.encode(), hashlib.sha256).hexdigest()
                if not hmac.compare_digest(signature, expected):
                    raise ValueError()
                data = json.loads(base64.urlsafe_b64decode(token + '=' * (-len(token) % 4)))
                if data['email'] != email:
                    raise ValueError()
                params.update(created=data['created'], id=data['id'])
                sql += ' AND (created_at > :created OR (created_at=:created AND id>:id))'
        except (ValueError, KeyError, TypeError):
            return error('invalid email, limit or cursor', 400)
        with engine.connect() as conn:
            result = rows(conn, sql + ' ORDER BY created_at,id LIMIT :limit', params)
        cursor = None
        if len(result) > limit:
            last = result[limit - 1]
            token = base64.urlsafe_b64encode(json.dumps(dict(email=email, created=last['created_at'], id=last['id'])).encode()).decode().rstrip('=')
            cursor = token + '.' + hmac.new(secret, token.encode(), hashlib.sha256).hexdigest()
        return jsonify(bookings=result[:limit], next_cursor=cursor)

    return app


if os.environ.get('API_KEY') and os.environ.get('DATABASE_URL'):
    app = create_app()

if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5000)
