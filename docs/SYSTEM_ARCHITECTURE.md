# Architecture and code map

**Purpose:** How the code is organised, how one web request flows through it, and where to find things.
**Who it is for:** Beginners reading the code for the first time, and examiners asking "how does it work?".
**Last verified:** 2026-11-22 against commit `dd2f32c`.

## 1. The big picture

MediFind is one Django project (a "monolith": one program, one database), with server-rendered HTML.

- **Back end:** Python 3.11, Django 5.2.19. Package versions are pinned in `requirements.txt`.
- **Database:** SQLite file `db.sqlite3` locally; PostgreSQL in production when `DATABASE_URL` is set.
- **Front end:** Django templates with Bootstrap 5.3.3, Bootstrap Icons, Leaflet 1.9.4 maps with
  OpenStreetMap tiles, and Chart.js 4.4.1. These come from CDNs with SRI hashes (a checksum the browser
  verifies). There is no React and no AJAX search; every filter reloads the page.
- **Production server:** Gunicorn (runs the Django app) and WhiteNoise (serves CSS/JS files).

## 2. Folder map

| Folder / file | What is in it |
|---|---|
| `config/` | `settings.py` (all settings, read from environment variables), `urls.py` (top-level URL list) |
| `accounts/` | Custom `User` model with a `role`, registration, login/logout, profile, notifications pages, role decorators (`decorators.py`), phone and pincode validators (`validators.py`) |
| `medicines/` | `Medicine` catalogue, public search and detail pages, admin catalogue pages, the `seed_data` command (`management/commands/seed_data.py`) |
| `pharmacies/` | `Pharmacy` model, directory and detail pages, profile edit, admin approval/users/requests pages, distance helpers |
| `inventory/` | `Inventory` (stock of one medicine at one pharmacy), the owner's stock pages |
| `requests_app/` | `AvailabilityRequest` and `Notification` models, request create/list/inbox/respond/cancel |
| `dashboard/` | Home page and the three role dashboards (no models of its own) |
| `templates/` | 35 HTML templates (+1 text template for the reset-email subject), one folder per app, `base.html` is the shared layout |
| `static/` | `css/styles.css`, `js/map_popup.js` (safe map popups), images, and `admin/js/admin/RelatedObjectLookups.js` (a patched copy of a Django admin file) |
| `tests/` | Unit/integration tests run with Django's test runner |
| `e2e/` | Browser tests with Playwright (see [TESTING_REPORT.md](TESTING_REPORT.md)) |
| `render.yaml`, `build.sh`, `Procfile` | Deployment (see [PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md)) |

Each app follows the same pattern:

| File | Job |
|---|---|
| `models.py` | Database tables (Django "models" are Python classes that map to tables) |
| `urls.py` | Which URL calls which view |
| `views.py` | Reads the HTTP request, checks the role, calls a service, picks a template |
| `services.py` | Business rules and database queries (the "service layer") |
| `forms.py` | Input validation for HTML forms |
| `admin.py` | How the model appears in Django admin (`/admin/`) |

Not everything goes through services: the admin list pages (`pharmacies/views.py:138` and below) and the
customer request list query the database in the view.

## 3. How one request travels (example: searching "Dolo")

1. The browser asks for `GET /medicines/search/?q=Dolo&city=Hyderabad`.
2. `config/urls.py` sends `medicines/...` to `medicines/urls.py`, which maps `search/` to
   `search_medicines_view` (`medicines/views.py:14`).
3. The view reads the query parameters. If the city box holds only digits, it is treated as a pincode.
4. The view calls the service `search_medicine_inventory()` (`medicines/services.py:30`). The service:
   - starts from stock rows of **approved** pharmacies and **active** medicines;
   - applies the text search and filters;
   - adds a stock rank (In Stock = 0, Low = 1, Out = 2) and, if the user's location was sent,
     a distance computed **in the database**;
   - orders and paginates in the database (10 per page) and builds map pins for that page only.
5. The view puts the results in a "context" (a dictionary) and renders `templates/medicines/search.html`.
6. The template extends `base.html`. Map data is passed to JavaScript with Django's `json_script`
   filter (JSON inside a `<script type="application/json">` tag), and popups are built by
   `buildPopup()` in `static/js/map_popup.js` with `textContent`, so names typed by pharmacies are
   never treated as HTML.
