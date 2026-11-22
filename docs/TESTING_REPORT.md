# Testing

**Purpose:** How to run the tests, what each test file covers, and the latest recorded results.
**Who it is for:** Developers before a commit, and examiners asking "how did you test it?".
**Last verified:** 2026-11-22 against commit `dd2f32c`. Counts come from `grep -c "def test_" tests/*.py`
and `pytest e2e --collect-only`. The results in section 4 are the runs recorded in `MEDIFIND_REVIEW.md`; they were not re-run for this doc.

There are two kinds of tests:

- **Unit/integration tests** (`tests/`, 160 tests in 15 files): Django's test client sends requests to the
  views and checks responses and database rows. They use a fresh test database each run.
- **End-to-end browser tests** (`e2e/`, 68 tests in 7 files): a real Chromium browser (driven by Playwright)
  clicks through the running app like a user.

## 1. Run the unit tests

```bash
python manage.py test tests                     # all 160
python manage.py test tests.test_security       # one file
```

## 2. Run the browser tests

```bash
pip install -r requirements-dev.txt             # pytest, playwright, pytest-playwright
python -m playwright install chromium            # on Linux maybe also: python -m playwright install-deps chromium
python -m pytest e2e                             # settings in e2e/pytest.ini (Chromium, headless)
```

What `e2e/conftest.py` does:

- builds a **new temporary database** (`migrate` + `seed_data`) and starts `runserver` on port 8001
  (`E2E_PORT` changes it) with `DEBUG=True`. `db.sqlite3` is never used. `E2E_KEEP_DB=1` keeps the temp folder;
- fails a test on any browser console error, uncaught page error, failed request or 4xx/5xx response,
  unless the test expects that status (for example 404 for another user's data, 405 for GET logout,
  429 for the login lockout);
- replaces OpenStreetMap tiles with a blank image, so tests do not load the public tile server;
- saves screenshots of failures and the server log in `e2e/screenshots/` (ignored by git).

`test_00_demo_script.py` must run first (it does, by file name) because it approves the seeded pending pharmacy.

## 3. What the tests cover

### `tests/` (160)

| File | Tests | Covers |
|---|---|---|
| `test_features.py` | 17 | Core flows: registration, login, stock status, search, distance, requests, cancel, approval, catalogue, role guards, notifications |
| `test_admin_portal.py` | 16 | Admin dashboard, pharmacy list filters/search/pagination, approve/revoke, users, request monitor |
| `test_auth_profile.py` | 15 | Registration rules, login/logout, profile, password change/reset |
| `test_database_performance.py` | 15 | Query counts (`select_related`, single aggregates), unique constraint, indexes exist, cascades, pagination |
| `test_location_discovery.py` | 15 | Haversine, radius, distance sort, freshness |
| `test_pharmacy_dashboard.py` | 15 | Pharmacy dashboard, stock add/update/delete and status, answering requests, ownership, freshness, pagination |
| `test_discovery.py` | 14 | Medicine search and filters |
| `test_customer_dashboard.py` | 13 | Customer dashboard, my requests, notifications |
| `test_security.py` | 12 | Role access, isolation, POST-only actions, weak passwords, input limits |
| `test_regressions_pass3.py` | 8 | Third-pass fixes P1–P8 (rate limiter, proxy IP, limits, pincode, ids, page 0) |
| `test_regressions_fix_all.py` | 6 | Answered once, cancel vs answer, double approve, search order, pincode box, duplicate request |
| `test_e2e_workflows.py` | 5 | Branding in the base template, whole customer / pharmacy / admin journeys, tenant isolation (test client, not a browser) |
| `test_xss_map_popups.py` | 5 | Map popups do not run injected HTML |
| `test_demo_logins.py` | 2 | Demo logins shown only with DEBUG=True |
| `test_regressions_e2e.py` | 2 | Browser-found bugs E1 (admin script) and E2 (quantity input min/max) |

### `e2e/` (68)

| File | Tests | Covers |
|---|---|---|
| `test_visitor.py` | 15 | Home, search filters and order, pagination, geolocation allowed/denied, maps, detail pages, stale badge, 375px and 1280px layouts |
| `test_auth.py` | 13 | Registration (valid and invalid), login, lockout, Sign Out, password reset via the console email, profile, change password |
| `test_security.py` | 19 | Stored XSS payload on map and admin pages, 12 direct-URL role checks, cross-pharmacy 404s, `/admin/` for a customer, GET logout 405 |
| `test_pharmacy.py` | 9 | Dashboard and chart, stock add/set/delete, inbox answer once, re-approval after address change, revoked pharmacy |
| `test_admin.py` | 6 | Dashboard chart, approve (double click and stale tab), revoke, catalogue add/edit/archive, lists, Django admin |
| `test_customer.py` | 5 | Request rules (duplicate, quantity 0 and 1001), tabs, cancel dialog, notifications |
| `test_00_demo_script.py` | 1 | The 5-minute demo from `MEDIFIND_PRESENTATION.md` |

## 4. Latest recorded results (from `MEDIFIND_REVIEW.md`, 2026-11-22)

- Unit tests: **160 tests, all passed** (after the E1/E2 fixes).
- Browser tests: first full run 68 tests, 67 passed, 1 failed (E1, a console error from Django admin's
  script). After the fixes the failed test and the changed customer test passed; the full browser suite
  was not re-run.
- Not tested in the browser: real email delivery, Firefox/Safari engines, real map tiles, the 10-per-hour
  request limit and the 20-per-IP login limit (both covered by unit tests), and production settings.

Run the suites yourself before quoting numbers in a presentation.
