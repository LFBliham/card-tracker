# Incident 001: Database stopped (controlled lab test)

**Date:** 2026-10-29
**Environment:** Ubuntu 26.04 VM (test environment), card-tracker.service via Gunicorn
**Type:** Deliberate test: `sudo systemctl stop postgresql@18-main`

## Symptoms
- `GET /health` → **503**, body `{"database":"unreachable","status":"error"}`
- `GET /` → **500** Internal Server Error
- Gunicorn itself still running: requests got HTTP responses (not curl `000`)

## Investigation
1. `curl` status codes showed the web server was up but failing → problem behind the app, not the app process.
2. `journalctl -u card-tracker -p err` returned no entries. Finding: journald stores
   this service's output at priority `info`, so `-p err` can't be used to find app errors.
3. Searched by text instead:

   ```
   journalctl -u card-tracker --since "15 minutes ago" -g "Health check failed|Traceback|OperationalError"
   ```

   Output:

   ```
   ERROR in app: Health check failed: database unreachable: connection failed:
   connection to server at "127.0.0.1", port 5432 failed: Connection refused
   psycopg.OperationalError: connection failed: connection to server at
   "127.0.0.1", port 5432 failed: Connection refused
   ```

4. "Connection refused" on 5432 = nothing listening → PostgreSQL not running.

## Root cause
PostgreSQL service stopped (deliberately, for this test).

## Fix
`sudo systemctl start postgresql@18-main`

## Verification
- `GET /health` → 200, `{"database":"ok","status":"ok"}`
- No app restart needed: each request opens a new database connection, so the app recovered on its own.

## Lessons
- `/health` gives monitoring a clear 503 with a specific reason; `/` just crashes with 500.
- Error details go to the logs, not the HTTP response (avoids leaking internal information).
- `-p err` doesn't work for this service's logs; search by text with `-g`.
- `connect_timeout=3` means a down database fails fast instead of hanging requests.
