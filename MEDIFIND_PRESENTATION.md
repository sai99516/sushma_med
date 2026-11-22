# MediFind – Presentation Pack

Based only on the code. Nothing was run, so the steps below are from reading the code and are untested.

---

## 1. Quick start (local, safe settings)

```bash
python3.11 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
echo "DEBUG=True" > .env            # local only; do NOT copy .env.example (it is for production + Postgres)
python manage.py migrate            # uses SQLite (db.sqlite3) because DATABASE_URL is not set
python manage.py seed_data          # demo users, 6 pharmacies, ~30 medicines, ~70 stock rows, sample requests
python manage.py runserver          # open http://127.0.0.1:8000
```

**Demo logins** (from `medicines/management/commands/seed_data.py`):

| Role | Username | Password |
|---|---|---|
| Admin (superuser) | `admin` | `admin123` |
| Customers | `customer1`, `customer2`, `customer3` | `password123` |
| Pharmacy owners (approved) | `apollo_owner`, `medplus_owner`, `wellness_owner`, `netmeds_owner`, `care_owner` | `password123` |
| Pharmacy owner (**pending**) | `pending_owner` | `password123` |

## 2. Features by role

**Anyone (not logged in)**
- Home page with counts: approved pharmacies, medicines, in-stock listings.
- Medicine search with filters: name, category, dosage form, strength, city, pincode, stock status. With the browser's location you can also filter by distance and sort by nearest.
- Medicine detail page: which approved pharmacies list the medicine, plus a map.
- Pharmacy directory (`/pharmacies/`) with a Leaflet map and pharmacy detail pages.
- Each result shows "Reported: <date> (X ago)" and a warning badge if the stock is older than 24 hours.

**Customer**
- Register, log in, edit profile, change or reset password.
- Send an "availability request" (quantity + note) to an approved pharmacy.
- "My requests" page with status tabs (Pending / Confirmed / Unavailable / Cancelled); pending requests can be cancelled.
- Notifications page (read/unread, mark all as read) and a customer dashboard.

**Pharmacy owner**
- Register the pharmacy (licence number, address, map coordinates). It starts as **pending approval**.
- Inventory: add medicines from the catalogue, change quantity, delete; search, filter, sort.
- The status is set automatically: more than 10 = In Stock, 1–10 = Low Stock, 0 = Out of Stock.
- Freshness badges: under 24h, 24–48h, over 48h.
- Request inbox: confirm or decline customer requests with a message, and the customer is notified.
- Dashboard: stock chart, low-stock alerts, recent requests; edit pharmacy profile.

**Admin**
- Admin dashboard: user, pharmacy and request counts, pending approvals, medicine category chart.
- Approve or revoke pharmacies (the owner gets a notification).
- Manage the medicine catalogue (add/edit), list users, monitor all requests.
- Django admin at `/admin/`.

## 3. Demo script (about 5 minutes)

| Time | Who | Do this | URL |
|---|---|---|---|
| 0:00 | Visitor | Show the home page and the disclaimer banner at the top | `/` |
| 0:30 | Visitor | Search "Dolo"; show the results, the "Reported X ago" text and the map | `/medicines/search/?q=Dolo` |
| 1:00 | Admin | Log in as `admin` and show the dashboard and pending approvals | `/accounts/login/` → `/dashboard/admin-portal/` |
| 1:30 | Admin | Approve "[DEMO] Metro Life Pharmacy" | `/pharmacies/manage/list/?status=pending` |
| 2:00 | Pharmacy | Log out, then log in as `pending_owner`; show the approval notification | `/accounts/notifications/` |
| 2:20 | Pharmacy | Add Dolo 650 with 25 units; it shows as "In Stock" | `/inventory/add/` → `/inventory/` |
| 3:00 | Customer | Log in as `customer1` and search "Dolo"; Metro Life now appears | `/medicines/search/?q=Dolo` |
| 3:20 | Customer | Click "Request Availability" and send 2 units with a note | `/requests/create/<pharmacy_id>/<medicine_id>/` |
| 3:50 | Pharmacy | Log in as `pending_owner`, open the inbox and confirm with a message | `/requests/pharmacy-inbox/` → `/requests/<id>/respond/` |
| 4:30 | Customer | Log in as `customer1` and show the request as "Confirmed" plus the notification | `/requests/my-requests/` |
| 5:00 | – | End on the disclaimer: the stock is reported by the pharmacy, not guaranteed | – |

Tip: use two browsers (or one private window) so you don't have to log out and in all the time.

## 4. Presentation outline (8 slides)

1. **Problem**
   - Patients go from shop to shop looking for a medicine.
   - There is no simple way to see which nearby pharmacy reports having it.
   - Phoning each shop takes time, especially when the need is urgent.
2. **Solution**
   - One search for a medicine across approved local pharmacies.
   - Pharmacies update their own stock, and every result shows when it was last updated.
   - Customers can ask a pharmacy to confirm before they travel.
