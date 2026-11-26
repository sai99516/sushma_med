# MediFind – Presentation Pack

Matches the code on branch `fix/manual-testing` (2026-11-26). The demo script below is also an automated
browser test (`e2e/test_00_demo_script.py`), which passed in the last full run (197 unit tests and 70
browser tests, all passed). Run the tests yourself before quoting numbers (see section 6, Q11).
Diagrams for the slides: [docs/diagrams/](docs/diagrams/); screenshots: [docs/screenshots/](docs/screenshots/).

---

## 1. Quick start (local)

```bash
python3.11 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # local-safe: DEBUG=True, SQLite, console email
python manage.py migrate
python manage.py seed_data          # demo data (only runs with DEBUG=True)
python manage.py runserver          # open http://127.0.0.1:8000
```

For a clean demo, start from a fresh database with `bash scripts/reset_demo.sh` (it keeps a backup of the
old one); otherwise Metro Life may already be approved from an earlier run.

**Demo logins** (from `medicines/management/commands/seed_data.py`; shown on the page only when DEBUG=True):

| Role | Username | Password |
|---|---|---|
| Admin (superuser) | `admin` | `admin123` |
| Customers | `customer1`, `customer2`, `customer3` | `password123` |
| Pharmacy owners (approved) | `apollo_owner`, `medplus_owner`, `wellness_owner`, `netmeds_owner`, `care_owner` | `password123` |
| Pharmacy owner (**pending**) | `pending_owner` | `password123` |

Seed data: 6 pharmacies in Hyderabad, Bengaluru and New Delhi (5 approved, 1 pending), 31 medicines,
69 stock rows (some backdated 30h, 60h and 72h to show the freshness badges) and 4 requests.

## 2. Features by role

**Anyone (not logged in)**
- Home page with counts of approved pharmacies, medicines and in-stock listings. Digits typed in the
  "City or Pincode" box search by pincode.
- Medicine search: name, category, dosage form, strength, city, pincode, stock status. With the
  browser's location: radius (5–50 km) and sort by nearest. Results are ordered In Stock, Low Stock,
  Out of Stock. List and map view.
- Medicine detail page ("Use my location" adds distances, nearest first) and pharmacy directory
  (`/pharmacies/`), each with a Leaflet map.
- Every result shows "Reported: <date> (X ago)"; reports older than 24h get a "confirm" badge.

**Customer**
- Register, log in, Sign Out (button), edit profile, change or reset password.
- Availability request (customers only; quantity 1–1000 + note) to an approved pharmacy that lists the medicine. No
  duplicate pending request for the same medicine and pharmacy; at most 10 requests per hour.
- "My Requests" with status tabs (including Partially Available, e.g. "60 of 100 available"); cancel while
  pending. Cancelled requests say why (by the customer, medicine removed, pharmacy no longer approved).
  Notifications page and dashboard.

**Pharmacy owner**
- Register the pharmacy (licence number, 6-digit pincode, optional map coordinates). It starts as
  **Pending** and is hidden until an admin approves it. One pharmacy per owner.
