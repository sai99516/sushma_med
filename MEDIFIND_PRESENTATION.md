# MediFind – Presentation Pack

Matches the code at commit `dd2f32c` (2026-11-22). The demo script below is also an automated browser
test (`e2e/test_00_demo_script.py`), which passed in the last full browser run recorded in
`MEDIFIND_REVIEW.md`. Run the tests yourself before quoting numbers (see section 6, Q11).

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

For a clean demo, start from a fresh database (see `docs/DATABASE_ARCHITECTURE.md`, "Rebuilding the
local database"); otherwise Metro Life may already be approved from an earlier run.

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
- Medicine detail page and pharmacy directory (`/pharmacies/`), each with a Leaflet map.
- Every result shows "Reported: <date> (X ago)"; reports older than 24h get a "confirm" badge.

**Customer**
- Register, log in, Sign Out (button), edit profile, change or reset password.
- Availability request (quantity 1–1000 + note) to an approved pharmacy that lists the medicine. No
  duplicate pending request for the same medicine and pharmacy; at most 10 requests per hour.
- "My Requests" with status tabs; cancel while pending. Notifications page and dashboard.

**Pharmacy owner**
- Register the pharmacy (licence number, 6-digit pincode, optional map coordinates). It starts as
  **Pending** and is hidden until an admin approves it. One pharmacy per owner.
- Inventory: add from the catalogue ("Set quantity" replaces the number), edit, delete; search, filter, sort.
  Status is automatic: more than 10 = In Stock, 1–10 = Low Stock, 0 = Out of Stock.
- Freshness tiers: within 24h, 24–48h, over 48h ("confirm before visiting").
- Request inbox: confirm or decline once, with a message; the customer is notified.
- Dashboard with a stock chart. Changing name, address or location sends the pharmacy back to Pending.

**Admin**
- Admin dashboard: counts, pending approvals, recent requests, medicines-per-category chart.
- Approve or revoke pharmacies (Pending / Approved / Revoked). Revoking cancels the pharmacy's pending
  requests and notifies everyone affected.
- Medicine catalogue: add, edit, archive (no delete). Users list and all-requests monitor. Django admin at `/admin/`.

## 3. Demo script (about 5 minutes)

| Time | Who | Do this | URL |
|---|---|---|---|
| 0:00 | Visitor | Show the home page and the disclaimer banner at the top | `/` |
| 0:30 | Visitor | Search "Dolo"; show the results (In Stock first), the "Reported … ago" text and the map | `/medicines/search/?q=Dolo` |
| 1:00 | Admin | Log in as `admin`; show the dashboard and the pending pharmacy | `/accounts/login/` → `/dashboard/admin-portal/` |
| 1:30 | Admin | Approve "[DEMO] Metro Life Pharmacy (Pending Review)" with the **Approve** button | `/pharmacies/manage/list/?status=pending` |
| 2:00 | Pharmacy | Sign Out (user menu), log in as `pending_owner`; show the approval notification | `/accounts/notifications/` |
| 2:20 | Pharmacy | Add Dolo 650 with 25 units; it shows as "In Stock" | `/inventory/add/` → `/inventory/` |
| 3:00 | Customer | Log in as `customer1` and search "Dolo"; Metro Life now appears | `/medicines/search/?q=Dolo` |
| 3:20 | Customer | Click "Request Availability" and send 2 units with a note | `/requests/create/<pharmacy_id>/<medicine_id>/` |
| 3:50 | Pharmacy | Log in as `pending_owner`, open the inbox, **Respond** → confirm with a message. The row now shows "Answered" | `/requests/pharmacy-inbox/` → `/requests/<id>/respond/` |
| 4:30 | Customer | Log in as `customer1`; the request shows "Confirmed Available" with the message, plus the notification | `/requests/my-requests/` |
| 5:00 | – | End on the disclaimer: the stock is reported by the pharmacy, not checked by MediFind | – |

Tips:
- Use two browsers (or one private window) to avoid logging out and in.
- "(Pending Review)" is part of the seeded pharmacy's **name**; it stays in the name after approval.
  The status is shown separately.
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
   - Models: User (role), Pharmacy, Medicine, Inventory, AvailabilityRequest, Notification.
5. **Main features**
   - Search with filters and distance (Haversine, computed in the database), with a map.
   - Pharmacy approval with three states; only approved pharmacies are public.
   - Automatic stock status, freshness wording; request → answer once → notification.
6. **Demo** (section 3).
7. **Testing and security**
   - 160 unit/integration tests and 68 browser tests (Playwright).
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
  distance. The medicine detail page shows no distances.
- The login rate limit is per server process (in-memory cache).
- No stored approval history and no rejection reason (only log lines and notifications).
- Admins can also send availability requests; deleting a stock row leaves its pending requests open.
- No external security test has been done. Not medical advice.

**Future work**
- Connect to pharmacy billing (POS) systems for automatic stock updates; stock history and expiry dates.
- Email/SMS alerts when a request is answered or stock comes back.
- Road distance and directions; a mobile app or installable web app.
- An approval audit log with reasons; a shared cache (for example Redis) for the rate limit.

## 6. Likely questions (short answers)

1. **How do you stop one pharmacy from editing another's stock?**
   Edit and delete look the row up together with the logged-in owner's pharmacy
   (`get_object_or_404(..., pharmacy=pharmacy)`, `inventory/views.py:119` and `:155`). Anything else is 404.
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
   (`pharmacies/services.py:35`) and as a database expression for filtering and sorting (`:91`).
6. **Why must pharmacies be approved, and what if one changes its address?**
   To keep fake pharmacies out. Public queries filter on approval. Changing name, address or location
   sends an approved pharmacy back to Pending (`pharmacies/services.py:333`). A revoked pharmacy is hidden
   and cannot change stock or answer requests.
7. **How are roles handled?**
   `User.role` plus decorators in `accounts/decorators.py`. Admin = role ADMIN or superuser
   (`accounts/models.py:31`); `is_staff` alone is not enough. Admins may also open customer pages.
8. **Can a pharmacy change its answer, or answer a cancelled request?**
   No. Only a PENDING request can change, through a conditional database update in a transaction
   (`requests_app/services.py:108`).
9. **Is it safe against CSRF, SQL injection and XSS?**
   CSRF middleware and tokens on every POST form; ORM only, no raw SQL; templates auto-escape, map data
   goes through `json_script`, and popups use `textContent` (`static/js/map_popup.js`). Tested with a
   stored XSS payload in the browser tests. No external penetration test yet.
10. **What stops someone guessing passwords?**
    5 failed logins per IP + username (20 per IP) are blocked for up to 15 minutes with HTTP 429
    (`accounts/views.py:121`). Behind Render's proxy the real client IP is taken from `X-Forwarded-For`
    (`TRUSTED_PROXY_COUNT=1`).
11. **How did you test it?**
    160 Django tests (`python manage.py test tests`) and 68 Playwright browser tests (`python -m pytest e2e`)
    that fail on any console error. Details in `docs/TESTING_REPORT.md`.
12. **What database do you use?**
    SQLite locally, PostgreSQL in production; `DATABASE_URL` decides.
13. **What would you improve first?**
    Automatic stock sync with pharmacy systems, an approval audit log, and email/SMS alerts.

## 7. Checks before presenting

1. Run `python manage.py test tests` (and, if time allows, `python -m pytest e2e`) on the presenting machine.
2. Rebuild the local database and run `seed_data`, so Metro Life is pending again.
3. Make sure `.env` has `DEBUG=True` (the demo logins and `seed_data` need it).
4. Open two browsers (one normal, one private) before starting.

---

## Additional presentation notes (applied)

_Status: applied. Every item below is fixed or already reflected in the main text above; kept as history._

Second pass (2026-11-22), from reading the code only. Details and fixes are in `MEDIFIND_REVIEW.md` → "Additional findings (second pass)".

1. **Q7 ("Is it safe…?") is incomplete.** CSRF and SQL injection are fine, but there is a stored XSS in the map popups (review N1). Do not say "secure against XSS" until it is fixed. If asked, say: "The map data is passed safely with `json_script`, but the popup HTML must also be escaped. That is on the fix list."
2. **Demo logins are visible to the audience.** `admin / admin123` and the other demo passwords appear in the footer of every page, on the home page and on the login page (`templates/base.html:242-244`, `templates/home.html:264-278`, `templates/accounts/login.html:66-72`). That is handy for the demo, but expect the question "is this on the live site too?". Slide 7's "some security settings still need fixing" should name it.
3. **Do not type a pincode in the home page search box.** The "City or Pincode" box is sent as `city` (`templates/home.html:29`), so a pincode returns no results. Use the pincode filter on `/medicines/search/` instead, or search by city.
4. **The search page shows a stray `} }` at the bottom** (`templates/medicines/search.html:494-496`). Fix it before the demo, or don't scroll to the bottom.
5. **The footer contradicts slide 3.** The footer says "Bootstrap 5 / Leaflet / SQLite" (`templates/base.html:263`), while slide 3 says PostgreSQL in production. Change the footer, or say "SQLite locally".
6. **The footer link "Store Inventory Directory" opens medicine search, not the pharmacy directory** (`templates/base.html:233`). Use the navbar "Nearby Pharmacies" link in the demo.
7. **Demo step 3:50 (pharmacy confirms):** the pharmacy can answer again and flip CONFIRMED to UNAVAILABLE (review N3). Avoid double submits. If asked "can the pharmacy change its answer?", the honest answer today is "yes, and the customer is notified each time".
8. **Demo step 1:30 (approve):** approval is a toggle. A double click un-approves the pharmacy (review N5). Click once and wait for the message.
9. **The freshness wording has two rules.** Section 2 says "warning badge if older than 24h" for customers and "under 24h, 24–48h, over 48h" for pharmacies. Both are in the code (review N20). Present it as "customers are warned after 24h; the pharmacy console also shows a 48h tier", or unify the rule first.
10. **Q6 (roles):** `@pharmacy_required` and `@customer_required` also let admins and any `is_staff` user in (review N16). Say "role decorators, with admins allowed everywhere".
11. **Q5 (approval):** approval controls public visibility, but a revoked pharmacy can still manage stock and answer old requests (review N19). Add that to the limitations if asked.
12. **Test numbers:** the `docs/` reports give anything from 17 to 136 tests. The code has 136 test functions (counted, not run). Quote that number only after running `python manage.py test tests` yourself. One fixture in `tests/test_admin_portal.py:102-113` silently fails (review N30).
13. **Section 5 "email defaults to the console":** in production, setting `EMAIL_HOST` etc. as `.env.example` suggests does nothing, because settings never read those variables (review N6). So password reset does not work on Render as configured.

---

## Updated notes after fixes (applied)

_Status: applied. These changes are now part of the main text above; kept as history._

After the fixes on branch `fix/all` (see "Fix log" in `MEDIFIND_REVIEW.md`). Tests were not run, so run `python manage.py test tests` yourself before quoting any test results.

**Remove or replace these earlier claims**
- Remove the XSS warning in note 1 above. Map popups are now built from DOM nodes with `textContent`, so pharmacy names and addresses are never parsed as HTML. If asked, say: "Map data is passed with `json_script`, and popups set text with `textContent`, not HTML strings." Still do not claim "fully secure": the app has had no external security test.
- Do not describe the stock as "live" or "real-time". The UI now says "Pharmacy-reported · updated X ago".
- Section 5 "Security items still to fix" and section 7 are done: safe settings defaults, `seed_data` blocked when DEBUG=False, POST logout, login rate limit, pinned packages, and Chart.js 4.4.1 with SRI. Notes 3–8, 10, 11 and 13 above are also fixed.

**Changed setup**
- `cp .env.example .env` is now the right local setup (DEBUG=True, SQLite). Without `DEBUG=True`, the app will not start unless `SECRET_KEY` and `ALLOWED_HOSTS` are set.
- Demo logins appear on the page only when DEBUG=True. Keep the table in section 1 handy.

**Changed demo steps**
- **Sign out** is now a button in the user menu (POST form), not a link.
- **Approve (1:30):** the buttons are explicit "Approve" / "Revoke". Clicking twice does nothing extra ("already approved"). The admin list has Pending / Approved / Revoked filters.
- **Pharmacy confirms (3:50):** a request can be answered **only once**. After the answer, the inbox shows "Answered" instead of "Respond".
- **Search (0:30 / 3:00):** results are ordered In Stock, then Low Stock, then Out of Stock. A pincode typed in the home search box now works.
- **Request (3:20):** a customer can only request a medicine the pharmacy lists, cannot send a second pending request for the same medicine at the same pharmacy, and can send at most 10 requests per hour.
- **Freshness:** `seed_data` now backdates some stock rows, so you can show the "updated 24–48h ago" and "over 48h ago · confirm before visiting" badges.
- **Optional extra demo:** as `pending_owner` (after approval), change the pharmacy address in the profile. It goes back to "Pending" and disappears from search until the admin approves it again.

**New or updated limitations (slide 7 / section 5)**
- Stock is still self-reported; anything older than 24h tells the customer to confirm first.
- Login rate limiting is per server process (local-memory cache), not shared across instances.
- Revoking a pharmacy cancels its pending requests; there is no stored approval history or rejection reason.
- One owner manages exactly one pharmacy.
- Notifications are in-app only. Password reset email works only after the `EMAIL_*` variables are filled in on Render.
- The medicine detail page shows no distances.
- Many files in `docs/` are outdated; see `docs/README_DOCS_STATUS.md`.

**Answers that changed**
- Q6 (roles): an `is_staff` user without the ADMIN role or superuser status no longer gets the admin portal. Admins can still open customer and pharmacy pages.
- Q5 (approval): approval has three states (Pending, Approved, Revoked). A revoked pharmacy is hidden and cannot change stock or answer requests.
- Q10 (what next): automatic stock sync, an approval audit log, and email/SMS alerts.
