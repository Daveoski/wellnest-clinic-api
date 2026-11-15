# Wellnest Clinic booking API

Python Flask API and a responsive, accessible booking page, built to the exact [Koya assessment contract](https://koyaacademy.com/assessment-api). The downloaded contract is tracked in `assessment-openapi.json`.

Deployment: https://wellnest-clinic-api.vercel.app (page and API base URL). Public assessor access is enabled with the owner's explicit approval. API endpoints require the separately supplied API key. See `VALIDATION.md` for results and `artifacts/` for desktop and mobile screenshots.

## Run locally

Requires Python 3.12 or later. Install `requirements-dev.txt`, copy `.env.example` to `.env`, and set `API_KEY`, `CURSOR_SECRET` and `DATABASE_URL`. Use a Neon PostgreSQL URL for deployment; for local development only, `sqlite:///clinic.db` works.

```powershell
python -m pip install -r requirements-dev.txt
python app.py
```

Open http://127.0.0.1:5000 and enter your API key. The key stays in browser memory and is sent in `X-API-Key` on each API request. It is never embedded in public JavaScript or stored in browser storage. Refreshing the page requires entering it again.

The application starts with no slots. Before submission, seed demo data in another terminal:

```powershell
python scripts/seed.py
```

**The seed and test scripts erase bookings. Do not run them against the submitted service after submission.** `/reset` exists because the assessment requires it and is protected by the same API key.

## API

Every API request requires `X-API-Key`. All errors use `{"error":"message"}`. The public page and its static files do not require a key.

| Method | Path | Behavior |
|---|---|---|
| POST | `/reset` | Atomically replace slots and delete bookings, retry records and attempt history; accepts past slots |
| GET | `/slots?provider=Dr%20Ade` | All slots, sorted by start, optional exact provider match, availability included |
| POST | `/bookings` | Accept `{slot_id,name,email}`, return confirmed booking and 201 |
| GET | `/bookings/{id}` | Booking or 404 |
| DELETE | `/bookings/{id}` | Cancel and free slot; repeat cancellation returns 409 |
| GET | `/bookings?email=ada@example.com&limit=10&cursor=...` | Oldest first, case-insensitive email; `next_cursor` is null on last page |

Bookings reject missing/empty fields, invalid email and started slots with 400; unknown slots with 404; already booked slots with 409. Names and emails are trimmed; emails are lowercased. Timestamps are normalized to UTC.

Send optional `Idempotency-Key` for retries. The same key and JSON body reproduce the original response status and booking ID. A different body with that key returns 422. JSON property order is ignored, while actual field values, including whitespace and case, are part of the body fingerprint. Cancelled bookings do not rewrite the original cached booking response.

At most five booking attempts per normalized email are allowed in a rolling 60-second window. Failed attempts and retries count too. Further requests return 429 and integer `Retry-After`. Rate limiting happens before idempotency lookup, so a retry beyond the allowed attempts gets 429 until the window clears. Rate-limit responses themselves are not cached. Requests with no usable string email cannot be attributed to an email; invalid API-key requests are rejected before counting.

## How the five levels work

1. **Persistence:** slots and bookings live in database tables, never an in-memory list. Reads on another request or another serverless instance see committed data.
2. **Authentication and validation:** `before_request` checks the header with a constant-time comparison. Routes validate JSON themselves so invalid requests return the specified 400 and error shape.
3. **Concurrency and cancellation:** PostgreSQL transaction advisory lock `73190421` serializes mutations across connections and serverless instances. A partial unique index on `bookings(slot_id) WHERE status='confirmed'` independently prevents two active bookings. Cancellation changes status inside the transaction; the index then allows a new booking. SQLite uses `BEGIN IMMEDIATE` for local tests.
4. **Retries and pagination:** the retry key, SHA-256 JSON fingerprint, original status and response are saved in the same transaction as the booking. A crash rolls everything back. Pages use a `(created_at,id)` continuation rather than offsets, so equal timestamps have a stable order. HMAC-signed cursors are tied to the requested email.
5. **Spam prevention:** attempts are stored in PostgreSQL. Counting and recording attempts happen under the same transaction lock, so separate instances cannot bypass the five-attempt limit. An index supports per-email window checks; expired attempt records are removed.

The single mutation lock deliberately favors simple, auditable correctness for a small assessment service. It serializes all emails and is a throughput bottleneck at larger scale. A larger clinic could move to per-email and per-slot locks with a carefully ordered reset strategy. API-key access follows the assessment contract; it is shared access and does not provide individual patient authorization.

## Tests

Run the levels in order; each must pass before the next:

```powershell
python -m pytest tests/test_level1.py -q --basetemp=.test-tmp-1
python -m pytest tests/test_level2.py -q --basetemp=.test-tmp-2
python -m pytest tests/test_level3.py -q --basetemp=.test-tmp-3
python -m pytest tests/test_level4.py -q --basetemp=.test-tmp-4
python -m pytest tests/test_level5.py -q --basetemp=.test-tmp-5
```

Default tests use temporary SQLite files. `python scripts/test_postgres.py` runs the same gates against `DATABASE_URL`, including simultaneous booking, retry and rate-limit tests. It is destructive and intended only before submission or against a separate test database.

## Deployment

The root `app.py` is the Flask entry point. `.python-version` selects Python 3.12. `vercel.json` selects Flask. Set production `DATABASE_URL` to the Neon connection string (SSL required), and set private `API_KEY` and `CURSOR_SECRET`. `NullPool` avoids retaining process-local connection pools on serverless instances; Neon provides the managed database.

```powershell
vercel link
vercel --prod
```

Schema creation is idempotent and coordinated by the database lock. No production SQLite fallback is configured. Both the page and API share one HTTPS origin, avoiding cross-origin setup. Deployment protection must allow public access for assessment checks; API routes still require the key.

See `WALKTHROUGH.md` for a short explanation and recording outline. After submitting, retain the deployment and database, and do not seed, reset, test against, redeploy or otherwise modify them until contacted.
