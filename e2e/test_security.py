"""6. Browser security checks: stored XSS in maps/pages, role access by direct URL, GET logout."""
import re

import pytest
from playwright.sync_api import expect

from helpers import (login, make_customer, make_pharmacy, make_stock, medicine_id, uid, url_path,
                     xss_not_run)

PAYLOAD = "<img src=x onerror=window.__xss=1>"


@pytest.fixture
def xss_pharmacy():
    # Unique pincode so the search shows this pharmacy alone.
    p = make_pharmacy(name=f"XSS {PAYLOAD} {uid()}", address=f"Lane {PAYLOAD}", pincode="500098",
                      lat=17.30, lng=78.30)
    make_stock(p, "Dolo 650", 30)
    return p


def _no_img_request(monitor):
    # If the payload were parsed as HTML, the browser would request "/x".
    assert not any(re.search(r"/x$", r) for r in monitor.bad_responses + monitor.failed_requests)


def test_xss_search_map_popups(page, monitor, xss_pharmacy):
    monitor.allow(404, r"/x$")  # recorded separately below
    page.goto(f"/medicines/search/?q=Dolo&pincode={xss_pharmacy.pincode}")
    expect(page.locator("#resultsList")).to_contain_text(PAYLOAD)  # shown as text
    page.locator("#btnMapView").click()
    page.locator("#map .leaflet-marker-icon").first.click(force=True)
    expect(page.locator(".leaflet-popup-content")).to_contain_text(PAYLOAD)
    page.locator("#btnListView").click()
    page.get_by_role("button", name="Pin on Map").first.click()
    expect(page.locator(".leaflet-popup-content")).to_have_count(1)  # old popup fades out
    expect(page.locator(".leaflet-popup-content")).to_contain_text(PAYLOAD)
    xss_not_run(page)
    assert page.locator(".leaflet-popup-content img").count() == 0
    _no_img_request(monitor)


def test_xss_medicine_detail_map(page, monitor, xss_pharmacy):
    monitor.allow(404, r"/x$")
    page.goto(f"/medicines/{medicine_id('Dolo 650')}/")
    expect(page.locator("main")).to_contain_text(PAYLOAD)
    for i in range(page.locator("#map .leaflet-marker-icon").count()):
        page.locator("#map .leaflet-marker-icon").nth(i).click(force=True)
        xss_not_run(page)
    assert page.locator(".leaflet-popup-content img").count() == 0
    xss_not_run(page)
    _no_img_request(monitor)


def test_xss_pharmacy_detail_and_discovery(page, monitor, xss_pharmacy):
    monitor.allow(404, r"/x$")
    page.goto(f"/pharmacies/{xss_pharmacy.pk}/")
    expect(page.locator("h3")).to_contain_text(PAYLOAD)
    expect(page.locator(".leaflet-popup-content")).to_contain_text(PAYLOAD)
    xss_not_run(page)

    page.goto(f"/pharmacies/?pincode={xss_pharmacy.pincode}")
    expect(page.locator("#resultsList")).to_contain_text(PAYLOAD)
    page.locator("#btnMapView").click()
    page.locator("#map .leaflet-marker-icon").first.click(force=True)
    expect(page.locator(".leaflet-popup-content")).to_contain_text(PAYLOAD)
    page.locator("#btnListView").click()
    page.get_by_role("button", name="Pin").first.click()
    expect(page.locator(".leaflet-popup-content")).to_have_count(1)  # old popup fades out
    expect(page.locator(".leaflet-popup-content")).to_contain_text(PAYLOAD)
    xss_not_run(page)
    page.goto("/")  # featured pharmacies on the home page
    xss_not_run(page)
    _no_img_request(monitor)


def test_xss_admin_pending_pages(page, monitor):
    monitor.allow(404, r"/x$")
    p = make_pharmacy(name=f"Pending {PAYLOAD} {uid()}", approved=False, address=PAYLOAD)
    login(page, "admin", "admin123")
    expect(page.locator("main")).to_contain_text(PAYLOAD)  # admin dashboard pending queue
    xss_not_run(page)
    page.goto("/pharmacies/manage/list/?status=pending")
    expect(page.locator("tbody")).to_contain_text(p.pharmacy_name)
    xss_not_run(page)
    page.goto(f"/pharmacies/{p.pk}/")  # admin may view a pending pharmacy
    expect(page.locator("h3")).to_contain_text(PAYLOAD)
    xss_not_run(page)
    _no_img_request(monitor)


# ------------------------------------------------------------------ role access
CASES = [
    # (who, url, expected path prefix after redirect, expected message)
    ("anon", "/dashboard/customer/", "/accounts/login/?next=/dashboard/customer/", None),
    ("anon", "/inventory/", "/accounts/login/?next=/inventory/", None),
    ("anon", "/dashboard/admin-portal/", "/accounts/login/?next=/dashboard/admin-portal/", None),
    ("customer", "/dashboard/admin-portal/", "/dashboard/customer/", "Administrator privileges required"),
    ("customer", "/inventory/", "/dashboard/customer/", "Only registered Pharmacy Owners"),
    ("customer", "/requests/pharmacy-inbox/", "/dashboard/customer/", "Only registered Pharmacy Owners"),
    ("customer", "/medicines/manage/", "/dashboard/customer/", "Administrator privileges required"),
    ("customer", "/pharmacies/manage/users/", "/dashboard/customer/", "Administrator privileges required"),
    ("pharmacy", "/requests/my-requests/", "/dashboard/pharmacy/", "designated for customers"),
    ("pharmacy", "/dashboard/customer/", "/dashboard/pharmacy/", "designated for customers"),
    ("pharmacy", "/dashboard/admin-portal/", "/dashboard/pharmacy/", "Administrator privileges required"),
    ("pharmacy", "/pharmacies/manage/list/", "/dashboard/pharmacy/", "Administrator privileges required"),
]


@pytest.mark.parametrize("who,url,dest,msg", CASES)
def test_direct_url_access_by_role(page, who, url, dest, msg):
    if who == "customer":
        login(page, make_customer().username)
    elif who == "pharmacy":
        login(page, make_pharmacy().owner.username)
    page.goto(url)
    page.wait_for_load_state()
    assert url_path(page) == dest
    if msg:
        expect(page.locator(".alert-danger.alert-dismissible")).to_contain_text(msg)


def test_owner_cannot_touch_other_pharmacy_stock_or_requests(page, monitor):
    other = make_pharmacy()
    inv = make_stock(other, "Dolo 650", 30)
    from helpers import make_request
    req = make_request(make_customer(), other, "Dolo 650")
    monitor.allow(404, r"/(inventory|requests)/\d+/")
    login(page, make_pharmacy().owner.username)
    for path in (f"/inventory/{inv.pk}/edit/", f"/inventory/{inv.pk}/delete/", f"/requests/{req.pk}/respond/"):
        resp = page.goto(path)
        assert resp.status == 404, path


def test_customer_cannot_open_django_admin(page):
    login(page, make_customer().username)
    page.goto("/admin/")
    assert "/admin/login/" in page.url
    expect(page.locator("main, #content").first).to_contain_text(re.compile("not authorized|authenticated as", re.I))


def test_get_logout_is_405_and_keeps_session(page, monitor):
    monitor.allow(405, r"/accounts/logout/$")
    u = make_customer()
    login(page, u.username)
    resp = page.goto("/accounts/logout/")
    assert resp.status == 405
    page.goto("/dashboard/customer/")
    assert url_path(page) == "/dashboard/customer/"
