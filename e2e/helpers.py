"""Shared helpers: test data built with the ORM, and UI actions done with real clicks."""
import itertools
import re
import time
from datetime import timedelta

from pathlib import Path

from playwright.sync_api import Page, expect

SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

PASSWORD = "Str0ng!Passw0rd#e2e"
_counter = itertools.count(1)


def uid(prefix="e2e"):
    return f"{prefix}{int(time.time() * 1000) % 10_000_000}{next(_counter)}"


# ----------------------------------------------------------------- ORM data
def make_customer(username=None, password=PASSWORD):
    from accounts.models import User
    username = username or uid("cust")
    u = User.objects.create_user(username=username, email=f"{username}@e2e.test",
                                 password=password, role="CUSTOMER", first_name="Test", last_name="Customer")
    return u


def make_pharmacy(name=None, approved=True, owner=None, lat=17.40, lng=78.45, city="Hyderabad",
                  pincode="500001", address=None):
    from accounts.models import User
    from pharmacies.models import Pharmacy
    tag = uid("ph")
    owner = owner or User.objects.create_user(username=f"{tag}_owner", email=f"{tag}@e2e.test",
                                              password=PASSWORD, role="PHARMACY")
    p = Pharmacy.objects.create(
        owner=owner, pharmacy_name=name or f"E2E Pharmacy {tag}", registration_number=f"E2E-{tag}",
        address=address or "1 Test Street", city=city, state="Telangana", pincode=pincode,
        phone_number="+91 9000000000", latitude=lat, longitude=lng,
        approval_status=Pharmacy.STATUS_APPROVED if approved else Pharmacy.STATUS_PENDING,
    )
    return p


def make_stock(pharmacy, medicine_name, qty, age_hours=0):
    from inventory.models import Inventory
    from medicines.models import Medicine
    med = Medicine.objects.get(medicine_name=medicine_name)
    inv = Inventory.objects.create(pharmacy=pharmacy, medicine=med, quantity=qty)
    if age_hours:
        from django.utils import timezone
        Inventory.objects.filter(pk=inv.pk).update(updated_at=timezone.now() - timedelta(hours=age_hours))
    return inv


def make_request(customer, pharmacy, medicine_name, status="PENDING", qty=1):
    from medicines.models import Medicine
    from requests_app.models import AvailabilityRequest
    med = Medicine.objects.get(medicine_name=medicine_name)
    return AvailabilityRequest.objects.create(customer=customer, pharmacy=pharmacy, medicine=med,
                                              quantity_requested=qty, status=status)


def medicine_id(name):
    from medicines.models import Medicine
    return Medicine.objects.get(medicine_name=name).pk


# ----------------------------------------------------------------- UI actions
def login(page: Page, username, password=PASSWORD, expect_ok=True):
    page.goto("/accounts/login/")
    page.get_by_placeholder("Enter your username").fill(username)
    page.get_by_placeholder("Enter your password").fill(password)
    page.locator("form button[type=submit]").first.click()
    page.wait_for_load_state()
    if expect_ok:
        expect(page.locator(".alert-success.alert-dismissible")).to_contain_text(f"Welcome back, {username}")


def logout(page: Page):
    """Uses the 'Sign Out' button in the user dropdown (POST form)."""
    page.locator("a.dropdown-toggle:has(.bi-person-circle)").click()
    page.get_by_role("button", name="Sign Out").click()
    page.wait_for_load_state()
    expect(page.locator(".alert-info.alert-dismissible")).to_contain_text("logged out")


def alerts(page: Page):
    return page.locator("main .alert").all_inner_texts()


def xss_not_run(page: Page):
    assert page.evaluate("typeof window.__xss") == "undefined", "XSS payload executed"


def status_texts(page: Page):
    """Stock status badges on the search results page, top to bottom."""
    return page.locator("#resultsList .badge-in-stock, #resultsList .badge-low-stock, #resultsList .badge-out-stock") \
        .evaluate_all("els => els.map(e => e.className)")


RANK = {"badge-in-stock": 0, "badge-low-stock": 1, "badge-out-stock": 2}


def ranks(classes):
    return [RANK[c] for c in classes]


def url_path(page):
    return re.sub(r"^https?://[^/]+", "", page.url)
