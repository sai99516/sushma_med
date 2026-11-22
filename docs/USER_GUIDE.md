# How MediFind works (user guide and rules)

**Purpose:** What each kind of user can do in MediFind, and the rules the code enforces.
**Who it is for:** Beginners, testers and examiners who want to understand the app before reading code.
**Last verified:** 2026-11-22 against commit `dd2f32c`.

MediFind helps people find out which nearby pharmacy **reports** having a medicine.
Stock is typed in by the pharmacy itself ("pharmacy-reported"). The app does not check it,
it is not a reservation, and it is not medical advice. A banner at the top of every page says so
(`templates/base.html`).

## 1. The four kinds of user

| User | How the code knows | Lands on after login |
|---|---|---|
| Visitor | not logged in | – |
| Customer | `User.role == 'CUSTOMER'` | `/dashboard/customer/` |
| Pharmacy owner | `User.role == 'PHARMACY'` | `/dashboard/pharmacy/` |
| Admin | `User.role == 'ADMIN'` **or** `is_superuser` (`accounts/models.py:31`) | `/dashboard/admin-portal/` |

`/dashboard/` sends each logged-in user to the right dashboard (`dashboard/views.py:27`).
Who may open which page is listed in [ROLE_PERMISSION_MATRIX.md](ROLE_PERMISSION_MATRIX.md).

## 2. Visitor (anyone)

- **Home page** (`/`): counts of approved pharmacies, active medicines and in-stock listings at approved
  pharmacies, the 3 newest approved pharmacies, and a search box. Digits typed in the
  "City or Pincode" box are used as a pincode.
- **Medicine search** (`/medicines/search/`):
  - Text search matches medicine name, generic name, strength, dosage form, category, description
    and pharmacy name.
  - Filters: category, dosage form, strength, city (part of the name), pincode (exact match),
    stock status.
  - With the browser's location (the user must allow it): a radius filter (5, 10, 25 or 50 km) and
    "sort by distance".
  - **Order:** In Stock, then Low Stock, then Out of Stock; within each group, the most recently
    updated first (`medicines/services.py:22`). With "sort by distance" the nearest comes first.
  - 10 results per page, with a list view and a map view.
  - Only **approved** pharmacies and **active** (not archived) medicines appear.
- **Medicine detail** (`/medicines/<id>/`): every approved pharmacy that lists the medicine, in the same
  stock order, plus a map. It shows no distances.
- **Pharmacy directory** (`/pharmacies/`): search by pharmacy name or address, city, pincode and
  radius. Sort by distance (needs location), name or newest. 9 per page, with a map.
- **Pharmacy detail** (`/pharmacies/<id>/`): address, phone, map and stock list (20 per page). A pharmacy
  that is not approved is visible only to its owner and admins; anyone else is redirected to search
  with a message. The licence number is shown only to the owner and admins.

**Stock status** is set automatically when stock is saved (`inventory/models.py:52`):

| Quantity | Status |
|---|---|
| more than 10 | In Stock |
| 1 to 10 | Low Stock (1–10 units) |
| 0 | Out of Stock |

**Freshness** ("how old is this report?") uses one rule (`inventory/models.py:66-99`):

| Last update | Tier | Wording |
|---|---|---|
| up to 24 hours ago | FRESH | "Pharmacy-reported · updated within 24h" |
| 24 to 48 hours ago | MODERATE | "… updated 24–48h ago · confirm before visiting" |
| over 48 hours ago | STALE | "… updated over 48h ago · confirm before visiting" |

Search results show "Reported: <date> (X ago)". Anything older than 24 hours also gets a warning badge
"Reported >24h ago • Inquire to confirm". Times are shown in India time (`TIME_ZONE = 'Asia/Kolkata'`);
the database stores UTC.

## 3. Customer

- **Register** at `/accounts/register/customer/`. Username and email must be unique, ignoring
  upper/lower case. Password: at least 8 characters and Django's password validators (not too common,
  not all digits, not too similar to the username). Phone is optional; if given, 7–15 digits
  (`+`, spaces, dashes, dots and brackets allowed).
- **Log in / out.** Sign Out is a button (a POST form) in the user menu.
- **Availability request** ("Is this medicine there?"): the "Request Availability" button on a search
  result opens `/requests/create/<pharmacy_id>/<medicine_id>/`. Rules (`requests_app/services.py:23`,
  `requests_app/forms.py`):
  - the pharmacy must be approved and must list the medicine (any quantity);
  - quantity 1 to 1000, optional note up to 1000 characters;
  - no second **pending** request for the same medicine at the same pharmacy;
  - at most 10 new requests per 60 minutes per customer.
- **My Requests** (`/requests/my-requests/`): tabs All Inquiries / Pending Review / Confirmed In Stock / Unavailable / Cancelled.
  A pending request can be cancelled (with a confirm dialog). Answered requests cannot be cancelled.
- **Notifications** (`/accounts/notifications/`): unread count in the navbar bell, filters
  (all / unread / read), "Mark Read" for one, "Mark All as Read".
- **Profile** (`/accounts/profile/`), change password, and reset password by email.

### Request states

