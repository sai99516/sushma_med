# Roles and permissions

**Purpose:** Who can open each URL, and what happens to everyone else.
**Who it is for:** Developers changing views, testers, and examiners asking about access control.
**Last verified:** 2026-11-22 against commit `dd2f32c` (URL list from `config/urls.py` and each app's `urls.py`).

## 1. Roles

The custom `User` model (`accounts/models.py`) has a `role` field: `CUSTOMER` (default), `PHARMACY` or `ADMIN`.

- `is_customer`: role is CUSTOMER.
- `is_pharmacy_owner`: role is PHARMACY.
- `is_admin_user`: role is ADMIN **or** the user is a superuser. `is_staff` alone does **not** make
  someone an app admin; it only allows Django admin (`/admin/`).

## 2. How access is checked

Decorators in `accounts/decorators.py` wrap the views (a decorator is a function that runs before the view):

| Decorator | Allows | Not logged in | Wrong role |
|---|---|---|---|
| `@customer_required` | customers **and admins** | redirect to `/accounts/login/?next=<page>` | redirect to `/dashboard/` (then to the user's own dashboard) with "This area is designated for customers." |
| `@pharmacy_required` | pharmacy owners **and admins** | same | same, with "Only registered Pharmacy Owners can access inventory." |
| `@admin_required` | admins | same | same, with "Platform Administrator privileges required." |
| `@login_required` (Django) | any logged-in user | redirect to login | – |
| `@require_POST` (Django) | POST only | – | GET returns **405 Method Not Allowed** |

On top of the role check, every query for private data includes the owner, for example
`get_object_or_404(Inventory, pk=pk, pharmacy=<the owner's pharmacy>)`. Another user's row therefore
returns **404 Not Found**, not someone else's data. This is called object-level ("tenant") isolation.

Admins pass `@pharmacy_required`, but they have no pharmacy, so pharmacy pages redirect them with
"No pharmacy record found" (or 404 for edit/delete/respond of a specific row). Admins **can** use
customer pages, including sending availability requests (a known, accepted choice).

## 3. URL table

V = visitor (not logged in), C = customer, P = pharmacy owner, A = admin.

### Public and account pages

| URL | Who | Notes |
|---|---|---|
| `/` | all | Home page |
| `/medicines/search/` | all | Approved pharmacies and active medicines only |
| `/medicines/<id>/` | all | Archived medicine → 404 |
| `/pharmacies/` | all | Approved pharmacies only |
| `/pharmacies/<id>/` | all; non-approved pharmacy: its owner and admins | Others are redirected to search with "pending administrative verification" |
| `/accounts/register/customer/`, `/accounts/register/pharmacy/` | V | Logged-in users are redirected to `/dashboard/` |
| `/accounts/login/` | V | Logged-in users are redirected to `/dashboard/`. Rate limited (see [SECURITY_FINAL_REVIEW.md](SECURITY_FINAL_REVIEW.md)) |
| `/accounts/logout/` | logged-in | POST only; GET → 405 |
| `/accounts/profile/` | C, P, A | `@login_required` |
| `/accounts/notifications/` | C, P, A | Own notifications only |
| `/accounts/notifications/<id>/read/` | C, P, A | POST only; another user's notification → 404 |
| `/accounts/notifications/mark-all-read/` | C, P, A | POST only |
| `/accounts/password-change/`, `/accounts/password-change/done/` | C, P, A | Django's built-in views (login required) |
| `/accounts/password-reset/`, `/accounts/password-reset/done/`, `/accounts/password-reset-confirm/<uidb64>/<token>/`, `/accounts/password-reset/complete/` | all | Django's built-in reset by email |

### Dashboards

| URL | Who | Notes |
|---|---|---|
| `/dashboard/` | C, P, A | Redirects to the user's own dashboard |
| `/dashboard/customer/` | C, A | `@customer_required` |
| `/dashboard/pharmacy/` | P (A without pharmacy is redirected) | `@pharmacy_required` |
| `/dashboard/admin-portal/` | A | `@admin_required` |

### Customer requests

| URL | Who | Notes |
|---|---|---|
| `/requests/create/<pharmacy_id>/<medicine_id>/` | C, A | Pharmacy not approved or medicine archived → 404; an owner cannot request from their own pharmacy |
| `/requests/my-requests/` | C, A | Own requests only |
| `/requests/<id>/cancel/` | C, A | POST only; another customer's request → 404; only PENDING can be cancelled |

### Pharmacy owner

| URL | Who | Notes |
|---|---|---|
| `/inventory/` | P | Own stock only |
| `/inventory/add/` | P | Blocked for a revoked pharmacy |
| `/inventory/<id>/edit/` | P | Another pharmacy's row → 404; blocked when revoked |
| `/inventory/<id>/delete/` | P | GET shows a confirm page, POST deletes; another pharmacy's row → 404; blocked when revoked |
| `/requests/pharmacy-inbox/` | P | Own pharmacy's requests only |
| `/requests/<id>/respond/` | P | Another pharmacy's request → 404; only PENDING can be answered; blocked when revoked |
| `/pharmacies/profile/edit/` | P | Sensitive changes send an approved pharmacy back to Pending |

### Admin

| URL | Who | Notes |
|---|---|---|
| `/pharmacies/manage/list/` | A | `?status=pending|approved|revoked`, search |
| `/pharmacies/manage/<id>/toggle-approval/` | A | POST only, with `action=approve` or `action=revoke`. The old URL name is kept; each button sets one state |
| `/pharmacies/manage/users/` | A | Customers and pharmacy owners (admins are not listed) |
| `/pharmacies/manage/requests/` | A | All requests, filter by status, search |
| `/medicines/manage/`, `/medicines/add/`, `/medicines/<id>/edit/` | A | Catalogue; archive by unticking "Active" (there is no delete page) |
| `/admin/` | users with `is_staff` | Django admin. The seeded `admin` user is staff and superuser |

That is 40 app URLs. In DEBUG mode Django also serves `/media/` files; the app has no uploads.

## 4. Business rules that also limit access

- A **pending** pharmacy is not public, but its owner can log in, add stock and see the dashboard.
- A **revoked** pharmacy is not public and cannot change stock or answer requests.
- A request can be answered once and cancelled only while PENDING.
- Tested by `tests/test_security.py`, `tests/test_admin_portal.py` and the browser tests in
  `e2e/test_security.py` (12 direct-URL cases plus cross-pharmacy 404 checks).
