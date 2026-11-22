# MediFind – Code Review

Read-only review (2026-11-18). Nothing was run. **IN CODE** means I saw it in the file and line given. **LIKELY** means it is inferred and not proven.

---

## 1. Summary

- MediFind is a Django website that helps people find medicines at nearby pharmacies.
- It has three roles: **Customer**, **Pharmacy owner** and **Admin** (`accounts/models.py:5-9`).
- Pharmacy owners register, wait for an admin to approve them, then add medicines to their stock and set quantities.
- Customers search medicines by name, city, pincode or distance (GPS + Haversine formula). They see the stock status and when it was last updated.
- Customers can send an "availability request" to a pharmacy. The pharmacy confirms or declines it, and both sides get in-app notifications.
- Admins approve pharmacies, manage the medicine catalogue and watch all requests.
- Only **approved** pharmacies show up in public search. A banner says stock is pharmacy-reported, not guaranteed and not medical advice (`templates/base.html:42-48`).

## 2. Structure

| Part | What it does |
|---|---|
| `config/settings.py`, `config/urls.py` | Project settings (reads `.env`), main URL routes |
| `accounts/` | Custom `User` model with `role`; register, login, logout, profile, notifications; role decorators (`decorators.py`) |
| `pharmacies/` | `Pharmacy` model (owner, address, lat/lng, `is_approved`); nearby search + distance (`services.py`); admin approval pages |
| `medicines/` | `Medicine` catalogue model; public medicine search (`services.py`); admin add/edit; `seed_data` demo command |
| `inventory/` | `Inventory` model (pharmacy + medicine + quantity + status + `updated_at`); pharmacy stock add/edit/delete |
| `requests_app/` | `AvailabilityRequest` (customer asks a pharmacy) and `Notification` models |
| `dashboard/` | Home page plus one dashboard per role (no models) |
| `templates/` | HTML pages (Bootstrap, Leaflet maps, Chart.js loaded from CDNs) |
| `tests/` | 10 test files |
| `docs/` | About 60 generated reports (not needed to understand the code) |
| `build.sh`, `render.yaml`, `Procfile` | Deployment to Render (gunicorn + PostgreSQL) |

Pattern: **views** read the request → **services.py** do the logic and queries → **templates** show the result.

## 3. How to start it (from reading only, LIKELY)

1. Python **3.11** (only stated in `render.yaml:35`). Create a venv and activate it.
2. `pip install -r requirements.txt`
3. Create `.env` with `DEBUG=True`. **Do not copy `.env.example` as it is.** It has `DEBUG=False` and a Postgres `DATABASE_URL`, so the app would ask for Postgres and HTTPS locally. With no `.env`, the app falls back to SQLite.
4. `python manage.py migrate`
5. `python manage.py seed_data`: demo data. Login is `admin / admin123`, and customers and pharmacies use `password123`.
6. `python manage.py runserver` → http://127.0.0.1:8000
7. Tests: `python manage.py test tests`

**Missing:**
- No README or setup guide in the root.
- Python version not stated for local use.
- No exact version pins (lock file).
- `.env.example` is set up for production, not local use.
- `db.sqlite3` is shipped with the code, so it may already contain users and data.

## 4. Is it current and safe

**Versions** (`requirements.txt`): Django `>=5.2,<6.0` (5.2 is an LTS release that still gets security fixes), Pillow, python-dotenv, gunicorn, whitenoise, dj-database-url, psycopg2-binary. All are **ranges, not pinned**, so two installs can get different versions. Chart.js is loaded **without a version** (`templates/base.html:277`, `cdn.jsdelivr.net/npm/chart.js`), so a new major version could break the charts.

**Security:**
- IN CODE: a hardcoded fallback `SECRET_KEY` (`config/settings.py:15-18`).
- IN CODE: `DEBUG` defaults to **True** (`config/settings.py:20`).
- IN CODE: `ALLOWED_HOSTS` defaults to `*` (`config/settings.py:22`).
- So if the env vars are missing on a server, the site runs insecurely. `render.yaml` sets them, so it is fine on Render.
- IN CODE: the demo command creates the superuser `admin / admin123` and **resets it on every run**, with no DEBUG check (`medicines/management/commands/seed_data.py:19-31`).
- Good: the CSRF middleware is on, and every POST form has `{% csrf_token %}`. Production uses secure cookies and HSTS. Maps get their data via `json_script` (no XSS). Login uses a safe `next` redirect check (`accounts/views.py:86`).
- No suspicious code found: no `eval`, `exec`, `subprocess`, `pickle` or hidden network calls in the app code.

## 5. Top bugs and risks (most important first)

**Checked and OK: pharmacy A cannot edit pharmacy B's stock.** Edit and delete look up the item with `pharmacy=<my pharmacy>` and return 404 for anything else (`inventory/views.py:105-109`, `:138-142`). Add always uses the owner's own pharmacy (`inventory/views.py:67,79`). Request replies are scoped the same way (`requests_app/views.py:160-164`).

