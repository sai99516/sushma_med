"""5. Customer: dashboard, request availability, my requests, cancel, notifications."""
import re

from playwright.sync_api import expect

from helpers import login, make_customer, make_pharmacy, make_request, make_stock, uid, url_path


def setup_stock(pincode):
    p = make_pharmacy(pincode=pincode, name=f"Cust Test Pharmacy {uid()}")
    make_stock(p, "Dolo 650", 30)
    return p


def test_customer_dashboard(page):
    cust = make_customer()
    p = setup_stock("500071")
    make_request(cust, p, "Dolo 650")
    login(page, cust.username)
    assert url_path(page) == "/dashboard/customer/"
    expect(page.locator("h2")).to_contain_text("Test")
    expect(page.locator(".stat-value").first).to_have_text("1")
    expect(page.locator("main", has_text="Dolo 650").first).to_be_visible()


def _open_request_form(page, pharmacy):
    page.goto(f"/medicines/search/?q=Dolo&pincode={pharmacy.pincode}")
    card = page.locator("#resultsList .med-card", has_text=pharmacy.pharmacy_name)
    card.get_by_role("link", name="Request Availability").click()
    page.wait_for_url(re.compile(rf"/requests/create/{pharmacy.pk}/\d+/$"))


def _submit(page, qty, note=""):
    page.locator("#id_quantity_requested").fill(str(qty))
    page.locator("#id_request_message").fill(note)
    page.locator("main form button[type=submit]").click()
    page.wait_for_load_state()


def test_request_availability_valid_duplicate_and_bad_quantities(page):
    from requests_app.models import AvailabilityRequest
    cust = make_customer()
    p = setup_stock("500072")
    login(page, cust.username)

    # search from the nav, then request
    page.locator("#navbarMain").get_by_role("link", name=re.compile("Find Medicine")).click()
    page.get_by_placeholder("Search by name...").fill("Dolo")
    page.get_by_placeholder("e.g. 500034").fill(p.pincode)
    page.get_by_role("button", name="Apply Filters").click()
    page.wait_for_load_state()
    page.locator("#resultsList .med-card", has_text=p.pharmacy_name).get_by_role(
        "link", name="Request Availability").click()
    page.wait_for_url(re.compile(rf"/requests/create/{p.pk}/\d+/$"))
    _submit(page, 2, "Need it tonight")
    assert url_path(page).startswith("/requests/my-requests/")
    expect(page.locator(".alert-success.alert-dismissible")).to_contain_text("has been sent to")
    expect(page.locator("tbody tr", has_text="Dolo 650")).to_contain_text("Pending Pharmacy Review")

    # duplicate pending request is blocked
    _open_request_form(page, p)
    _submit(page, 1)
    expect(page.locator(".alert-danger.alert-dismissible")).to_contain_text("already have a pending request")

    # quantity 0 and 1001: blocked by the browser (min=1, max=1000, review E2) ...
    _open_request_form(page, p)
    for bad in ("0", "1001"):
        page.locator("#id_quantity_requested").fill(bad)
        page.locator("main form button[type=submit]").click()
        assert re.search(r"/requests/create/", page.url)
        assert page.locator("#id_quantity_requested").evaluate("el => el.validationMessage"), bad
    # ... and by the server when the browser check is bypassed
    page.locator("main form").evaluate("f => f.noValidate = true")
    _submit(page, 0)
    expect(page.locator("main form")).to_contain_text("at least 1 unit")

    # quantity 1001 is rejected by the server (the re-rendered form validates again)
    page.locator("main form").evaluate("f => f.noValidate = true")
    _submit(page, 1001)
    expect(page.locator("main form")).to_contain_text("at most 1000 units")
    assert AvailabilityRequest.objects.filter(customer=cust).count() == 1


