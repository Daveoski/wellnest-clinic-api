# Explain it in under five minutes

## 0:00–1:15 — Show the working page

Open the deployed page and enter the clinic key. Pick a clinician and available time, enter a name and email, and confirm. Point out the booking reference. Search the same email under “Find your bookings” and show the confirmation again. Cancel the booking and refresh the slots to show that time becomes available.

Say: “This page uses the Python API. Every API request includes the clinic key. The database stores bookings, so refreshing or sending the next request does not lose them.”

## 1:15–2:00 — Level 1 and Level 2

Open `app.py`. Show `create_app`, the `authenticate` hook, and the `slots`, `book`, and `lookup` routes.

Say: “Flask receives the requests. SQLAlchemy sends parameterized SQL to PostgreSQL on Neon. I followed the supplied endpoint names, JSON shapes and status codes. The API validates required fields, trims name and email, lowercases email, and rejects appointments that have started.”

## 2:00–2:45 — Level 3

Show `transaction` and the `one_confirmed_booking` index, then `cancel`.

Say: “Checking availability alone is unsafe: two requests could both see a free slot. The database transaction lock makes each write take its turn, even on separate serverless instances. The unique index also makes two confirmed bookings for one slot impossible. Cancelling changes the status and releases that constraint.”

## 2:45–3:30 — Level 4

Show the idempotency lookup and `finish`, then `history`.

Say: “The browser creates a retry key. The API stores its body fingerprint and response in the same transaction as the booking. Repeating it returns the same booking; changing the body returns 422. Booking history uses a signed cursor containing the last timestamp and ID, so the next page continues in stable order.”

## 3:30–4:10 — Level 5

Show the `attempts` query near the start of `book`.

Say: “I record every attempt for the normalized email, including failures. Five are allowed within a rolling minute. The sixth returns 429 and how many seconds to wait. This is database-backed, so restarting or scaling the API does not reset the limit. It is checked inside the transaction to prevent simultaneous requests bypassing it.”

## 4:10–4:50 — Tests and deployment

Open `tests/test_level3.py`, `test_level4.py` and `test_level5.py`. Explain the barriers that start concurrent requests together. Show the recorded pre-submission test results, then the Vercel deployment and public GitHub repository. Do not rerun destructive tests on the submitted database.

Say: “I verified the levels in order and tested the PostgreSQL path used in production. Vercel runs the Python app and serves the page over HTTPS; Neon keeps the data. Secrets are environment variables and are excluded from Git. After submission I will leave the deployment and data unchanged.”

Record this in Loom using your screen and voice, then copy Loom's share link into the submission. A generated script is not a Loom recording; the recording still needs to be made.