| # | Severity | Problem | Where | One-line fix |
|---|---|---|---|---|
| 1 | **High** | Insecure defaults: secret key fallback, DEBUG=True, hosts `*` | IN CODE `config/settings.py:15-22` | Default `DEBUG` to False and raise an error if `SECRET_KEY` is not set in production. |
| 2 | **High** | `seed_data` creates and resets the superuser `admin/admin123`; one run on the live database creates a known login | IN CODE `medicines/management/commands/seed_data.py:19-31` | Refuse to run when `DEBUG` is False, or read the password from an env var. |
| 3 | **Medium** | Search lists **Out of Stock first**: `order_by('-availability_status')` sorts the text in reverse (O > L > I) | IN CODE `medicines/services.py:68`, `:179` | Sort by an explicit rank (`Case/When`: IN=0, LOW=1, OUT=2). |
| 4 | **Medium** | Wording suggests guaranteed or checked stock ("Live Stock", "Real-time Stock", "Verified Fresh"). This contradicts the disclaimer banner. | IN CODE `templates/base.html:224`, `templates/pharmacies/discovery.html:177`, `inventory/models.py:99`, `templates/inventory/list.html:149`, `templates/home.html:13` | Say "Pharmacy-reported · last updated X ago" everywhere. |
| 5 | **Medium** | An approved pharmacy can change its name, address and map location with no new admin check | IN CODE `accounts/forms.py:192-215`, `pharmacies/forms.py:7-16` (saved in `accounts/views.py:118-125`, `pharmacies/views.py:102-105`) | Set `is_approved=False` when those fields change, or make them read-only. |
| 6 | **Low** | Logout works with a GET link, so another site can log users out. Login has no limit on attempts, so passwords can be brute-forced. | IN CODE `accounts/views.py:95-102`, `templates/base.html:159`; brute force LIKELY | Make logout a POST form; add login rate limiting (e.g. django-axes). |
| 7 | **Low** | Raw error text is shown to users | IN CODE `accounts/views.py:63`, `requests_app/views.py:183` | Show a generic message and keep details in the log. |

Small stock note: the status label says "Low Stock (< 10 units)" (`inventory/models.py:11`), but the code marks exactly 10 units as LOW (`inventory/models.py:54-57`). Fix the label to "1–10".

## 6. Learning path

**Read in this order:**
1. `config/settings.py`, `config/urls.py`
2. `accounts/models.py`, `accounts/decorators.py`
3. `pharmacies/models.py`, `medicines/models.py`, `inventory/models.py`, `requests_app/models.py`
4. `inventory/views.py` + `inventory/services.py` (stock management)
5. `medicines/views.py` + `medicines/services.py` (customer search)
6. `pharmacies/services.py` (distance, approval)
7. `requests_app/views.py` + `services.py`, then `dashboard/`
8. `templates/base.html`, `templates/medicines/search.html`
9. `medicines/management/commands/seed_data.py`, then one test file, e.g. `tests/test_security.py`

**8 questions to answer:**
1. What are the three user roles, and where is a user's role stored?
2. How does the code stop pharmacy A from editing pharmacy B's stock?
3. When is an item "In Stock", "Low Stock" or "Out of Stock", and where is that decided?
4. Why does an unapproved pharmacy not appear in search? Which line filters it out?
5. What does `updated_at` (`auto_now=True`) do, and how does the page use it to show freshness?
6. How is the distance to a pharmacy calculated, and what happens if a pharmacy has no coordinates?
7. What happens, step by step, when a customer sends an availability request?
8. What changes between local (`DEBUG=True`) and production (`DEBUG=False`) in `settings.py`?

---

## Additional findings (second pass)

Second read-only pass (2026-11-22). I read every app, the templates, tests, settings and deployment files, and the 67 files in `docs/`. No code was changed. Django is not installed here, so no tests or management commands were run. The only thing "run" was reading `db.sqlite3` in read-only mode. The bugs already in sections 4–5 are not repeated.

**IN CODE** = seen at the file:line given. **LIKELY** = inferred from the code but not proven by running it.

**Correction to section 4:** "Maps get their data via `json_script` (no XSS)" is not fully true. `json_script` makes the data safe to carry into the page, but the JavaScript then puts it into popup HTML without escaping it. See N1.

### High

| ID | Where | What is wrong | Why it matters | Suggested fix | Source | Status |
|---|---|---|---|---|---|---|
| N1 | `templates/pharmacies/detail.html:152`, `templates/medicines/detail.html:169`, `templates/pharmacies/discovery.html:316-332` and `:409-417`, `templates/medicines/search.html:397-410` and `:487-489` | **Stored XSS in the Leaflet map popups.** Pharmacy name, address and phone are inserted raw into popup HTML with template literals (`bindPopup(\`<strong>${p.name}</strong>…\`)`, `setContent(...)`). The `escapejs` → `showOnMap()` path decodes back to raw HTML too. The pharmacy owner controls these fields (`accounts/forms.py:112-122`, `pharmacies/forms.py:7-16`). | A person registers a pharmacy named e.g. `<img src=x onerror=…>`. Admins can open the detail page of an **unapproved** pharmacy (`pharmacies/services.py:245-248`), so the script runs in the admin's session, and it can approve itself or use `/admin/`. After approval it also runs for every visitor who opens the map. | Build popups with DOM nodes and `textContent`, or escape the values with a small `escapeHtml()` before inserting them. Also validate the fields on the server. | code review; docs claiming "XSS safe" are wrong (SECURITY_FINAL_REVIEW, ADMIN_SECURITY_REVIEW, LOCATION_DISCOVERY_REPORT) | IN CODE |
| N2 | `templates/base.html:242-244`, `templates/home.html:264-278`, `templates/accounts/login.html:66-72` | **Demo logins, including `admin / admin123`, are printed on every page** (footer), on the home page and on the login page. There is no `DEBUG` or demo-mode check. | Together with known issue #2 (seed_data), anyone who visits a deployed site where `seed_data` was ever run gets a superuser login, which also opens `/admin/`. Even without seed data, it tells attackers which usernames to try. | Show the block only when `settings.DEBUG` (or an explicit `DEMO_MODE` env var) is on. | code review; TECHNICAL_DEBT_REPORT SEC-04, PROJECT_BASELINE_AUDIT | IN CODE |

### Medium

