"""
7. The full 5-minute demo script from MEDIFIND_PRESENTATION.md section 3, as one test.
Runs first (file name), so the seeded pending_owner / Metro Life pharmacy is untouched.
"""
import re

from playwright.sync_api import expect

from helpers import login, logout, url_path

METRO = "[DEMO] Metro Life Pharmacy"


def test_demo_script(page):
    from pharmacies.models import Pharmacy
    metro = Pharmacy.objects.get(owner__username="pending_owner")
    assert metro.approval_status == "PENDING", "precondition: seed data not fresh"

    # 0:00 Visitor: home page + disclaimer banner
    page.goto("/")
    expect(page.locator(".disclaimer-banner")).to_be_visible()
    expect(page.locator(".disclaimer-banner")).to_contain_text("pharmacy-reported stock")

    # 0:30 Visitor: search "Dolo", results, "Reported X ago", map
    page.get_by_placeholder(re.compile("Search medicine")).fill("Dolo")
    page.locator("button.btn-search-main").click()
    page.wait_for_url(re.compile(r"/medicines/search/\?q=Dolo"))
    expect(page.locator("#resultsList").get_by_text(re.compile(r"Reported: .* ago")).first).to_be_visible()
    expect(page.locator("#resultsList")).not_to_contain_text(METRO)
    page.locator("#btnMapView").click()
    expect(page.locator("#map .leaflet-marker-icon").first).to_be_visible()

    # 1:00 Admin: log in, dashboard, pending approvals
    page.get_by_role("link", name="Sign In").click()
    login(page, "admin", "admin123")
    assert url_path(page) == "/dashboard/admin-portal/"
    expect(page.locator("tr", has_text=METRO)).to_be_visible()

    # 1:30 Admin: approve Metro Life from /pharmacies/manage/list/?status=pending
    page.get_by_role("link", name=re.compile("Manage All")).click()
    page.wait_for_url(re.compile(r"/pharmacies/manage/list/\?status=pending"))
    page.locator("tr", has_text=METRO).get_by_role("button", name="Approve").click()
    page.wait_for_load_state()
    expect(page.locator(".alert-success.alert-dismissible")).to_contain_text("has been approved")

    # 2:00 Pharmacy: log out, log in as pending_owner, approval notification
    logout(page)
    login(page, "pending_owner", "password123")
    expect(page.locator("a[title=Notifications] .badge")).to_have_text("1")
    page.locator("a[title=Notifications]").click()
    page.wait_for_url(re.compile(r"/accounts/notifications/"))
    expect(page.get_by_text(re.compile("has been approved"))).to_be_visible()

    # 2:20 Pharmacy: add Dolo 650 with 25 units -> In Stock
    page.goto("/inventory/add/")
    page.locator("#id_medicine").select_option(label="Dolo 650 (650mg) - Tablet")
    page.locator("#id_quantity").fill("25")
    page.locator("main form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/inventory/$"))
    expect(page.locator("tbody tr", has_text="Dolo 650").locator(".badge-in-stock")).to_have_text("In Stock")

    # 3:00 Customer: customer1 searches "Dolo"; Metro Life now appears
    logout(page)
    login(page, "customer1", "password123")
    page.goto("/medicines/search/?q=Dolo")
    card = page.locator("#resultsList .med-card", has_text=METRO)
    expect(card).to_be_visible()

    # 3:20 Customer: Request Availability, 2 units with a note
    card.get_by_role("link", name="Request Availability").click()
    page.wait_for_url(re.compile(rf"/requests/create/{metro.pk}/\d+/$"))
    page.locator("#id_quantity_requested").fill("2")
    page.locator("#id_request_message").fill("Please keep 2 strips for this evening.")
    page.locator("main form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/requests/my-requests/"))
    expect(page.locator("tbody tr", has_text=METRO)).to_contain_text("Pending Pharmacy Review")

    # 3:50 Pharmacy: inbox, confirm with a message
    logout(page)
    login(page, "pending_owner", "password123")
    page.goto("/requests/pharmacy-inbox/")
    row = page.locator("tbody tr", has_text="Dolo 650")
    expect(row).to_contain_text("customer1")
    row.get_by_role("link", name="Respond").click()
    page.wait_for_url(re.compile(r"/requests/\d+/respond/$"))
    page.locator("#id_status").select_option("CONFIRMED")
    page.locator("#id_pharmacy_response").fill("2 strips kept at the counter until 8 PM.")
    page.locator("main form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/requests/pharmacy-inbox/"))
    expect(page.locator(".alert-success.alert-dismissible")).to_contain_text("Response recorded")

    # 4:30 Customer: request shows Confirmed, plus the notification
    logout(page)
    login(page, "customer1", "password123")
    page.goto("/requests/my-requests/")
    row = page.locator("tbody tr", has_text=METRO)
    expect(row).to_contain_text("Confirmed Available")
    expect(row).to_contain_text("2 strips kept at the counter until 8 PM.")
    page.locator("a[title=Notifications]").click()
    page.wait_for_url(re.compile(r"/accounts/notifications/"))
    expect(page.get_by_text(re.compile("Metro Life")).first).to_be_visible()

    # 5:00 End on the disclaimer
    expect(page.locator(".disclaimer-banner")).to_contain_text("not a guaranteed reservation")
