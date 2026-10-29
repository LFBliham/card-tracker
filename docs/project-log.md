## 2026-10-22: Expanded VM root disk

Problem: / only 30G with 9.7G free. `sudo vgs` showed 30.47G unallocated (VFree).
Cause: the Ubuntu installer only allocated about half the volume group to ubuntu-lv.
Fix: `sudo lvextend -r -l +100%FREE /dev/ubuntu-vg/ubuntu-lv` (grows LV + ext4 online)
Verification: `df -h /` went from 30G size / 9.7G avail to 60G / 39G. VFree is now 0. Used unchanged at 19G.

## 2026-10-22: Environment check and PostgreSQL install

Checked VM: Ubuntu 24.04.5 LTS, aarch64 (Apple Silicon, UTM), Python 3.12.3, 7.7 GiB RAM.
Installed: `sudo apt install postgresql python3-venv git` (PostgreSQL 16.15).
Verification: `systemctl status postgresql@16-main` showed active (running), enabled at boot.
Notes:
- Cluster runs as dedicated `postgres` Linux user (non-root).
- Auth: local socket = peer (Linux username must match DB role); TCP = scram-sha-256 (password).
- Plain `psql` as jackjack fails: no DB role named jackjack.
- `SELECT version();` showed no output: wide result went to the pager. Fix: `\pset pager off`.

## 2026-10-28: Unplanned OS upgrade discovered

Symptom: psql reported version 18.6 instead of 16.15; sudo prompt looked different.
Investigation: `lsb_release -d` showed Ubuntu 26.04.1 LTS. `python3 --version` showed 3.14.4 (was 3.12.3).
`pg_lsclusters` showed two clusters: 16/main (port 5433, down) and 18/main (port 5432, online).
Cause: release upgrade installed PostgreSQL 18 and left the old 16 cluster in place.
Decision: removed 16. It held no project data (only `SELECT version();` had ever been run on it).
Fix: `sudo pg_dropcluster 16 main`, then `sudo apt purge postgresql-16 postgresql-client-16`.
Verification: `pg_lsclusters` shows only 18/main online on 5432; `postgresql@18-main` active (running).

## 2026-10-28: Database role and database for the app

Created role `cardtracker` (LOGIN only, no superuser/createdb), password set with `\password`.
Created database `cardtracker` owned by that role (least privilege: app never uses `postgres`).
Verification: `psql -h localhost -U cardtracker -d cardtracker` then `\conninfo`:
TCP to 127.0.0.1:5432, Password Used: true, SSL: true (TLSv1.3), Superuser: off.

## 2026-10-28: Project setup

- Git repo in ~/projects/card-tracker, branch renamed to `main`.
- Python virtual environment `.venv`; installed Flask 3.1.3 and psycopg 3.3.6; `pip freeze > requirements.txt`.
- `.gitignore`: .venv/, .env, __pycache__/ (keeps credentials out of Git).

## 2026-10-28: Database schema (migrations)

Approach: numbered migration files in db/, each run once with
`psql ... -v ON_ERROR_STOP=1 -1 -f <file>` (single transaction, stop on first error).
- 001_create_sets.sql: sets (identity id, year CHECK 1950-2100, UNIQUE(year, name)).
- 002_create_cards.sql: cards (FK to sets with ON DELETE RESTRICT, variant default 'Base',
  print_run CHECK > 0, wishlisted default false, UNIQUE(set_id, card_number, variant)).
Design decision: split checklist (`cards`) from physical copies (`owned_copies`, next)
so each copy can have its own condition, serial number, price and storage.
Constraint tests (all rejected as expected):
- duplicate set, year 20226, manual id
- duplicate card/variant, set_id 999 (FK), deleting a set with cards (RESTRICT), print_run 0
Observation: failed inserts still use up identity values, so gaps in IDs are normal.
Data: added set 2026 Topps F1 Turbo Attax (id 1) and first card: #168 Lando Norris, DriverCore.
Open decision: team naming convention (full official name vs short name).

## 2026-10-28: GitHub

- Generated ed25519 SSH key, added public key to GitHub.
- Verified GitHub's host key fingerprint before trusting it; `ssh -T git@github.com` authenticated.
Problem: push rejected with GH007 (commits would publish private email).
Fix: set Git email to GitHub noreply address; rewrote the 3 unpushed commits' author with
`git rebase -r --root --exec 'git commit --amend --no-edit --author=...'`.
Verification: `git log --format='%h %an <%ae>'` showed noreply on all commits; push succeeded.

## 2026-10-29: owned_copies table