7. On every page, two "context processors" (functions that add variables to all templates) run:
   the unread notification count and `show_demo_logins` (`accounts/context_processors.py`).

A POST works the same way, except that the view first validates a form and usually redirects after
success, with a flash message from `django.contrib.messages`.

## 4. Services by app

| Service file | Main functions |
|---|---|
| `accounts/services.py` | `register_customer`, `register_pharmacy` (user + pharmacy + notification in one transaction), `authenticate_user`, `mark_notification_as_read`, `mark_all_notifications_as_read` |
| `medicines/services.py` | `search_medicine_inventory`, `get_search_filter_options`, `get_medicine_detail_data` |
| `pharmacies/services.py` | `is_valid_coordinate`, `calculate_haversine_distance`, `bounding_box`, `haversine_expression`, `paginate`, `discover_nearby_pharmacies`, `get_pharmacy_for_user`, `set_pharmacy_approval`, `apply_pharmacy_profile_update`, `get_pharmacy_detail_data` |
| `inventory/services.py` | `get_inventory_counts`, `get_filtered_inventory`, `add_or_update_inventory` (sets, does not add to, the quantity), `delete_inventory_item` |
| `requests_app/services.py` | `create_availability_inquiry`, `respond_to_availability_inquiry`, `cancel_availability_inquiry`, `get_pharmacy_inbox_counts` |
| `dashboard/services.py` | `get_home_page_metrics` and one `get_*_dashboard_metrics` per role |

Counts on dashboards and inboxes use one `aggregate()` query with conditional `Count(..., filter=Q(...))`
instead of one query per status.

## 5. Distance and the map

- **Haversine formula:** the straight-line ("great circle") distance between two latitude/longitude
  points on a sphere of radius 6371 km. It is not road distance.
- The Python version `calculate_haversine_distance()` (`pharmacies/services.py:35`) rounds to 2 decimals
  and returns `None` for missing or invalid coordinates.
- For filtering and sorting, the same formula is built as a **database expression**
  (`haversine_expression()`, `pharmacies/services.py:91`), so radius filter, ordering and pagination run
  in the database. A cheap latitude/longitude box (`bounding_box()`) is applied first.
- The user's location comes from the browser (the HTML5 Geolocation API) only after the user allows it.
  It is sent as `lat`/`lng` in the URL and also appears in the page (in `json_script`) to draw the
  user's pin. It is not stored in the database.
- Pharmacies without coordinates have no pin and no distance. On the search page at most 100 pins are
  drawn, one per pharmacy, for the current page.

## 6. Front end

- `templates/base.html`: navbar (role-aware menu, notification bell, Sign Out form), disclaimer banner,
  footer, CDN links.
- `static/css/styles.css`: design tokens as CSS variables, for example `--med-primary: #102A43`,
  `--med-secondary: #0EA5A4`, `--med-success: #16A34A`, `--med-warning: #F59E0B`,
  `--med-danger: #DC2626`; font "Plus Jakarta Sans".
- Charts: the admin dashboard bar chart (medicines per category) and the pharmacy dashboard doughnut
  chart (stock status). Data is passed with `json_script`.
- Layout uses the Bootstrap grid; the navbar collapses into a menu button on small screens.

## 7. Where do I find …?

| I want to see … | Look in |
|---|---|
| Who may open a page | the decorator above the view; decorators are in `accounts/decorators.py` |
| How "In Stock / Low / Out" is decided | `Inventory.save()` in `inventory/models.py:52` |
| The freshness rule (24h / 48h) | `inventory/models.py:66-99` |
| The search order | `STOCK_RANK` in `medicines/services.py:22` |
| Approve / revoke | `set_pharmacy_approval()` in `pharmacies/services.py:286` |
| Re-approval after a profile edit | `apply_pharmacy_profile_update()` in `pharmacies/services.py:333` |
| Request rules (duplicate, rate limit) | `create_availability_inquiry()` in `requests_app/services.py:23` |
| "Answered once" | `respond_to_availability_inquiry()` in `requests_app/services.py:108` |
| Login rate limit | `login_view()` and helpers in `accounts/views.py:78-152` |
| All settings and their defaults | `config/settings.py` and [ENVIRONMENT_VARIABLES_GUIDE.md](ENVIRONMENT_VARIABLES_GUIDE.md) |
| Demo data | `medicines/management/commands/seed_data.py` |
| Safe map popups | `static/js/map_popup.js` |