```
PENDING ──(pharmacy confirms)──> CONFIRMED     (final)
   │   ──(pharmacy declines)──> UNAVAILABLE   (final)
   │   ──(customer cancels)───> CANCELLED     (final)
   └──(admin revokes the pharmacy)──> CANCELLED, with an automatic note
```

A request is **answered once**: only a PENDING request can change. The change is a conditional
database update (`... WHERE status='PENDING'`) inside a transaction, so a cancel and an answer at the
same moment cannot overwrite each other (`requests_app/services.py:108`).

## 4. Pharmacy owner

- **Register** at `/accounts/register/pharmacy/`: owner account plus pharmacy details in one step.
  One owner has exactly one pharmacy. Licence (registration) number must be unique. Pincode must be a
  6-digit Indian PIN that does not start with 0. Latitude (−90 to 90) and longitude (−180 to 180) are
  optional; without them the pharmacy has no map pin and no distance.
- A new pharmacy starts as **Pending** and is hidden from the public until an admin approves it.
  The owner can still log in and prepare stock.
- **Inventory** (`/inventory/`): add a medicine from the active catalogue with a quantity. If it is
  already listed, the new number **replaces** the old one ("Set quantity"). Edit the quantity, delete a
  row (a confirm page, then POST). Search, filter by status and sort by last update, name or quantity.
- **Request inbox** (`/requests/pharmacy-inbox/`, shows Pending by default): open a pending request,
  choose "Confirm Medicine Available for Pickup" or "Report Medicine Unavailable / Out of Stock" and add a message (up to 1000 characters). The customer is notified.
  After that the inbox shows "Answered" instead of "Respond". A cancelled request cannot be answered.
- **Dashboard** (`/dashboard/pharmacy/`): stock counts, a doughnut chart, low/out-of-stock list,
  recent requests.
- **Profile changes** (`/pharmacies/profile/edit/` or the profile page): if an **approved** pharmacy
  changes its name, address, city, pincode, latitude or longitude, it goes back to **Pending**, is hidden
  from search and the owner is notified (`pharmacies/services.py:333`). Changing only the phone or state
  keeps it approved.
- A **revoked** pharmacy is hidden from the public and cannot add, edit or delete stock or answer requests.

## 5. Admin

- **Admin dashboard** (`/dashboard/admin-portal/`): user, pharmacy and request counts, the 5 newest
  pending pharmacies with Approve buttons, recent requests, and a bar chart of medicines per category.
- **Pharmacy approval** (`/pharmacies/manage/list/`, tabs All / Pending / Approved / Revoked).
  Approval has three states:

  ```
  PENDING ──Approve──> APPROVED ──Revoke──> REVOKED ──Approve──> APPROVED
     └──────Revoke (reject)──────────────────┘
  APPROVED ──owner edits name/address/location──> PENDING
  ```

  Approve and Revoke are separate buttons. Clicking one twice changes nothing the second time
  ("already approved"). Revoking cancels the pharmacy's pending requests and notifies those customers and
  the owner (`pharmacies/services.py:286`). There is no stored approval history and no rejection reason.
- **Medicine catalogue** (`/medicines/manage/`): add and edit medicines. Name + strength + dosage form
  must be unique (ignoring case). Medicines are **archived** (untick "Active"), not deleted; archived
  medicines disappear from search, the detail page, the add-stock form and new requests.
- **Users** (`/pharmacies/manage/users/`, customers and pharmacy owners) and **all requests**
  (`/pharmacies/manage/requests/`) with search and filters.
- **Django admin** (`/admin/`): needs `is_staff`. Approval fields are read-only there; the
  "Approve/Revoke selected" actions use the same service as the portal, so notifications still go out.

## 6. Notifications sent by the app

| Event | Who is notified |
|---|---|
| Customer registers | the customer (welcome) |
| Pharmacy registers | the owner ("pending admin verification") |
| Pharmacy approved / revoked | the owner |
| Approved pharmacy edits name, address or location | the owner (needs re-approval) |
| New availability request | the pharmacy owner |
| Request confirmed / unavailable | the customer |
| Pharmacy revoked while requests are pending | each affected customer |

Notifications are in-app only. There are no emails or SMS for these events; email is used only for
password reset.

## 7. Demo data (local only)

`python manage.py seed_data` refuses to run unless `DEBUG=True`. It creates:
6 pharmacies in Hyderabad, Bengaluru and New Delhi (5 approved, 1 pending: "[DEMO] Metro Life Pharmacy
(Pending Review)"), 31 medicines, 69 stock rows (some backdated by 30, 60 and 72 hours to show the
freshness badges), 4 requests and these logins:

| Role | Username | Password |
|---|---|---|
| Admin (superuser) | `admin` | `admin123` |
| Customers | `customer1`, `customer2`, `customer3` | `password123` |
| Approved owners | `apollo_owner`, `medplus_owner`, `wellness_owner`, `netmeds_owner`, `care_owner` | `password123` |
| Pending owner | `pending_owner` | `password123` |

The login page, home page and footer show these logins only when `DEBUG=True`.

## 8. What MediFind does not do

No payments, orders, reservations or prescription upload; no automatic stock sync with pharmacy
systems; no road distance (distance is a straight line); no mobile app.