| ID | Where | What is wrong | Why it matters | Suggested fix | Source | Status |
|---|---|---|---|---|---|---|
| N3 | `requests_app/services.py:85-93`, `requests_app/views.py:166`, `templates/requests/pharmacy_inbox.html:88-93` | A pharmacy can **answer the same request again and again**. Only CANCELLED is blocked, so CONFIRMED can be flipped to UNAVAILABLE (and back) at any time. The inbox shows "Respond" on every row that is not cancelled. | Each change sends the customer a new notification. A customer who saw "Confirmed" may travel for nothing. The docs describe CONFIRMED and UNAVAILABLE as final states. | Allow a response only while the status is PENDING, or keep a history of changes. | code review; PHARMACY_REQUEST_MANAGEMENT, CUSTOMER_REQUEST_TRACKING, CURRENT_ARCHITECTURE (wrong claim) | IN CODE |
| N4 | `requests_app/services.py:78-93` vs `:113-116` | **Lost update between cancel and respond.** Respond reads the row, checks `status != 'CANCELLED'`, then calls a full `save()` with no lock or transaction. Cancel saves only `status`. | If the customer cancels between the pharmacy's check and its save, the CANCELLED status is overwritten with CONFIRMED or UNAVAILABLE. | `transaction.atomic()` + `select_for_update()`, or a conditional `filter(pk=…, status='PENDING').update(...)`. | code review | pattern IN CODE; race LIKELY |
| N5 | `pharmacies/services.py:216-226`, `pharmacies/views.py:163-169` | **Approval is a toggle, not a set.** Each POST flips `is_approved`. | A double click, or two admins approving at the same time, leaves the pharmacy **un**approved, and the owner gets both "approved" and "revoked" notifications. The message also reads "has been revoked approval". | Send the wanted state (`approve` / `revoke`) and set it. Do nothing if it is already in that state. | code review | IN CODE |
| N6 | `config/settings.py:173-177`, `.env.example:46-53`, `render.yaml:19-37` | **Password reset email cannot work in production.** Settings only read `EMAIL_BACKEND` (default: console). `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` and `DEFAULT_FROM_EMAIL` are listed in `.env.example` but never read. `render.yaml` sets none of them. | Users see "email sent" (`password_reset_done`), but the email only goes to the server log. Setting the documented env vars does nothing. | Read all the EMAIL_* settings and `DEFAULT_FROM_EMAIL` from env, and set them in `render.yaml`. | code review; ENVIRONMENT_VARIABLES_GUIDE, PASSWORD_MANAGEMENT_REPORT, ENVIRONMENT_AUDIT | IN CODE |
| N7 | `medicines/services.py:67-69`, `:112-132`, `:137`; `pharmacies/services.py:117`, `:169-181`, `:186` | Public search and pharmacy discovery **load every matching row into a Python list**, compute distances in Python, then paginate the list. Map pins are built from *all* results, not just the current page. An empty search (`/medicines/search/`) returns every stock row of every approved pharmacy. | Each anonymous request reads the whole inventory table and sends every row as a map pin in the HTML. This gets slow quickly as data grows, and it is easy to abuse. | Paginate in the database. Filter by distance with a bounding box (lat/lng range) before running Haversine. Limit map pins to the current page or a fixed maximum. | code review; TECHNICAL_DEBT_REPORT PERF-01, DATABASE_PERFORMANCE_TEST_REPORT | IN CODE |
| N8 | `accounts/forms.py:120-121`, `:203-204`; `pharmacies/forms.py:14-15`; `pharmacies/models.py:26-39` | **No range check on latitude/longitude** in any of the 3 pharmacy forms. `DecimalField(9,6)` accepts values like 450.0. The detail-page map pins test truthiness (`if p.latitude and p.longitude`, `pharmacies/services.py:253`, `medicines/services.py:184`), not `is_valid_coordinate()`. | Invalid coordinates are saved silently. The pharmacy then gets no distance and drops out of every radius search, while the detail map still tries to draw it. A real coordinate of exactly 0 is dropped. | Add `MinValueValidator`/`MaxValueValidator` (±90 / ±180) on the model, and use `is_valid_coordinate()` everywhere pins are built. | code review; TECHNICAL_DEBT_REPORT DATA-01, PROJECT_BASELINE_AUDIT | IN CODE |
| N9 | `requests_app/views.py:24-49`, `requests_app/services.py:23-36` | **No limit and no duplicate check on availability requests.** The view also does not check that the pharmacy actually lists that medicine. Any medicine id works. | One customer (or a script) can send unlimited requests and notifications to a pharmacy, including for medicines it does not stock. | Block a second PENDING request for the same customer+pharmacy+medicine, require an `Inventory` row, and add a simple per-user rate limit. | code review; TECHNICAL_DEBT_REPORT SEC-03, PROJECT_BASELINE_AUDIT | IN CODE |
| N10 | `templates/home.html:29` | The home page hero search has a "City or Pincode…" box, but the input is named `city`. The search filters `pharmacy__city__icontains` with it (`medicines/services.py:58-59`). | Typing a pincode on the home page always gives "no results". This is the first search box people use in a demo. | Detect digits and send them as `pincode`, or add a separate pincode field. | docs/LANDING_PAGE_IMPLEMENTATION_REPORT (wrong claim), confirmed in code | IN CODE |
| N11 | `pharmacies/models.py:5-9`, `pharmacies/services.py:202-208` | `Pharmacy.owner` is a ForeignKey (one user can own many pharmacies), but every owner view uses `Pharmacy.objects.filter(owner=user).first()`. | If an admin adds a second pharmacy for an owner (possible in `/admin/`), only the newest one can be managed. Requests to the other one are never visible to its owner. | Make it a `OneToOneField`, or let the owner choose a pharmacy. | docs/PROJECT_BASELINE_AUDIT, TECHNICAL_DEBT_REPORT ARCH-01 | IN CODE |

### Low

