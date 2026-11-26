# Deployment and settings

How to configure MediFind with environment variables and how to put it online on Render.
For the local setup see the project [README](../README.md). Checked against the code on branch
`fix/manual-testing` (2026-11-26); the app has not been deployed from this code yet.

## 1. Environment variables

`config/settings.py` reads a `.env` file in the project folder (`load_dotenv()`); real environment
variables win over `.env`. Yes/no values accept `true`, `1`, `yes` or `on`.

- `.env.example`: safe for local use (DEBUG=True, SQLite, console email). Copy it to `.env`.
- `.env.production.example`: every production variable with placeholders. Set them on the host;
  never commit real values.

| Variable | Default | Meaning |
|---|---|---|
| `DEBUG` | `False` | Developer mode: detailed errors, demo logins shown, `seed_data` allowed. Never on in production |
| `SECRET_KEY` | none | Signs sessions and tokens. **Required when DEBUG is False**. Generate: `python -c "import secrets; print(secrets.token_urlsafe(55))"` |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` with DEBUG, else empty | Host names the app answers to (comma-separated, no `*`) |
| `CSRF_TRUSTED_ORIGINS` | empty | Origins with scheme, for example `https://your-app.onrender.com` |
| `DATABASE_URL` | unset → SQLite `db.sqlite3` | PostgreSQL connection string in production |
| `SECURE_SSL_REDIRECT` | `True` | HTTP → HTTPS (only when DEBUG is False). Set `False` to test on plain `http://localhost` |
| `SECURE_HSTS_SECONDS` | `31536000` | HSTS time (only when DEBUG is False) |
| `USE_MANIFEST_STATIC` | True when `DATABASE_URL` is set and DEBUG is False | Hashed, compressed static files; needs `collectstatic` |
| `TRUSTED_PROXY_COUNT` | `0` | Reverse proxies in front of the app. Render: `1` (used for the login rate limit) |
| `LOGIN_RATE_LIMIT_ATTEMPTS` / `_IP_ATTEMPTS` / `_WINDOW` | `5` / `20` / `900` | Failed logins per IP + username, per IP, and seconds the counters last |
| `EMAIL_BACKEND` | console (prints emails in the terminal) | `django.core.mail.backends.smtp.EmailBackend` to really send |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | `localhost`, `587`, `True`, `False` | SMTP server (password reset only) |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | empty | SMTP login |
| `DEFAULT_FROM_EMAIL`, `SERVER_EMAIL`, `EMAIL_TIMEOUT` | `MediFind <noreply@localhost>`, same, `10` | Sender and timeout |
| `PYTHON_VERSION` | `3.11.9` in `render.yaml` | Render only: which Python to install |

Fixed settings: `TIME_ZONE = 'Asia/Kolkata'` with `USE_TZ = True`; after login → dashboard, after
logout → home; logs go to the console.

## 2. Deploy to Render

| File | Job |
|---|---|
| `render.yaml` | Render Blueprint: one free web service `medifind` (start command `gunicorn config.wsgi:application`) and one free PostgreSQL database, with the variables above |
| `build.sh` | Runs on every deploy: `pip install -r requirements.txt`, `collectstatic`, `migrate` |
| `.github/workflows/ci.yml` | GitHub Actions: lint, checks and both test suites on every push |

Steps:

1. Push the repo to GitHub and create a **Blueprint** from it in the Render dashboard.
2. Put your real address in `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` (`render.yaml` or the
   dashboard). A wrong host gives "400 Bad Request".
3. `render.yaml` already sets `DEBUG=False`, a generated `SECRET_KEY`, `DATABASE_URL`, HTTPS settings,
   `TRUSTED_PROXY_COUNT=1` and `PYTHON_VERSION`.
4. Optional: fill in `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` and `DEFAULT_FROM_EMAIL`.
   Without them, password reset emails are not sent.
5. Deploy. `build.sh` collects static files and applies the migrations.
6. Create the first admin with `python manage.py createsuperuser` in a Render shell. **Do not run
   `seed_data`** (it refuses when DEBUG is False), so add pharmacies and medicines through the app.

`TRUSTED_PROXY_COUNT=1` matters: without it every visitor seems to come from Render's proxy, and the
login rate limit would block everyone after 5 failed logins.

## 3. Test production settings locally

```bash
export DEBUG=False SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(55))')"
export ALLOWED_HOSTS=localhost,127.0.0.1 SECURE_SSL_REDIRECT=False USE_MANIFEST_STATIC=True
python manage.py collectstatic --no-input
python manage.py check --deploy      # warns about the SSL redirect, which is off here on purpose
gunicorn config.wsgi:application
```

## 4. Backups

There is no backup script. Manual options:

```bash
pg_dump "$DATABASE_URL" -F c -f medifind_$(date +%Y%m%d).dump                     # PostgreSQL
pg_restore -d "$DATABASE_URL" --clean --no-owner medifind_YYYYMMDD.dump
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission --indent 2 > backup.json
```

Locally, copy `db.sqlite3` while the server is stopped, or use `python scripts/setup.py --reset` (it keeps a
backup).

## 5. Known limits

- The login rate limit uses an in-memory cache, so several Gunicorn workers each count separately.
- `static/admin/js/admin/RelatedObjectLookups.js` patches a Django admin file; delete it after
  upgrading to Django 6.x.