3. **Tech stack**
   - Python 3.11, Django 5.2, SQLite (local) / PostgreSQL (production).
   - Bootstrap 5, Leaflet maps, Chart.js; plain Django templates.
   - Gunicorn + WhiteNoise, deployed with Render (`render.yaml`, `build.sh`).
4. **Architecture**
   - Six Django apps: accounts, pharmacies, medicines, inventory, requests_app, dashboard.
   - Views → `services.py` (business logic) → templates; role checks in `accounts/decorators.py`.
   - Main models: User(role), Pharmacy, Medicine, Inventory, AvailabilityRequest, Notification.
5. **Main features**
   - Search by name, filters and distance (Haversine), with a map.
   - Admin approval of pharmacies; only approved ones appear in public results.
   - Stock status and freshness badges; request → confirm/decline → notification.
6. **Demo**
   - Admin approves a pharmacy.
   - The pharmacy adds stock and the customer finds it.
   - The customer sends a request and the pharmacy confirms it.
7. **Limitations**
   - Stock is reported by the pharmacy and not guaranteed or synced automatically.
   - No payment, no reservation, no mobile app, no email/SMS alerts by default.
   - Some security settings still need fixing before real use.
8. **Future work**
   - Connect to pharmacy billing systems for automatic stock updates.
   - Email/SMS/push notifications, plus a mobile app or installable web app.
   - Security hardening, login rate limiting, a re-check when a pharmacy changes its address.

## 5. Limitations and future work (honest list)

**Limitations**
- Stock is **reported by the pharmacy**; the app cannot check it. A result is not a reservation.
- No real-time sync: stock only changes when the owner edits it by hand.
- No payment, ordering, reservation or prescription upload.
- No mobile app. Notifications are in-app only, and email defaults to the console (password reset emails are not really sent).
- Distance is a straight line (Haversine), not road distance. Pharmacies without coordinates have no distance.
- An approved pharmacy can change its name or address without being checked again.
- Not medical advice; no doctor or pharmacist review of medicines.

**Security items still to fix** (details in `MEDIFIND_REVIEW.md`)
- Unsafe defaults if env vars are missing: hardcoded `SECRET_KEY`, `DEBUG=True`, `ALLOWED_HOSTS=*` (`config/settings.py:15-22`).
- `seed_data` creates and resets `admin/admin123`, even in production.
- Logout works through a GET link; there is no limit on login attempts.
- Package versions are not pinned; Chart.js is loaded with no version.

**Future work**
- Pharmacy billing (POS) integration, stock history, expiry dates.
- Email/SMS alerts when a request is answered or when stock comes back.
- Road distance and directions; a mobile app.
- Fix the security items above; add an audit log of stock changes.

## 6. Likely questions (short answers)

1. **How do you stop one pharmacy from editing another's stock?**
   Every edit and delete looks up the item together with the logged-in owner's pharmacy (`pharmacy=pharmacy`). Anything else returns 404 (`inventory/views.py:105-109`).
2. **How do you know the stock is correct?**
   We don't. It is reported by the pharmacy. We show when it was last updated, warn if it is older than 24h, and let the customer ask the pharmacy to confirm.
3. **How is "In Stock / Low / Out" decided?**
   Automatically in `Inventory.save()`: more than 10 is In Stock, 1–10 is Low Stock, 0 is Out of Stock (`inventory/models.py:52-61`).
4. **How do you calculate distance?**
   With the Haversine formula, using the user's browser location and the pharmacy's latitude/longitude (`pharmacies/services.py:32-67`).
5. **Why must pharmacies be approved?**
   To stop fake pharmacies from listing medicines. Public queries filter on `is_approved=True`.
6. **How are user roles handled?**
   A custom `User` model has a `role` field, and decorators such as `@pharmacy_required` protect the views.
7. **Is it safe against CSRF and SQL injection?**
   CSRF: yes, the middleware is on and every POST form has `{% csrf_token %}`. SQL injection: we only use the Django ORM, with no raw SQL.
8. **What database do you use?**
   SQLite locally and PostgreSQL in production. `DATABASE_URL` decides which.
9. **Why use a `services.py` layer?**
   It keeps views small and puts the business logic in one place, which makes it easier to test and reuse.
10. **What would you improve first?**
    The production security defaults, the order of search results, and automatic stock sync with pharmacy systems.

## 7. Fixes to do before presenting (top 3 most visible)

1. **Search shows "Out of Stock" first.** `order_by('-availability_status')` sorts the status names in reverse alphabetical order (`medicines/services.py:68`, `:179`). Sort by a fixed rank instead (In Stock, then Low Stock, then Out of Stock). The audience will see this in the first search.
2. **Wording that promises too much.** "Live Stock", "Real-time Stock" and "Verified Fresh" (`templates/base.html:224`, `templates/pharmacies/discovery.html:177`, `inventory/models.py:99`, `templates/inventory/list.html:149`) contradict the disclaimer. Change them to "Pharmacy-reported · updated X ago".
3. **Chart.js has no version** (`templates/base.html:277`). A new release could break the dashboard charts during the demo. Pin it, e.g. `chart.js@4.4.1`.

---

## Additional presentation notes

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
