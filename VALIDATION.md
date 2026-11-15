# Pre-submission validation

Verified 15 November 2026, before submission.

| Gate | SQLite | Neon PostgreSQL |
|---|---|---|
| Level 1: slots, booking, lookup, persistence and reset | 2 passed | 2 passed |
| Level 2: API key, invalid details, normalization and atomic reset validation | 14 passed | 14 passed |
| Level 3: simultaneous booking and cancellation | 2 passed | 2 passed |
| Level 4: retries, simultaneous retries, response replay and pagination | 4 passed | 4 passed |
| Level 5: failures counted, expiry, email isolation and simultaneous attempts | 2 passed | 2 passed |

Each gate ran after the previous gate passed. SQLite and PostgreSQL each passed 24 tests. Concurrent tests synchronize workers with a barrier: 12 compete for one slot, 5 replay one retry key, and 10 attempt to exceed one email's allowance.

The first PostgreSQL run emitted warnings because pytest could not write its local cache directory under the Windows permission boundary. All tests passed; subsequent commands disable the optional cache provider.

`node --check static/app.js` passed. Vercel built the Flask application with Python 3.12. An authenticated HTTPS check confirmed the deployed API reads 42 available slots from Neon. After the owner's explicit approval, Vercel SSO was disabled specifically for this project. Public HTTPS checks then confirmed the page and both static assets return 200 without authentication, `/slots` returns 401 for absent or wrong API keys, and the correct API key returns 200 with all 42 persisted slots. These final checks were read-only.

The Edge headless browser check passed: connect, choose slot, book, show confirmation, find history, cancel, and verify the slot becomes available. A 390px mobile viewport had no horizontal overflow; no JavaScript errors occurred. Screenshots are in `artifacts/desktop.png` and `artifacts/mobile.png`. The browser used an HTTPS test origin backed by Flask's test transport and an isolated SQLite database. This verifies browser behavior; it does not claim a browser session against the deployed service. The initial localhost navigation timed out in this environment.

Tests use `/reset`. Do not run them on the submitted database after submission.
