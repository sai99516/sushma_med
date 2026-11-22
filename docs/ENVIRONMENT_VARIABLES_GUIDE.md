# Setup and settings (environment variables)

**Purpose:** How to run MediFind locally and what every environment variable does, with its real default.
**Who it is for:** Anyone setting up the project for the first time or configuring a server.
**Last verified:** 2026-11-22 against commit `dd2f32c` (`config/settings.py`, `.env.example`, `.env.production.example`, `requirements.txt`).

## 1. Local setup

Needs Python 3.11. No database server: SQLite is used when `DATABASE_URL` is not set.

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # local-safe: DEBUG=True, SQLite, console email
python manage.py migrate
python manage.py seed_data         # demo data; refuses to run when DEBUG=False
python manage.py runserver         # open http://127.0.0.1:8000
```

`config/settings.py` calls `load_dotenv()`, so values in a `.env` file in the project folder are read
automatically. Real environment variables win over `.env`.

**Packages** (`requirements.txt`, exact versions): Django 5.2.19, asgiref, sqlparse, python-dotenv,
gunicorn, whitenoise, dj-database-url, psycopg2-binary. Test-only packages (pytest, playwright,
pytest-playwright) are in `requirements-dev.txt`, which also includes `requirements.txt`.

## 2. Environment variables

"Bool" values accept `true`, `1`, `yes` or `on` (any case); anything else is false.

### Core

| Variable | Default | Meaning |
|---|---|---|
| `DEBUG` | `False` | Developer mode: detailed error pages, demo logins shown, `seed_data` allowed. Never on in production |
| `SECRET_KEY` | none | Signs sessions and tokens. **Required when DEBUG is False** (the app will not start without it). With DEBUG=True and no value, an insecure fixed key is used |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` if DEBUG, else empty | Comma-separated host names the app answers to |
| `CSRF_TRUSTED_ORIGINS` | empty | Comma-separated origins with scheme, for example `https://your-app.onrender.com` |
| `DATABASE_URL` | unset → SQLite `db.sqlite3` | PostgreSQL connection string in production |

### HTTPS (used only when DEBUG is False)

| Variable | Default | Meaning |
|---|---|---|
| `SECURE_SSL_REDIRECT` | `True` | Redirect HTTP to HTTPS. Set `False` to test DEBUG=False on plain `http://localhost` |
| `SECURE_HSTS_SECONDS` | `31536000` (1 year) | HSTS: tells browsers to use HTTPS only for this site |

### Static files

| Variable | Default | Meaning |
|---|---|---|
| `USE_MANIFEST_STATIC` | True when `DATABASE_URL` is set (and DEBUG is False) | Use WhiteNoise's hashed, compressed files; needs `collectstatic` first. Otherwise WhiteNoise serves straight from `static/` |

### Login rate limit and proxy

| Variable | Default | Meaning |
|---|---|---|
| `LOGIN_RATE_LIMIT_ATTEMPTS` | `5` | Failed logins allowed per IP + username |
| `LOGIN_RATE_LIMIT_IP_ATTEMPTS` | `20` | Failed logins allowed per IP (any username) |
| `LOGIN_RATE_LIMIT_WINDOW` | `900` | Seconds the counters last |
| `TRUSTED_PROXY_COUNT` | `0` | Number of reverse proxies in front of the app. `0` = use `REMOTE_ADDR` (local). Render: `1` |

### Email (password reset)

| Variable | Default | Meaning |
|---|---|---|
| `EMAIL_BACKEND` | console backend (prints emails in the terminal) | Use `django.core.mail.backends.smtp.EmailBackend` to really send |
| `EMAIL_HOST` | `localhost` | SMTP server |
| `EMAIL_PORT` | `587` | SMTP port |
| `EMAIL_USE_TLS` | `True` | STARTTLS |
| `EMAIL_USE_SSL` | `False` | Implicit SSL (do not combine with TLS) |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | empty | SMTP login |
| `EMAIL_TIMEOUT` | `10` | Seconds |
| `DEFAULT_FROM_EMAIL` | `MediFind <noreply@localhost>` | Sender address |
| `SERVER_EMAIL` | same as `DEFAULT_FROM_EMAIL` | Sender for error emails |

### Render only

`PYTHON_VERSION` (`3.11.9` in `render.yaml`) tells Render which Python to install; the app does not read it.

## 3. Fixed settings worth knowing

`TIME_ZONE = 'Asia/Kolkata'` with `USE_TZ = True` (stored in UTC, shown in India time);
`LANGUAGE_CODE = 'en-us'`; `LOGIN_URL = 'login'`; after login → `dashboard`; after logout → `home`.
Logs go to the console through the `medfind` logger (INFO) and Django's request/security loggers (WARNING).

## 4. Templates for `.env`

- `.env.example`: safe for local use (DEBUG=True, SQLite, console email). Copy it to `.env`.
- `.env.production.example`: every production variable with placeholders. Set these on the host; never
  commit real values. Generate a secret key with
  `python -c "import secrets; print(secrets.token_urlsafe(55))"`.

Deployment steps are in [PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md).