- Inventory: add from the catalogue ("Set quantity" replaces the number), edit, delete (cancels that
  medicine's pending requests); search, filter, sort.
  Status is automatic: more than 10 = In Stock, 1–10 = Low Stock, 0 = Out of Stock.
- Freshness tiers: within 24h, 24–48h, over 48h ("confirm before visiting").
- Request inbox: answer once with Confirm, Partially Available (how many units) or Unavailable, plus a
  message; the customer is notified. Opening a request marks its "new request" notification read.
- Dashboard with a stock chart. Changing name, address or location sends the pharmacy back to Pending.

**Admin**
- Admin dashboard: counts, pending approvals, recent requests, medicines-per-category chart.
- Approve or revoke pharmacies (Pending / Approved / Revoked), with an optional reason. Revoking cancels
  the pharmacy's pending requests and notifies everyone affected. Every change is kept in an approval
  history shown to the owner and admins.
- Medicine catalogue: add, edit, archive (no delete). Users list and all-requests monitor (with a Partially Available filter). Django admin at `/admin/`.

## 3. Demo script (about 5 minutes)

| Time | Who | Do this | URL |
|---|---|---|---|
| 0:00 | Visitor | Show the home page and the disclaimer banner at the top | `/` |
| 0:30 | Visitor | Search "Dolo"; show the results (In Stock first), the "Reported … ago" text and the map | `/medicines/search/?q=Dolo` |
| 1:00 | Admin | Log in as `admin`; show the dashboard and the pending pharmacy | `/accounts/login/` → `/dashboard/admin-portal/` |
| 1:30 | Admin | Approve "[DEMO] Metro Life Pharmacy" with the **Approve** button | `/pharmacies/manage/list/?status=pending` |
| 2:00 | Pharmacy | Sign Out (user menu), log in as `pending_owner`; show the approval notification | `/accounts/notifications/` |
| 2:20 | Pharmacy | Add Dolo 650 with 25 units; it shows as "In Stock" | `/inventory/add/` → `/inventory/` |
| 3:00 | Customer | Log in as `customer1` and search "Dolo"; Metro Life now appears | `/medicines/search/?q=Dolo` |
| 3:20 | Customer | Click "Request Availability" and send 2 units with a note | `/requests/create/<pharmacy_id>/<medicine_id>/` |
| 3:50 | Pharmacy | Log in as `pending_owner`, open the inbox, **Respond** → confirm with a message. The row now shows "Answered" | `/requests/pharmacy-inbox/` → `/requests/<id>/respond/` |
| 4:30 | Customer | Log in as `customer1`; the request shows "Confirmed Available" with the message, plus the notification | `/requests/my-requests/` |
| 5:00 | – | End on the disclaimer: the stock is reported by the pharmacy, not checked by MediFind | – |

Tips:
- Use two browsers (or one private window) to avoid logging out and in.
- Optional extra: as `admin`, open Metro Life's pharmacy page and show the approval history.
- Optional extra (partial answer): send a request for 100 units; as the owner choose **Partially Available**
  and enter 60. The customer sees "60 of 100 available".
- Optional extra (1 minute): as `pending_owner`, change the pharmacy address in the profile. It goes back
  to Pending and disappears from search until the admin approves it again.

## 4. Presentation outline (8 slides)

1. **Problem**
   - Patients go from shop to shop looking for a medicine.
   - There is no simple way to see which nearby pharmacy reports having it.
   - Phoning each shop takes time, especially when the need is urgent.
2. **Solution**
   - One search for a medicine across approved local pharmacies.
   - Pharmacies update their own stock; every result shows when it was last reported.
   - Customers ask the pharmacy to confirm before they travel.
3. **Tech stack**
   - Python 3.11, Django 5.2, SQLite (local) / PostgreSQL (production).
   - Bootstrap 5, Leaflet maps (OpenStreetMap), Chart.js; server-rendered Django templates.
   - Gunicorn + WhiteNoise, deployed with a Render Blueprint (`render.yaml`, `build.sh`).
4. **Architecture**
   - Six Django apps: accounts, pharmacies, medicines, inventory, requests_app, dashboard.
   - URL → view (role check) → `services.py` (business rules) → template.
   - 7 models: User (role), Pharmacy, PharmacyApprovalLog, Medicine, Inventory, AvailabilityRequest,
     Notification (19 migrations). Show `docs/diagrams/architecture.png` and `er_diagram.png`.
5. **Main features**
   - Search with filters and distance (Haversine, computed in the database), with a map.
   - Pharmacy approval with three states; only approved pharmacies are public.
   - Automatic stock status, freshness wording; request → answer once (confirm / partial / unavailable) → notification.
6. **Demo** (section 3).
7. **Testing and security**
   - 197 unit/integration tests and 70 browser tests (Playwright); lint and CI on every push.
   - Role checks plus owner-scoped queries (404 for other users' data), POST-only actions, CSRF,
     login rate limit, safe map popups, safe production defaults.
8. **Limitations and future work** (section 5).

## 5. Limitations and future work (honest list)

**Limitations**
- Stock is **reported by the pharmacy**; the app cannot check it. A result is not a reservation.
- No automatic sync: stock changes only when the owner edits it.
- No payment, ordering, reservation or prescription upload; no mobile app.
- Notifications are in-app only. Email is used only for password reset, and only after the `EMAIL_*`
  variables are set on the server.
- Distance is a straight line (Haversine), not road distance. Pharmacies without coordinates have no
  distance.
- The login rate limit is per server process (in-memory cache).
- No external security test has been done. Not medical advice.

**Future work**
- Connect to pharmacy billing (POS) systems for automatic stock updates; stock history and expiry dates.
- Email/SMS alerts when a request is answered or stock comes back.
- Road distance and directions; a mobile app or installable web app.
- A shared cache (for example Redis) for the rate limit; one real deployment with monitoring.

## 6. Likely questions (short answers)

1. **How do you stop one pharmacy from editing another's stock?**
   Edit and delete look the row up together with the logged-in owner's pharmacy
   (`get_object_or_404(..., pharmacy=pharmacy)`, `inventory/views.py:120` and `:156`). Anything else is 404.
2. **How do you know the stock is correct?**
   We don't. It is reported by the pharmacy. We show when it was last updated, warn after 24h, and let
   the customer ask the pharmacy to confirm.
3. **How is "In Stock / Low / Out" decided?**
   In `Inventory.save()`: more than 10 is In Stock, 1–10 Low Stock, 0 Out of Stock (`inventory/models.py:52`).
4. **How is the search ordered?**
   By an explicit rank: In Stock, Low Stock, Out of Stock, then newest update (`STOCK_RANK`,
   `medicines/services.py:22`). With location, "sort by distance" puts the nearest first.
5. **How do you calculate distance?**
   Haversine formula on the browser's location and the pharmacy's latitude/longitude. In Python
   (`pharmacies/services.py:37`) and as a database expression for filtering and sorting (`:93`).
6. **Why must pharmacies be approved, and what if one changes its address?**
   To keep fake pharmacies out. Public queries filter on approval. Changing name, address or location
   sends an approved pharmacy back to Pending (`pharmacies/services.py:346`). A revoked pharmacy is hidden
   and cannot change stock or answer requests. Every
   change is stored with who, when and an optional reason (`PharmacyApprovalLog`, `pharmacies/models.py:134`).
7. **How are roles handled?**
   `User.role` plus decorators in `accounts/decorators.py`. Admin = role ADMIN or superuser
   (`accounts/models.py:31`); `is_staff` alone is not enough. Admins may also open customer pages.
8. **Can a pharmacy change its answer, or answer a cancelled request?**
   No. Only a PENDING request can change, through a conditional database update in a transaction
   (`requests_app/services.py:114`).
9. **Is it safe against CSRF, SQL injection and XSS?**
   CSRF middleware and tokens on every POST form; ORM only, no raw SQL; templates auto-escape, map data
   goes through `json_script`, and popups use `textContent` (`static/js/map_popup.js`). Tested with a
   stored XSS payload in the browser tests. No external penetration test yet.
10. **What stops someone guessing passwords?**
    5 failed logins per IP + username (20 per IP) are blocked for up to 15 minutes with HTTP 429
    (`accounts/views.py:121`). Behind Render's proxy the real client IP is taken from `X-Forwarded-For`
    (`TRUSTED_PROXY_COUNT=1`).
11. **How did you test it?**
    197 Django tests (`python manage.py test tests`) and 70 Playwright browser tests (`python -m pytest e2e`)
    that fail on any console error. Details in `docs/TESTING.md`.
12. **What database do you use?**
    SQLite locally, PostgreSQL in production; `DATABASE_URL` decides.
13. **What would you improve first?**
    Automatic stock sync with pharmacy systems, email/SMS alerts, and road distance.

## 7. Checks before presenting

1. Run `python manage.py test tests` (and, if time allows, `python -m pytest e2e`) on the presenting machine.
2. Run `bash scripts/reset_demo.sh`, so Metro Life is pending again.
3. Make sure `.env` has `DEBUG=True` (the demo logins and `seed_data` need it).
4. Open two browsers (one normal, one private) before starting.
