# Deployment (Render)

**Purpose:** How to deploy MediFind to Render with the files in this repo, how to check it, and how to back up the data.
**Who it is for:** Whoever puts the app online.
**Last verified:** 2026-11-22 against commit `513e68f` (`render.yaml`, `build.sh`, `Procfile`, `config/settings.py`). Not yet deployed from this commit.

## 1. What is in the repo

| File | Job |
|---|---|
| `render.yaml` | Render "Blueprint": one free Python web service `medifind` and one free PostgreSQL database `medifind-postgres`, with environment variables |
| `build.sh` | Runs on every deploy: `pip install -r requirements.txt`, `collectstatic --no-input`, `migrate --no-input` |
| start command | `gunicorn config.wsgi:application` (in `render.yaml`; the `Procfile` has the same command for other hosts) |
| `.env.production.example` | Every production variable with placeholders |
| `.github/workflows/ci.yml` | GitHub Actions: lint, Django checks and both test suites on every push (runs once the repo is on GitHub) |
| `templates/404.html`, `templates/500.html` | Error pages shown when DEBUG is False |

## 2. Steps

1. Push the repo to GitHub (or GitLab) and create a **Blueprint** from it in the Render dashboard.
2. Replace `medifind.onrender.com` with your real address in `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`
   (`render.yaml` or the dashboard). Use exact values, no wildcards.
3. `render.yaml` already sets: `DEBUG=False`, a generated `SECRET_KEY`, `DATABASE_URL` from the database,
   `SECURE_SSL_REDIRECT=True`, `SECURE_HSTS_SECONDS=31536000`, `TRUSTED_PROXY_COUNT=1`,
   `PYTHON_VERSION=3.11.9`, the SMTP `EMAIL_BACKEND`, `EMAIL_PORT=587` and `EMAIL_USE_TLS=True`.
4. Fill in `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` and `DEFAULT_FROM_EMAIL` in the
   dashboard (marked `sync: false`). Without them, password reset emails are not sent.
5. Deploy. `build.sh` collects static files and applies all migrations.
6. Create the first admin in the Render shell: `python manage.py createsuperuser`.
   **Do not run `seed_data`** in production (it refuses when DEBUG is False anyway).
7. Log in and open `/dashboard/admin-portal/`. A superuser counts as an app admin.

`TRUSTED_PROXY_COUNT=1` matters: without it every visitor appears to come from Render's proxy, and the
login rate limit would block everyone after 5 failed logins.

## 3. Production checklist

| Check | Where it is set |
|---|---|
| `DEBUG=False` | `render.yaml` |
| Real `SECRET_KEY` (app refuses to start without one) | `render.yaml` (`generateValue`) |
| Exact `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` (https) | step 2 |
| HTTPS redirect, HSTS, secure cookies, `X-Frame-Options: DENY` | automatic when DEBUG is False (`config/settings.py:188`) |
| `TRUSTED_PROXY_COUNT=1` | `render.yaml` |
| Email variables filled in | step 4 |
| No demo data or demo logins | `seed_data` blocked; demo logins hidden when DEBUG is False |

## 4. Test production settings on your own machine

```bash
export DEBUG=False SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(55))')"
export ALLOWED_HOSTS=localhost,127.0.0.1 SECURE_SSL_REDIRECT=False USE_MANIFEST_STATIC=True
python manage.py collectstatic --no-input
python manage.py check --deploy
gunicorn config.wsgi:application
```

`check --deploy` will warn about the SSL redirect because it is turned off here for plain `http://localhost`.
Without `USE_MANIFEST_STATIC`, DEBUG=False also works locally without `collectstatic` (WhiteNoise serves
files straight from `static/`).

## 5. Backups

The project has no backup script and no scheduled backup. Check what your Render database plan offers.
Manual options:

```bash
# PostgreSQL (production): dump and restore with the standard tools
pg_dump "$DATABASE_URL" -F c -f medifind_$(date +%Y%m%d).dump
pg_restore -d "$DATABASE_URL" --clean --no-owner medifind_YYYYMMDD.dump

# Any database, through Django (JSON)
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission --indent 2 > backup.json
```

Locally, copy `db.sqlite3` while the server is stopped. To rebuild the local database, see
[DATABASE_ARCHITECTURE.md](DATABASE_ARCHITECTURE.md).

## 6. Known deployment limits

- The login rate limit uses an in-memory cache, so with several Gunicorn workers or instances each one
  counts separately.
- `static/admin/js/admin/RelatedObjectLookups.js` overrides a Django admin file (a one-line browser fix
  copied from newer Django). Delete it after upgrading Django to 6.x.
