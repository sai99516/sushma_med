# MediFind

MediFind is a Django web app that helps people find medicines at nearby pharmacies.

- **Customers** search medicines by name, city, pincode or distance, see the
  **pharmacy-reported** stock level and when it was last updated, and send an
  availability request to a pharmacy. A pharmacy answers each request once.
- **Pharmacy owners** register (one pharmacy per owner), wait for admin approval,
  keep their stock up to date and answer requests.
- **Admins** approve or revoke pharmacies (with a stored history and optional
  reason), manage (and archive) the medicine catalogue and monitor requests.

Stock shown is reported by pharmacies. It is not a reservation and not medical advice.

## Requirements

- Python **3.11**
- No database server needed locally (SQLite). Production uses PostgreSQL.

## Quick start

```bash
git clone <repo-url> medifind && cd medifind
python scripts/setup.py                  # Windows: py scripts\setup.py
.venv/bin/python manage.py runserver     # Windows: .venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000

`scripts/setup.py` checks for Python 3.11+, creates `.venv`, installs `requirements.txt`, copies
`.env.example` to `.env` (if missing), runs `migrate`, and runs `seed_data` when the database is new.
It prints the exact command to start the server.

**Fresh demo database:** `python scripts/setup.py --reset` (Windows: `py scripts\setup.py --reset`)
moves `db.sqlite3` to a timestamped backup in the parent folder, then runs `migrate` and `seed_data`
(so "Metro Life" is pending again for the demo).

### Manual setup (same steps by hand)

Linux / Mac:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # local-safe: DEBUG=True, SQLite, console email
python manage.py migrate
python manage.py seed_data         # demo data; refuses to run when DEBUG=False
python manage.py runserver
```

Windows (cmd or PowerShell):

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

`DEBUG` defaults to **False**. Without `DEBUG=True` in `.env` the app requires a
real `SECRET_KEY` and `ALLOWED_HOSTS` and will not start.

### Demo logins (only after `seed_data`, only shown when DEBUG=True)

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `admin123` |
| Pharmacy owner | `apollo_owner` | `password123` |
| Customer | `customer1` | `password123` |

All demo logins are listed in [docs/USER_GUIDE.md](docs/USER_GUIDE.md#7-demo-data-local-only).
Never run `seed_data` against a production database.

## Running the tests

```bash
python manage.py test tests            # 197 unit/integration tests

pip install -r requirements-dev.txt    # browser tests (70, Playwright + Chromium) and ruff
python -m playwright install chromium
python -m pytest e2e                   # builds its own temporary database
python -m ruff check .                 # lint
```

GitHub Actions (`.github/workflows/ci.yml`) runs all of this on every push.
Details: [docs/TESTING.md](docs/TESTING.md).

## Deploying to Render

`render.yaml` is a Render Blueprint (web service + free PostgreSQL) and `build.sh` runs on every deploy.
Steps and every environment variable: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Known limitations

- Stock is self-reported by pharmacies; freshness is shown as "updated X ago".
  Anything older than 24h is marked "confirm before visiting".
- Login rate limiting uses Django's local-memory cache, so it is per process
  (not shared between several gunicorn workers or instances).
- In-app notifications only; no email/SMS notifications for requests.
- The project has no backup script; check what your Render database plan offers.

## Documentation

Start at [docs/README.md](docs/README.md): user guide, architecture, testing, deployment, the report
draft, diagrams and screenshots. Demo script and likely questions:
[MEDIFIND_PRESENTATION.md](MEDIFIND_PRESENTATION.md). History of every review finding and fix:
[MEDIFIND_REVIEW.md](MEDIFIND_REVIEW.md).