def test_my_requests_tabs_and_cancel(page, new_context):
    cust = make_customer()
    p = setup_stock("500073")
    make_stock(p, "Pan 40", 5)
    make_stock(p, "Telma 40", 5)
    pending = make_request(cust, p, "Dolo 650")
    make_request(cust, p, "Pan 40", status="CONFIRMED")
    make_request(cust, p, "Telma 40", status="UNAVAILABLE")

    login(page, cust.username)
    page.get_by_role("link", name=re.compile("My Requests")).click()
    page.wait_for_url(re.compile(r"/requests/my-requests/"))
    rows = page.locator("tbody tr")
    expect(rows).to_have_count(3)
    for tab, count, med in (("Pending Review", 1, "Dolo 650"), ("Confirmed In Stock", 1, "Pan 40"),
                            ("Unavailable", 1, "Telma 40"), ("Cancelled", 0, None), ("All Inquiries", 3, None)):
        page.locator("main a.rounded-pill", has_text=tab).first.click()
        page.wait_for_load_state()
        expect(rows if count else page.locator("tbody tr")).to_have_count(count)
        if med:
            expect(rows.first).to_contain_text(med)

    # cancel the pending one (confirm dialog accepted)
    page.on("dialog", lambda d: d.accept())
    page.locator("tbody tr", has_text="Dolo 650").get_by_role("button", name=re.compile("Cancel")).click()
    page.wait_for_load_state()
    expect(page.locator(".alert-success.alert-dismissible")).to_contain_text(f"Request #{pending.pk} has been cancelled")
    pending.refresh_from_db()
    assert pending.status == "CANCELLED"
    page.get_by_role("link", name=re.compile("Cancelled")).click()
    page.wait_for_load_state()
    expect(page.locator("tbody tr")).to_have_count(1)

    # the pharmacy cannot answer a cancelled request
    o = new_context().new_page()
    login(o, p.owner.username)
    o.goto("/requests/pharmacy-inbox/?status=ALL")
    expect(o.locator("tbody tr", has_text="Dolo 650")).to_contain_text("Cancelled")
    o.goto(f"/requests/{pending.pk}/respond/")
    o.wait_for_url(re.compile(r"/requests/pharmacy-inbox/"))
    expect(o.locator(".alert-warning.alert-dismissible")).to_contain_text("cancelled by the customer")
    pending.refresh_from_db()
    assert pending.status == "CANCELLED"


def test_cancel_dialog_dismissed_keeps_request(page):
    cust = make_customer()
    p = setup_stock("500074")
    req = make_request(cust, p, "Dolo 650")
    login(page, cust.username)
    page.goto("/requests/my-requests/")
    page.once("dialog", lambda d: d.dismiss())
    page.locator("tbody tr", has_text="Dolo 650").get_by_role("button", name=re.compile("Cancel")).click()
    page.wait_for_timeout(500)
    req.refresh_from_db()
    assert req.status == "PENDING"


def test_notifications_unread_mark_one_mark_all_and_other_users(page, monitor):
    from requests_app.models import Notification
    cust = make_customer()
    other = make_customer()
    for i in range(3):
        Notification.objects.create(user=cust, message=f"E2E note {i}")
    foreign = Notification.objects.create(user=other, message="Someone else's note")

    login(page, cust.username)
    bell = page.locator("a[title=Notifications] .badge")
    expect(bell).to_have_text("3")
    page.locator("a[title=Notifications]").click()
    page.wait_for_url(re.compile(r"/accounts/notifications/"))
    expect(page.get_by_text("3 New")).to_be_visible()

    page.locator("div.rounded-3.border", has_text="E2E note 1").get_by_role("button", name="Mark Read").click()
    page.wait_for_load_state()
    expect(page.locator(".alert-success.alert-dismissible")).to_contain_text("marked as read")
    expect(bell).to_have_text("2")
    page.get_by_role("link", name=re.compile("Unread Alerts")).click()
    page.wait_for_load_state()
    expect(page.get_by_text("E2E note 1")).to_have_count(0)

    page.get_by_role("button", name=re.compile("Mark All")).click()
    page.wait_for_load_state()
    expect(page.locator(".alert-success.alert-dismissible")).to_contain_text("Marked 2 notifications as read")
    expect(bell).to_have_count(0)

    # Try to mark another user's notification with a real form POST (valid CSRF token).
    monitor.allow(404, rf"/accounts/notifications/{foreign.pk}/read/")
    page.goto("/accounts/notifications/")
    page.evaluate("""id => {
        const token = document.querySelector('input[name=csrfmiddlewaretoken]').value;
        const f = document.createElement('form');
        f.method = 'POST'; f.action = `/accounts/notifications/${id}/read/`;
        const i = document.createElement('input'); i.type = 'hidden'; i.name = 'csrfmiddlewaretoken'; i.value = token;
        f.appendChild(i); document.body.appendChild(f); setTimeout(() => f.submit(), 0);
    }""", foreign.pk)
    page.wait_for_url(re.compile(rf"/notifications/{foreign.pk}/read/$"))
    expect(page.locator("body")).to_contain_text(re.compile("not found", re.I))
    foreign.refresh_from_db()
    assert foreign.is_read is False