- 003_create_owned_copies.sql: FK to cards (ON DELETE RESTRICT), condition CHECK list
  (mint, near_mint, excellent, good, fair, poor), serial_number CHECK > 0,
  purchase_price NUMERIC(8,2) CHECK >= 0, plus index on card_id
  (PostgreSQL doesn't index foreign key columns automatically).
- First run failed: syntax error (`.` instead of `,`); psql exited with code 3 (ON_ERROR_STOP).
  Fixed typo and re-ran. Note: always include `-1` so a migration is all-or-nothing.
- Verification: JOIN query showed copy of #168 Lando Norris, near_mint, Binder 1 page 1.

## 2026-10-29: Credentials via environment (.env)

- .env holds PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD (libpq reads these automatically,
  so no connection details in code). `chmod 600 .env` -> -rw------- (owner only).
- .env.example (placeholder password) committed; .env excluded by .gitignore.
- Verification: `git status` never lists .env; GitHub repo shows only .env.example.

## 2026-10-29: First Flask page

- app.py index route: LEFT JOIN cards -> owned_copies with count(), so every checklist card
  shows, including ones with 0 copies.
- Jinja template auto-escapes output (XSS protection).
- Verification: GET / returned 200, page showed cards from PostgreSQL.
- Clean-environment test: in a new terminal (no manually loaded variables), Flask still
  connected -> confirms python-dotenv loads .env.

## 2026-10-29: Add-card and add-copy forms with server-side validation

- Parameterised queries (%(name)s) throughout: values sent separately from SQL,
  preventing SQL injection.
- Post/Redirect/Get after successful submit (refresh doesn't resubmit).
- Validation failures return HTTP 400 and re-fill the form.
- DB UNIQUE violation caught and shown as a message (not a crash).
- Copy validation: serial number must be <= card's print_run (cross-table rule a CHECK
  constraint can't enforce); price as Decimal (rejects NaN/Infinity, >2 decimal places);
  date not in the future.
- Browser tests: second Lando copy -> Copies 2; added #317 Oscar Piastri Gold /50,
  copy with serial 42 -> Copies 1.
- curl tests (browser checks bypassed):
  - empty card number + print_run 0 -> 400, both errors listed
  - serial on unnumbered card -> 400
  - bad price + future date -> 400
  - copy for non-existent card 9999 -> 404
  - serial 51 on a /50 card -> 400
  - copy counts unchanged afterwards (nothing saved by rejected requests)

## 2026-10-29: Inconsistent team/subset data

Symptom: same team stored two ways ("Formula 1 Team" vs "Formula 1® Team");
subset stored as "TURBO CHROME" vs "Turbo Chrome".
Cause: subset and team were free-text fields with no restrictions.
Fix: inside BEGIN ... COMMIT, SELECT to check, then UPDATE (UPDATE 1 subset, UPDATE 2 team),
SELECT again to verify before COMMIT.
Prevention: subset and team restricted to fixed lists (dropdowns + server-side validation).
Resolved earlier open decision: team names stored as full official names, without ®.
Verification: curl POST with "McLaren Mastercard Formula 1® Team" -> 400.
Future improvement: move subsets/teams into database tables linked to each set.

## 2026-10-29: Gunicorn control socket permission error

Symptom: after starting card-tracker.service, journal showed
`[ERROR] Control server error: [Errno 13] Permission denied: '/home/cardtracker'`.
App still served requests (curl -> 200).
Investigation:
- `getent passwd cardtracker` -> home field is /home/cardtracker, which doesn't exist
  (--no-create-home records the path but doesn't create it).
- `gunicorn --help | grep -i control` -> Gunicorn 26 opens a control socket by default
  (/run/user/<uid>/gunicorn.ctl). The service user has no login session, so no such
  directory, and it fell back to the home path, also blocked by ProtectHome=true.
Root cause: Gunicorn's default control socket location isn't usable by a no-login system user.
Fix: added `--no-control-socket` to ExecStart (feature not used; disabling reduces attack surface).
Alternative considered: RuntimeDirectory=card-tracker + --control-socket /run/card-tracker/gunicorn.ctl.
Verification: restart -> new PIDs, curl 200, startup log in `systemctl status` no longer
shows the "Control server error" line. (Note: an earlier `journalctl -p err` check was not
valid evidence, since this service's output is stored at priority info. See incident 001.)

## 2026-10-29: Deployed as a systemd service

- Gunicorn 26.2.0 (2 sync workers) on 127.0.0.1:8000 replaces Flask dev server.
- Deliberate test before deploying: Gunicorn without PG* variables -> HTTP 500
  (psycopg fell back to socket + peer auth as jackjack). Loading env -> 200.
- System user `cardtracker` (uid 996, nologin, no home).
- Code: /opt/card-tracker (cloned from GitHub, root-owned, read-only to service).
- Config: /etc/card-tracker/card-tracker.env, root:cardtracker, 640.
- Unit: User=cardtracker, EnvironmentFile, Restart=on-failure, NoNewPrivileges,
  ProtectSystem=strict, ProtectHome, PrivateTmp. Unit file copied to deploy/.
- Verification: active (running), enabled; curl 200; `ps` shows all 3 processes
  (1 master + 2 workers) running as cardtracker; access log lines in journalctl.
- Reboot test: after `sudo reboot`, both card-tracker and postgresql@18-main active,
  curl -> 200, with no manual steps.

## 2026-10-29: /health endpoint

- GET /health runs `SELECT 1`; returns 200 {"status":"ok"} or 503 {"database":"unreachable"}.
- connect_timeout=3 added to database connections (fail fast if the database is down).
- Error details logged (app.logger.error), not returned in the response.
- Deploy process: commit and push, then `sudo git -C /opt/card-tracker pull`
  and `sudo systemctl restart card-tracker`.
- Verification: curl /health -> 200 on the service; database-stop test -> 503
  (see docs/incidents/001-database-stopped.md).
