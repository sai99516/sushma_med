# Security

**Purpose:** The security controls in the code today, where they live, and the known gaps.
**Who it is for:** Developers, reviewers and examiners asking "is it secure?".
**Last verified:** 2026-11-22 against commit `513e68f`.

No external penetration test has been done. The list below is what the code does, checked by reading
it and by the tests named at the end. For the history of every finding and fix, see
`MEDIFIND_REVIEW.md` ("Status of all findings" and later sections).

## 1. Settings that fail safe (`config/settings.py`)

| Setting | Behaviour |
|---|---|
| `DEBUG` | **False** unless the environment says `DEBUG=True` |
| `SECRET_KEY` | Read from the environment. If it is missing and DEBUG is False, the app stops with `ImproperlyConfigured`. A fixed, clearly insecure key is used only when DEBUG is True |
| `ALLOWED_HOSTS` | From the environment. Default: `localhost,127.0.0.1,[::1]` when DEBUG is True, **empty** otherwise. No `*` default |
| `CSRF_TRUSTED_ORIGINS` | From the environment, default empty |
| Always on | `SECURE_CONTENT_TYPE_NOSNIFF`, `SESSION_COOKIE_HTTPONLY`, `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` |
| When DEBUG is False | `X_FRAME_OPTIONS = 'DENY'`, secure session and CSRF cookies, `SECURE_SSL_REDIRECT` (default True), HSTS (`SECURE_HSTS_SECONDS` default 31536000, include subdomains, preload) |

`python manage.py check --deploy` with production-like settings reported no issues during the
verification recorded in `MEDIFIND_REVIEW.md` ("Verification results").

## 2. Accounts and login

- **Passwords** are hashed by Django's default PBKDF2-SHA256 hasher (1,000,000 iterations in Django 5.2).
  Registration applies Django's four password validators and a minimum length of 8.
- **Login rate limit** (`accounts/views.py:78-152`), using Django's cache:
  - 5 failed logins for the same IP + username, or 20 failed logins from one IP (any username), block
    further attempts with **HTTP 429** and "Too many failed login attempts".
  - The counters expire 15 minutes (`LOGIN_RATE_LIMIT_WINDOW = 900` seconds) after the first failure.
  - A successful login clears only the IP + username counter, so logging into your own account does not
    reset the per-IP counter.
  - Because the per-account counter includes the IP, a stranger cannot lock a user out from another IP.
  - **Client IP:** `REMOTE_ADDR`, or, when `TRUSTED_PROXY_COUNT` is N > 0, the N-th entry from the right
    of `X-Forwarded-For` (entries further left can be forged). Render needs `TRUSTED_PROXY_COUNT=1`.
  - The default cache is in-memory, so the limit is **per server process**, not shared between
    several workers or instances.
- **Safe redirect after login:** `?next=` is followed only if `url_has_allowed_host_and_scheme()` accepts it.
- **Logout is POST only** (`@require_POST`); a GET returns 405. The Sign Out button is a form with a CSRF token.
- **Password reset** uses Django's built-in token views and sends email through the `EMAIL_*` settings
  (console output locally).

## 3. Access control

Role decorators plus owner-scoped queries; see [ROLE_PERMISSION_MATRIX.md](ROLE_PERMISSION_MATRIX.md).
Another user's inventory row, request or notification returns 404. `is_staff` alone does not give access
to the app's admin portal.

## 4. Forms, CSRF and state changes

- Django's CSRF middleware is on; POST forms carry `{% csrf_token %}`.
- Actions that change data accept POST only: logout, mark notification(s) read, cancel request,
  approve/revoke. Inventory delete shows a confirm page on GET and deletes only on POST.
- Input limits: request quantity 1–1000, request and response messages up to 1000 characters,
  6-digit pincode, phone 7–15 digits, latitude/longitude ranges, stock quantity not negative.
- Abuse limits on requests: no duplicate pending request, at most 10 requests per customer per hour.

## 5. Injection and XSS

- **SQL injection:** all queries use the Django ORM; there is no raw SQL in the app code.
- **XSS** (cross-site scripting: getting the browser to run attacker-written script):
  - Django templates escape variables by default; no template uses `|safe` or `mark_safe`.
  - Data for JavaScript is passed with `json_script`.
  - Map popups are built from DOM nodes with `textContent` (`buildPopup()` in `static/js/map_popup.js`),
    so a pharmacy name like `<img src=x onerror=…>` is shown as text. Popup links allow only `tel:`, `/`
    and `https://`. "Pin on Map" buttons read `data-*` attributes instead of inline JavaScript strings.
  - `innerHTML` is used only for fixed geolocation status messages written in the template.
- CDN files (Bootstrap, Bootstrap Icons, Leaflet, Chart.js) are pinned to exact versions with SRI hashes.

## 6. Data exposure

- Demo logins are shown only when DEBUG is True, and `seed_data` refuses to run when DEBUG is False
  (it creates `admin/admin123`).
- The pharmacy licence number is shown only to the owner and admins, and is not searchable publicly.
- Pages for non-approved pharmacies are hidden from the public.
- Users see generic error messages; details go to the server log with `logger.exception`. With DEBUG
  off, unknown pages and server errors show the app's own `404.html` / `500.html`, never a traceback.
- Approval changes are stored with who made them (`PharmacyApprovalLog`); only the owner and admins can see them.
  The registration log line has the username and id, not the email.

## 7. Known gaps (honest list)

- The login rate limit is per process (local-memory cache).
- No Content-Security-Policy header, no two-factor login.
- Stock data is self-reported and cannot be verified by the app.

## 8. Tests that cover security

`tests/test_security.py` (role access, tenant isolation, GET rejected on POST-only URLs, weak passwords,
logout), `tests/test_finishing.py` (approval history visibility, customer-only requests),
`tests/test_xss_map_popups.py`, `tests/test_demo_logins.py`, `tests/test_regressions_pass3.py`
(rate limiter and proxy IP), and the browser tests in `e2e/test_security.py` (stored XSS on the 4 map pages, the home
page and the admin pending pages; 12 direct-URL cases, cross-pharmacy 404s, GET logout 405). How to run them: [TESTING_REPORT.md](TESTING_REPORT.md).