| ID | Where | What is wrong | Why it matters | Suggested fix | Source | Status |
|---|---|---|---|---|---|---|
| N12 | `templates/medicines/search.html:494-496` | Leftover `}` `}` `</script>` after the real closing `</script>` (line 493). | The two braces show up as visible text at the bottom of the search page. | Delete lines 494-496. | code review | IN CODE |
| N13 | `templates/base.html:233` | The footer link "Store Inventory Directory" points to `search_medicines` instead of `pharmacy_discovery`. | Wrong page. | Use `{% url 'pharmacy_discovery' %}`. | code review | IN CODE |
| N14 | `medicines/services.py:62`, `pharmacies/services.py:115` | The pincode filter uses `icontains`, so "50" or "500" matches many pincodes. | Pincode search returns pharmacies from other areas. | Use an exact match (`pincode=…`) or `startswith`. | code review | IN CODE |
| N15 | `pharmacies/admin.py:11-19` | Django-admin bulk approve/revoke uses `queryset.update()`. No owner notification and no log, unlike the portal toggle (`pharmacies/services.py:222-231`). | Owners are not told. There is no audit trail. | Call the service for each pharmacy, or create the notifications in the action. | code review; PHARMACY_GOVERNANCE_DOCUMENTATION | IN CODE |
| N16 | `accounts/decorators.py:5-39`, `accounts/models.py:29-31`, `dashboard/views.py:36-40` | Role checks are looser than they look. (a) `customer_required` and `pharmacy_required` also let admins in, and `is_admin_user` is true for **any `is_staff` user**, so a staff account with no Django permissions gets the full admin portal (approve pharmacies, see all users' emails and phones). (b) `customer_dashboard_view` only has `@login_required`. (c) The role decorators redirect to `login` without `?next=`, so users lose the page they wanted. | Wider access than intended, and worse UX. Several docs say each decorator admits only its own role. | Do not treat `is_staff` as app admin, or document it. Use `@customer_required` on the customer dashboard. Use `redirect_to_login(request.get_full_path())`. | code review; ROLE_PERMISSION_MATRIX, SECURITY_FINAL_REVIEW (wrong claims) | IN CODE |
| N17 | `config/settings.py:121`, `dashboard/services.py:62` | `TIME_ZONE='UTC'` and no per-user time zone. The greeting and every "Reported: <date>" stamp are in UTC for Indian users (UTC+5:30). | "Good morning" in the afternoon. Times are 5.5 hours off. | Set `TIME_ZONE='Asia/Kolkata'` (data stays UTC because `USE_TZ=True`). | code review; CUSTOMER_DASHBOARD_REPORT (wrong claim) | IN CODE |
| N18 | `dashboard/services.py:151-154`, `pharmacies/views.py:126-127` | "Pending approvals" means `is_approved=False`, which also includes **revoked** pharmacies. | The admin queue mixes new sign-ups with revoked pharmacies. | Add a status field (pending / approved / revoked). | code review | IN CODE |
| N19 | `requests_app/views.py:27` (the only `is_approved` check), `inventory/views.py:20-152`, `requests_app/views.py:108-191` | A revoked pharmacy can still manage stock and answer old requests. Its customers' PENDING requests stay pending forever, and they are not told. | Confusing state after a revoke. | On revoke, notify affected customers and close or cancel open requests. Decide whether a revoked pharmacy can still respond. | docs/ROLE_PERMISSION_MATRIX (via agent check), confirmed in code | IN CODE |
| N20 | `inventory/models.py:67-73` vs `:76-93`; `templates/medicines/search.html:232-235` vs `templates/inventory/list.html:147` | Two freshness rules exist side by side. Public pages warn at >24h (`is_stale`). Pharmacy pages and map pins use 3 tiers (STALE only at >48h). | Users see different "stale" meanings, and the docs contradict each other. | Use one rule (e.g. `freshness_tier`) everywhere. | docs/STOCK_MONITORING_REPORT, PHARMACY_SEARCH_DOCUMENTATION | IN CODE |
| N21 | `inventory/services.py:76-79` | "Add to inventory" for a medicine that is already listed **replaces** the quantity instead of adding to it. The message says so, but SERVICE_LAYER_DOCUMENTATION and BACKEND_ARCHITECTURE_REPORT say it "increments". | Owners may expect +N. | Decide which behaviour is wanted, and match the label and docs. | docs (wrong claim), confirmed in code | IN CODE |
| N22 | `accounts/services.py:103-105` | The "account inactive" branch never runs. Django's `ModelBackend` already returns `None` for inactive users, so they see "Invalid username or password". | Dead code. Inactive users get a misleading message. | Remove it, or use `AllowAllUsersModelBackend` and keep the check. | code review | IN CODE (Django behaviour LIKELY) |
| N23 | `accounts/forms.py:24`, `:102` | The password fields say `min_length=6`, but `MinimumLengthValidator` needs 8. | Mixed error messages. | Use 8, or remove `min_length`. | code review | IN CODE |
| N24 | `accounts/services.py:25-40`, `pharmacies/services.py:216-226`, `requests_app/services.py:23-36`, `:91-100` | Only pharmacy registration uses `transaction.atomic`. Customer registration + welcome notification, toggle + notification, and request create/respond + notification are separate writes. | A failure halfway leaves half-done data, e.g. a user is created but the page shows an error. | Wrap each service in `transaction.atomic()`. | code review; ADMIN_WORKFLOW_TEST_REPORT, SERVICE_LAYER_DOCUMENTATION (wrong "atomic" claims) | IN CODE |
| N25 | `accounts/forms.py:43-44`, `:49-50`, `:137-138`, `:143-144` | Registration says "A user with this email address already exists" / "This username is already taken". | Anyone can find out whether an email is registered. | Accept this for a demo, or use a generic message and rate-limit. | code review | IN CODE |
| N26 | `templates/pharmacies/discovery.html:160`, `templates/pharmacies/detail.html:14`, `pharmacies/services.py:108` | The licence/registration number is shown on public pages, and the public search matches on it. | It exposes internal data, which could be used to impersonate a pharmacy during registration. | Show it only to the owner and admins. Remove it from public search. | code review | IN CODE |
| N27 | `accounts/services.py:42` | The email address is written to the log at registration. CODE_QUALITY_REPORT claims there is no PII in the logs. | Personal data ends up in hosting logs. | Log only the username or id. | docs/CODE_QUALITY_REPORT (wrong claim), confirmed in code | IN CODE |
| N28 | `medicines/models.py:58-65` | No unique constraint on Medicine (name + strength + dosage form). ROLE_PERMISSION_MATRIX claims there is one. | Duplicate catalogue entries split stock across two records. | Add a `UniqueConstraint`. Clean up existing duplicates first. | docs/PROJECT_BASELINE_AUDIT, TECHNICAL_DEBT_REPORT DATA-02 | IN CODE |
| N29 | `requests_app/models.py:20-29` | `pharmacy` and `medicine` on AvailabilityRequest use `CASCADE`. | Deleting a medicine or pharmacy in `/admin/` silently deletes all customers' request history. | Use `PROTECT`, or a soft-delete/archive flag. | code review | IN CODE |
| N30 | `tests/test_admin_portal.py:102-113` | The fixture calls `Inventory.objects.create(..., price=10.00)`. `Inventory` has no `price` field, so it always raises. The bare `except Exception` then sets `cls.inventory` to `.first()` = `None`. | That inventory row is never created, and the error is hidden. Tests in this class run without the stock they appear to set up. | Remove `price=` and the try/except. | code review | IN CODE |
| N31 | `tests/test_discovery.py:297-320` | `test_inventory_freshness_stale_detection` says it checks the stale badge on the search page. It only checks status 200 and `assertNotContains(..., "Unapproved Drugs")` on an unrelated search. | It passes even if the stale badge is broken. | `assertContains(resp, "Reported &gt;24h ago")` on the `StaleMed` search. | code review | IN CODE |
| N32 | `tests/test_security.py:276-285` | The logout test uses `self.client.get(reverse('logout'))`. | It locks in the GET logout behaviour (known #6). Fixing logout to POST will break this test. | Change it to POST when logout is fixed, and add a test that GET returns 405. | code review | IN CODE |
| N33 | (no test) | No test covers popup escaping (N1), re-responding to answered requests (N3), the search status order (known #3), or the home pincode box (N10). | These bugs went unnoticed. | Add regression tests with the fixes. | code review | IN CODE (absence checked by grep) |
| N34 | `medicines/management/commands/seed_data.py:290-296`, `:357-368` | Every run re-saves all stock rows (so all show "Verified Fresh"), and it adds the 3 demo notifications again. | Stale badges can never be demoed. Notifications pile up as duplicates. | Use `get_or_create` for notifications. Optionally backdate some `updated_at` values with `.update()`. | code review | IN CODE |
| N35 | `db.sqlite3` (read in read-only mode) | It confirms the "may contain data" note in section 3: 11 users including a superuser `admin`, 6 pharmacies and 69 stock rows. `.gitignore:3-4` ignores it, but it is in the project folder. | Shipped password hashes and a ready superuser. | Delete it from the submission and rebuild it with `migrate` + `seed_data`. | code review | IN CODE |
| N36 | `config/settings.py:131-140` | With `DEBUG=False`, static files use `CompressedManifestStaticFilesStorage`. | Running locally or running tests with `DEBUG=False` (e.g. after copying `.env.example`) without `collectstatic` makes every `{% static %}` raise "Missing staticfiles manifest entry". | Document it, or use the manifest storage only when `DATABASE_URL` / a production flag is set. | code review | LIKELY |
| N37 | `render.yaml:27` | `CSRF_TRUSTED_ORIGINS` in the production blueprint includes `http://localhost:8000` and the wildcard `https://*.onrender.com`. | The wildcard trusts every other Render app's subdomain for CSRF origin checks. | List only the real site URL. | docs/ENVIRONMENT_AUDIT, PRODUCTION_SECURITY_CHECKLIST | IN CODE |
| N38 | `templates/base.html:17`, `:20`, `:270` | Bootstrap CSS/JS and Bootstrap Icons come from jsDelivr with no `integrity` hash (Leaflet has one, `:23-24`, `:273-274`). | If the CDN is compromised, script runs on every page. | Add SRI hashes, or serve the files locally. | code review | IN CODE |
| N39 | `accounts/context_processors.py:6`, `dashboard/services.py:59`, `accounts/views.py:155`; `templates/medicines/detail.html:67`, `templates/pharmacies/detail.html:65`, `pharmacies/services.py:250` | Small query waste. The unread count runs on every request and is computed again on two pages. `{{ qs.count }}` is used twice per template (an extra COUNT each time). The pharmacy detail stock list is not paginated. | Minor slowdowns that grow with data. | Reuse the processor value, use `|length` after evaluating, and paginate the pharmacy stock. | code review; TECHNICAL_DEBT_REPORT PERF-03 | IN CODE |
| N40 | `accounts/services.py:39` | The welcome notification promises "real-time stock updates". | Another place with the wording from known #4 (not in that list). | Use the same "pharmacy-reported" wording. | code review | IN CODE |
| N41 | `requirements.txt:2` | Pillow is installed but there is no `ImageField` anywhere. | An extra dependency with no use. | Remove it. | docs/DEPENDENCY_AUDIT | IN CODE |
| N42 | project root | There is no `.git` folder. GIT_BACKUP_STRATEGY mentions `scripts/backup_database.py` and `backups/`, which do not exist. `render.yaml:8` uses `plan: free` for Postgres, while DATABASE_BACKUP_AND_RECOVERY only describes backups on paid plans. | No history and no backups. | `git init` and commit. Note that free-plan Postgres has no backups. | docs/GIT_BACKUP_STRATEGY, DATABASE_BACKUP_AND_RECOVERY | IN CODE |

### Issues from docs/ that are still open (confirmed in code)

- Owner is a FK but used as 1:1 → N11 (PROJECT_BASELINE_AUDIT, TECHNICAL_DEBT ARCH-01)
- No coordinate range validation → N8 (TECHNICAL_DEBT DATA-01, PROJECT_BASELINE_AUDIT)
- Search loads all rows into memory → N7 (TECHNICAL_DEBT PERF-01)
- No medicine uniqueness → N28 (TECHNICAL_DEBT DATA-02)
- No request rate limit → N9 (TECHNICAL_DEBT SEC-03)
- Demo credentials on public pages → N2 (TECHNICAL_DEBT SEC-04)
- Email env vars not read, so reset emails are not sent → N6 (ENVIRONMENT_VARIABLES_GUIDE, PASSWORD_MANAGEMENT_REPORT)
- Unread-count query on every request → N39 (TECHNICAL_DEBT PERF-03)
- No medicine delete/archive route (`medicines/urls.py:4-10`) (TECHNICAL_DEBT FEAT-01)
- Phone numbers not validated (`accounts/models.py:13`, `pharmacies/models.py:25`) (TECHNICAL_DEBT DATA-03)
- Medicine detail page shows no distances (`medicines/services.py:171-196`) (TECHNICAL_DEBT UX-01)
- Pillow unused → N41 (DEPENDENCY_AUDIT)
- Django-admin bulk actions skip notifications → N15 (PHARMACY_GOVERNANCE)
- No approval audit trail or rejection reason (`pharmacies/services.py:228` only logs) (ADMIN_SECURITY_REVIEW)
- No git and no backups → N42 (GIT_BACKUP_STRATEGY)
- The known items that docs call "fixed" are **not** fixed: logout is still GET (CUSTOMER_WORKFLOW_TEST_REPORT says POST), the SECRET_KEY fallback is still there (PRODUCTION_SECURITY_CHECKLIST says none), and DEBUG/ALLOWED_HOSTS defaults are still unsafe (FINAL_QA_AUDIT_REPORT BUG-01 calls them "safe").

**Total: 16 docs/ issues still open** (15 items above plus the "claimed fixed but not" group).

### Issues from docs/ that are already fixed or wrong

**Fixed in code:**
- State changes via GET: toggle, cancel and mark-read now use `@require_POST` (`pharmacies/views.py:164`, `requests_app/views.py:195`, `accounts/views.py:188,197`). Logout is the only one left.
- Registration skipped the password validators: now enforced (`accounts/forms.py:60-69`, `:160-169`).
- Duplicate email on profile edit is blocked (`accounts/forms.py:185-189`).
- Missing pagination: added on all list views.
- Repeated count queries: replaced by single aggregates (`inventory/services.py:18-23`, `requests_app/services.py:50-56`, `dashboard/services.py:46-52`).
- Haversine domain error: clamped (`pharmacies/services.py:63`).
- Notifications were auto-marked read on view: no longer.
- `load_dotenv`, security headers, `DATABASE_URL` switch and gunicorn/whitenoise are all in place. DEPENDENCY_AUDIT and ENVIRONMENT_AUDIT are out of date.
- All 15 named indexes exist in the models and migrations.

**Wrong or outdated in the docs:**
- **Test counts:**
  - The docs give 17 / 29 / 43 / 58 / 73 / 86 / 116 / 131 / 136. The code has **136** test functions (counted, not run).
  - FINAL_END_TO_END_QA_REPORT's per-file counts are wrong.
- **Template counts:** the docs say 16 / 22. There are 35.
- **URLs:**
  - `/dashboard/admin/` → `/dashboard/admin-portal/`
  - `/requests/inbox/` → `/requests/pharmacy-inbox/`
  - `/pharmacies/discovery/` → `/pharmacies/`
  - `manage/approval/<id>/` and `admin/<id>/toggle/` → `manage/<pk>/toggle-approval/`
  - `/pharmacies/register/` → `/accounts/register/pharmacy/`
  - `/accounts/password-reset-complete/` → `/accounts/password-reset/complete/`
- **Pharmacy owner relation:** ER_DIAGRAM and DATABASE_ARCHITECTURE describe a 1:1 relation with `related_name='pharmacy'`. The code has a FK with `related_name='pharmacies'`.
- **ROLE_PERMISSION_MATRIX:**
  - It says admins are denied on customer and pharmacy pages; they are allowed.
  - It says an unapproved pharmacy page returns 404; it redirects instead.
  - It says inventory delete is `@require_POST`; it is not, and GET shows a confirm page.
  - It lists medicine catalogue routes that do not exist.
- **XSS-safe claims** (SECURITY_FINAL_REVIEW, ADMIN_SECURITY_REVIEW, LOCATION_DISCOVERY_REPORT) are wrong (N1).
- **Request states:** CONFIRMED and UNAVAILABLE are described as final (CURRENT_ARCHITECTURE, PHARMACY_REQUEST_MANAGEMENT). They are not (N3).
- **Service docs:**
  - "atomic" `register_customer` and "increments" stock are wrong (N21, N24).
  - The return types are out of date.
  - "100% in services" is false: the admin list views query the database directly.
- **Search and freshness:**
  - PHARMACY_SEARCH_DOCUMENTATION says medicine search sorts by distance by default and has name/newest options. It only has "" and "distance" (`medicines/views.py:26`).
  - The stale badge text is ">24h", not ">48h".
- **Haversine:**
  - HAVERSINE_IMPLEMENTATION's sample distances (6.71 km, 501.50 km) do not match the code's formula (6.69, 499.99).
  - The `delta=0.5` tolerance in `tests/test_location_discovery.py:171` hides the gap.
- **Location privacy:** LOCATION_DISCOVERY says user coordinates are never in the HTML. They are, in `json_script` (`templates/medicines/search.html:354`).
- **Settings defaults:** ENVIRONMENT_VARIABLES_GUIDE says the HSTS default is 0 and SSL redirect is off. With DEBUG=False they are 31536000 and True (`config/settings.py:163-164`).
- **Features that do not exist:** "AJAX search", "caching" and "request-trend charts" (SYSTEM_ARCHITECTURE and the test reports).
- **Color palette:** the colours in IMPLEMENTATION_PLAN and SYSTEM_ARCHITECTURE do not match `static/css/styles.css`.

**Docs that contradict each other:** test totals; template counts; who can approve (superuser only vs the ADMIN-role portal); freshness threshold (24h vs 48h); query-count "before/after" numbers (QUERY_OPTIMIZATION vs ORM_OPTIMIZATION vs BACKEND_ARCHITECTURE); PBKDF2 iterations (600k vs 720k); backup method (a plain file copy is "safe" vs "dangerous").

### Suggested fix order

1. **N1** XSS in map popups, and **N2** hide demo credentials (together with known #1 and #2 settings/seed_data).
2. **N3 + N4** lock the request state: respond only while PENDING, with an atomic conditional update.
3. **N5** set approval instead of toggling it; **N15** route admin bulk actions through the service.
4. **N10, N12, N13** small visible fixes before a demo (home pincode box, stray `} }`, footer link), together with known #3 (search order).
5. **N6** read the EMAIL_* env vars so password reset works on Render.
6. **N8, N28, N11** data integrity: coordinate validators, medicine unique constraint, owner one-to-one.
7. **N9** request duplicate check and rate limit; **N16** tighten role checks.
8. **N7** database-side pagination and bounding-box distance filter.
9. **N30–N33** fix the broken or weak tests and add regression tests for the items above.
10. The remaining Low items, then update or delete the outdated docs in `docs/`.

---

## Fix log

Fixes made on branch `fix/all` (2026-11-22), one commit per phase. As instructed, **no tests were run** and no new tests were written. Existing tests that the fixes would break were updated, but they were not run. Checks that were run: `python manage.py check` (no issues), `python manage.py makemigrations --check` (no changes), and `migrate` on a **copy** of `db.sqlite3` (all 6 new migrations applied; 5 pharmacies became APPROVED, 1 PENDING). The real `db.sqlite3` was not touched.

| Commit | Phase | Findings |
|---|---|---|
| `bf3dcea`, `af04651` (earlier) | Step 0, first N1 pass | `*:Zone.Identifier` ignored and untracked; popup values escaped |
| `ba2c406` (earlier) | Test fixture | N30 |
| Phase 1 | Security | N1 (DOM nodes + `textContent`, `data-*` instead of `escapejs` in `onclick`), N2, known #1, #2, #6, #7, N12, N27, N32, N36, N37, N38 |
| Phase 2 | Requests and approval | N3, N4, N5, N9, N15, N18, N19, N24, N29, known #5 |
| Phase 3 | Data and permissions | N8, N11, N16, N21, N22, N23, N26, N28, phone validation, medicine archive |
| Phase 4 | Search, wording, UX, speed | known #3, #4, N7, N10, N13, N14, N17, N20, N31, N34, N39, N40, "Low Stock (1–10 units)" label |
| Phase 5 | Deployment and cleanup | N6, N41, N35 (documented), N42, README.md, docs/README_DOCS_STATUS.md |

Decisions applied:
- A request can be answered only once, while it is PENDING (conditional `UPDATE ... WHERE status='PENDING'` in `transaction.atomic()`).
- Add-stock keeps "replace quantity". The field is labelled "Set quantity" and the help text says it replaces.
- Registration "already exists" messages are unchanged (N25).
- An approved pharmacy that changes name, address, city, pincode or lat/lng goes back to PENDING (`apply_pharmacy_profile_update`).
- A revoked pharmacy cannot add, edit or delete stock or respond to requests. On revoke, its PENDING requests are cancelled and the customers are notified.
- Login rate limiting: a simple cache-based counter in `accounts/views.py` (5 failed attempts per IP or per username, then blocked for 15 minutes, HTTP 429). No extra dependency. It uses Django's default local-memory cache, so the limit applies per process.
- Approval status: a new `Pharmacy.approval_status` (PENDING / APPROVED / REVOKED). `is_approved` is kept in sync so public filters still work.

New migrations (run `python manage.py migrate` on Render; `build.sh` already does this):
`accounts.0003_alter_user_phone_number`, `inventory.0003_inventory_low_stock_label`, `medicines.0003_medicine_is_active_and_more`, `pharmacies.0003_pharmacy_approval_status` (with data backfill), `pharmacies.0004_alter_pharmacy_latitude_alter_pharmacy_longitude_and_more` (owner becomes OneToOne), `requests_app.0003_availabilityrequest_protect_fks`.

Pre-checks on the current `db.sqlite3` (read-only): no duplicate medicines (N28), no owner with two pharmacies (N11), no coordinates out of range (N8).

## Status of all findings

| ID | Status | Notes |
|---|---|---|
| Known #1 | Fixed | DEBUG defaults to False; `ImproperlyConfigured` if `SECRET_KEY` is missing and DEBUG is off; no `*` host default; local `.env` with `DEBUG=True` still works; local-safe `.env.example` and new `.env.production.example`. |
| Known #2 | Fixed | `seed_data` raises `CommandError` when DEBUG is False. |
| Known #3 | Fixed | Explicit `Case/When` rank (In Stock, Low Stock, Out of Stock) in search and medicine detail. |
| Known #4 | Fixed | "Live Stock", "Real-time", "Verified Fresh" replaced with "Pharmacy-reported · updated X ago" wording. |
| Known #5 | Fixed | Sensitive profile changes send an approved pharmacy back to PENDING, with an owner notification. |
| Known #6 | Fixed | Logout is POST only (form in `base.html`). Login rate limit via the cache (see Fix log). |
| Known #7 | Fixed | Generic messages for users; details go to the log with `logger.exception`. |
| Low Stock label | Fixed | "Low Stock (1–10 units)". |
| N1 | Fixed | `buildPopup()` builds DOM nodes with `textContent` on all 4 map pages; "Pin on Map" uses `data-*` attributes. Other templates checked: no raw pharmacy fields in JS. |
| N2 | Fixed | Demo logins shown only when `settings.DEBUG` is True (base, home, login). |
| N3 | Fixed | Respond only while PENDING; "Respond" hidden for answered requests. |
| N4 | Fixed | Conditional update in `transaction.atomic()` for respond and cancel. |
| N5 | Fixed | Explicit `action=approve|revoke`, idempotent, clearer wording. |
| N6 | Fixed | All `EMAIL_*`, `DEFAULT_FROM_EMAIL` and `SERVER_EMAIL` are read from env; placeholders in `render.yaml`. |
| N7 | Fixed | Database-side filtering, Haversine distance expression, ordering and pagination; bounding box before the distance filter; map pins only for the current page (max 100). An empty search loads one page. |
| N8 | Fixed | Model validators (±90 / ±180) used by all 3 forms; pins use `is_valid_coordinate()`, so 0 is kept. |
| N9 | Fixed | No duplicate PENDING request; an Inventory row is required; per-customer limit of 10 requests per 60 minutes. |
| N10 | Fixed | Digits in the home "City or Pincode" box are used as a pincode (handled in the search views). |
| N11 | Fixed | `Pharmacy.owner` is a `OneToOneField` (`related_name='pharmacy'`); `get_pharmacy_for_user` uses `user.pharmacy`. |
| N12 | Fixed | Stray `} }` removed. |
| N13 | Fixed | Footer link points to `pharmacy_discovery`. |
| N14 | Fixed | Exact pincode match. |
| N15 | Fixed | Django-admin actions call `set_pharmacy_approval`; approval fields are read-only in the admin form. |
| N16 | Fixed | `is_staff` alone no longer means app admin; `@customer_required` on the customer dashboard; decorators use `redirect_to_login` (`?next=`). Admins can still open customer and pharmacy pages (unchanged on purpose). |
| N17 | Fixed | `TIME_ZONE = 'Asia/Kolkata'`. |
| N18 | Fixed | `approval_status` field with data migration; admin queue, filters and dashboard counts use it. |
| N19 | Fixed | On revoke, PENDING requests are cancelled and customers notified; a revoked pharmacy cannot change stock or respond. |
| N20 | Fixed | One rule: `is_stale` is derived from `freshness_tier` (over 24h). |
| N21 | Fixed | "Set quantity" label and help text. The docs that say "increments" are listed in `docs/README_DOCS_STATUS.md` (docs/ files were not edited). |
| N22 | Fixed | Dead inactive-account branch removed. |
| N23 | Fixed | `min_length=8`. |
| N24 | Fixed | `transaction.atomic()` around customer registration, approval, and request create/respond. |
| N25 | Skipped | Decision: keep the "already exists" messages. |
| N26 | Fixed | Licence number shown only to the owner and admins; removed from public search. |
| N27 | Fixed | Registration log line has username and id, no email. |
| N28 | Fixed | Case-insensitive `UniqueConstraint` (name, strength, dosage form). No existing duplicates. |
| N29 | Fixed | `PROTECT` on `AvailabilityRequest.pharmacy` and `.medicine` (migration). |
| N30 | Fixed | Earlier commit `ba2c406`. |
| N31 | Fixed | The stale-badge test also checks that the badge is absent for fresh items and that the fresh wording is absent for the stale item. |
| N32 | Fixed | Logout tests use POST; `test_security` also checks that GET returns 405. |
| N33 | Skipped | Instructions for this pass: no new tests. Regression tests for N1 and N2 already exist (`tests/test_xss_map_popups.py`, `tests/test_demo_logins.py`). N3, known #3 and N10 still have no dedicated test. |
| N34 | Fixed | `get_or_create` for notifications; unchanged stock is not re-saved; some rows backdated (30h / 60h / 72h) to demo the badges. |
| N35 | Skipped (by instruction) | `db.sqlite3` was not deleted. README explains how to rebuild it: back it up, `migrate`, `seed_data`. |
| N36 | Fixed | Manifest storage only when deployed (`DATABASE_URL` set) or `USE_MANIFEST_STATIC=True`; otherwise WhiteNoise serves from the finders. |
| N37 | Fixed | `render.yaml` lists only the real origin (placeholder `https://medifind.onrender.com`). |
| N38 | Fixed | SRI on Bootstrap CSS/JS and Bootstrap Icons; Chart.js pinned to 4.4.1 with SRI. |
| N39 | Fixed | Unread count computed once per request and reused; `|length` instead of a double `.count`; pharmacy detail stock list paginated (20 per page). |
| N40 | Fixed | Welcome notification uses "pharmacy-reported" wording. |
| N41 | Fixed | Pillow removed; all packages pinned to the versions installed in the venv. |
| N42 | Fixed | The project is now in git with history. README notes that free Render Postgres has no backups. |
| docs: phone validation | Fixed | Lenient validator (7–15 digits; `+`, spaces, dashes, brackets) on User and Pharmacy phones and the owner phone. |
| docs: medicine archive | Fixed | `Medicine.is_active`; archived medicines are hidden from public search, the medicine detail page, the add-stock form and new requests. |
| docs: medicine detail distances | Skipped | Not a tiny change. |
| docs: approval audit trail / rejection reason | Open | Only log lines and owner notifications; no stored history or reason. |
| docs: outdated docs | Open | Listed in `docs/README_DOCS_STATUS.md`; no file in `docs/` was edited or deleted. |
