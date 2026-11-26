# Testing

How to run the tests, what they cover, and the latest results.

- **Unit/integration tests** (`tests/`, 197 tests in 17 files): Django's test client sends requests to
  the views and checks the responses and database rows. Each run uses a fresh test database.
- **Browser tests** (`e2e/`, 70 tests in 7 files): a real Chromium browser (driven by Playwright) clicks
  through the running app like a user.

## 1. Run them

```bash
python manage.py test tests                     # all 197 unit tests
python manage.py test tests.test_security       # one file

pip install -r requirements-dev.txt             # pytest, playwright, ruff
python -m playwright install chromium
python -m pytest e2e                            # all 70 browser tests
python -m ruff check .                          # lint (settings in ruff.toml)
python scripts/check_doc_links.py               # every link in the Markdown docs points to a real file
```

What `e2e/conftest.py` does:

- builds a **temporary database** (`migrate` + `seed_data`) and starts the app on port 8001 with
  `DEBUG=True`; `db.sqlite3` is never used;
- fails a test on any browser console error, page error, failed request or 4xx/5xx response, unless the
  test expects it (for example 404 for another user's data);
- replaces OpenStreetMap tiles with a blank image, so tests do not load the public tile server;
- saves screenshots of failures in `e2e/screenshots/` (ignored by git).

`e2e/test_00_demo_script.py` runs first (by file name) because it approves the seeded pending pharmacy.

GitHub Actions (`.github/workflows/ci.yml`) runs ruff, Django checks, the unit tests and the browser
tests on every push.

## 2. What the tests cover

### `tests/` (197)

| File | Tests | Covers |
|---|---|---|
| `test_manual_testing.py` | 19 | Referrer policy and OSM attribution, cancel reasons, partial availability, status texts, "All (N)" totals, owner notification read, migration count in the docs |
| `test_finishing.py` | 18 | Seed names, medicine-page distances, template tags, approval history and reason, stock delete cancels requests, customer-only requests, 404/500 pages |
| `test_features.py` | 17 | Registration, login, stock status, search, distance, requests, cancel, approval, catalogue, role checks, notifications |
| `test_admin_portal.py` | 16 | Admin dashboard, pharmacy list filters/search/pagination, approve/revoke, users, request monitor |
| `test_auth_profile.py` | 15 | Registration rules, login/logout, profile, password change/reset |
| `test_database_performance.py` | 15 | Query counts, unique constraint, indexes, cascades, pagination |
| `test_location_discovery.py` | 15 | Haversine, radius, distance sort, freshness |
| `test_pharmacy_dashboard.py` | 15 | Pharmacy dashboard, stock add/update/delete, answering requests, ownership |
| `test_discovery.py` | 14 | Medicine search and filters |
| `test_customer_dashboard.py` | 13 | Customer dashboard, my requests, notifications |
| `test_security.py` | 12 | Role access, isolation, POST-only actions, weak passwords, input limits |
| `test_regressions_pass3.py` | 8 | Rate limiter, proxy IP, limits, pincode, ids, page 0 |
| `test_regressions_fix_all.py` | 6 | Answered once, cancel vs answer, double approve, search order, duplicate request |
| `test_e2e_workflows.py` | 5 | Whole customer / pharmacy / admin journeys with the test client |
| `test_xss_map_popups.py` | 5 | Map popups do not run injected HTML |
| `test_demo_logins.py` | 2 | Demo logins shown only with DEBUG=True |
| `test_regressions_e2e.py` | 2 | Two bugs found in the browser (admin script, quantity input limits) |

### `e2e/` (70)

| File | Tests | Covers |
|---|---|---|
| `test_security.py` | 19 | Stored XSS payload on map and admin pages, 12 direct-URL role checks, cross-pharmacy 404s, GET logout 405 |
| `test_visitor.py` | 16 | Home, search filters and order, pagination, geolocation allowed/denied, maps, detail pages, layouts at 375px and 1280px |
| `test_auth.py` | 13 | Registration, login, lockout, Sign Out, password reset by console email, profile, change password |
| `test_pharmacy.py` | 10 | Dashboard and chart, stock add/set/delete, answer once, partial answer, re-approval after address change, revoked pharmacy |
| `test_admin.py` | 6 | Dashboard chart, approve (double click, stale tab), revoke, catalogue, lists, Django admin |
| `test_customer.py` | 5 | Request rules, tabs, cancel dialog, notifications |
| `test_00_demo_script.py` | 1 | The 5-minute demo from [MEDIFIND_PRESENTATION.md](../MEDIFIND_PRESENTATION.md) |

## 3. Latest results (branch `fix/manual-testing`, 2026-11-26)

- Unit tests: **197 passed** (about 80 s).
- Browser tests: **70 passed** (about 2 minutes). One test (`test_xss_search_map_popups`) failed once by
  timing and passed on every re-run.
- `ruff check .`: no issues. `makemigrations --check`: no changes.
- Not covered in the browser: real email delivery, Firefox/Safari, the 10-per-hour request limit and the
  20-per-IP login limit (both covered by unit tests), and production settings. Real map tiles were
  checked once by `scripts/take_screenshots.py`.

The history of every bug found and fixed is in [MEDIFIND_REVIEW.md](../MEDIFIND_REVIEW.md).
