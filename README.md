# MediFind

MediFind is a Django web app that helps people find medicines at nearby pharmacies.

- **Customers** search medicines by name, city, pincode or distance, see the
  **pharmacy-reported** stock level and when it was last updated, and send an
  availability request to a pharmacy. A pharmacy answers each request once.
- **Pharmacy owners** register (one pharmacy per owner), wait for admin approval,
  keep their stock up to date and answer requests.
- **Admins** approve or revoke pharmacies, manage (and archive) the medicine
  catalogue and monitor requests.

Stock shown is reported by pharmacies. It is not a reservation and not medical advice.

## Requirements

- Python **3.11**
- No database server needed locally (SQLite). Production uses PostgreSQL.

## Local setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # local-safe: DEBUG=True, SQLite, console email
python manage.py migrate
python manage.py seed_data         # demo data; refuses to run when DEBUG=False
python manage.py runserver
```

Open http://127.0.0.1:8000

`DEBUG` defaults to **False**. Without `DEBUG=True` in `.env` the app requires a
real `SECRET_KEY` and `ALLOWED_HOSTS` and will not start.

### Local demo logins (only after `seed_data`, only shown when DEBUG=True)

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `admin123` |
| Pharmacy owner | `apollo_owner` | `password123` |
| Customer | `customer1` | `password123` |

Never run `seed_data` against a production database.

### Rebuilding the local database

`db.sqlite3` is ignored by git and may contain old data. To start clean:

```bash
mv db.sqlite3 db.sqlite3.bak       # keep a backup instead of deleting
python manage.py migrate
python manage.py seed_data
```

## Running the tests

```bash
python manage.py test tests
```

## Deploying to Render

`render.yaml` is a Render Blueprint (web service + free PostgreSQL).

1. Push the repo and create a Blueprint from it on Render.
2. In `render.yaml` / the Render dashboard, replace `medifind.onrender.com` with
   your real URL in `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` (no wildcards).
3. Fill in the email variables (`EMAIL_HOST`, `EMAIL_HOST_USER`,
   `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`) so password reset emails are sent.
4. `build.sh` installs requirements, runs `collectstatic` and `migrate`.
5. Create the first admin with `python manage.py createsuperuser` in the Render
   shell (do **not** use `seed_data`).

See `.env.production.example` for every production variable.

## Known limitations

- Stock is self-reported by pharmacies; freshness is shown as "updated X ago".
  Anything older than 24h is marked "confirm before visiting".
- Login rate limiting uses Django's local-memory cache, so it is per process
  (not shared between several gunicorn workers or instances).
- In-app notifications only; no email/SMS notifications for requests.
- No audit trail or rejection reason for approvals (only log lines).
- The medicine detail page does not show distances.
- Render's free PostgreSQL plan has no automatic backups.
- Many files in `docs/` describe older versions of the code; see
  `docs/README_DOCS_STATUS.md`.
