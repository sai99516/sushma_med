"""3. Admin: dashboard + chart, pending queue, approve, revoke, catalogue, users, requests, /admin/."""
import re

from playwright.sync_api import expect

from helpers import (login, make_customer, make_pharmacy, make_request, make_stock, uid,
                     url_path)

ADMIN = ("admin", "admin123")


def admin_login(page):
    login(page, *ADMIN)
    assert url_path(page) == "/dashboard/admin-portal/"


def test_admin_dashboard_and_chart(page):
    admin_login(page)
    expect(page.locator("h2")).to_contain_text("Operations Command Console")
    # Chart.js drew the category bar chart
    page.wait_for_function("() => window.Chart && Chart.getChart('categoryBarChart')")
    n = page.evaluate("Chart.getChart('categoryBarChart').data.labels.length")
    assert n > 0
    box = page.locator("#categoryBarChart").bounding_box()
    assert box and box["width"] > 50 and box["height"] > 50
    # nav dropdown works
    page.get_by_role("button", name=re.compile("Admin Portal")).or_(
        page.get_by_role("link", name=re.compile("Admin Portal"))).first.click()
    expect(page.get_by_role("link", name="Verify Pharmacies")).to_be_visible()


def test_admin_pending_queue_and_approve_double_click(page, new_context):
    p = make_pharmacy(approved=False, name=f"Queue Pharmacy {uid()}")
    admin_login(page)
    row = page.locator("tr", has_text=p.pharmacy_name)
    expect(row).to_be_visible()  # in the dashboard pending queue

    # Second tab with the same (stale) admin list page open
    page2 = page.context.new_page()
    page2.goto(f"/pharmacies/manage/list/?status=pending&q={p.registration_number}")
    expect(page2.locator("tr", has_text=p.pharmacy_name).get_by_role("button", name="Approve")).to_be_visible()

    # Real double click on the dashboard Approve button
    row.get_by_role("button", name="Approve").dblclick()
    page.wait_for_load_state()
    expect(page.locator(".alert").first).to_contain_text(p.pharmacy_name)
    p.refresh_from_db()
    assert p.approval_status == "APPROVED" and p.is_approved

    # Click Approve again on the stale tab: still approved, no second change
    page2.locator("tr", has_text=p.pharmacy_name).get_by_role("button", name="Approve").click()
    page2.wait_for_load_state()
    expect(page2.locator(".alert-info.alert-dismissible")).to_contain_text("already approved")
    p.refresh_from_db()
    assert p.approval_status == "APPROVED"

    from requests_app.models import Notification
    assert Notification.objects.filter(user=p.owner, message__contains="has been approved").count() == 1


def test_admin_revoke_cancels_requests_and_notifies(page, new_context):
    from requests_app.models import Notification
    p = make_pharmacy(name=f"Revoke Me {uid()}")
    make_stock(p, "Dolo 650", 30)
    cust = make_customer()
    req = make_request(cust, p, "Dolo 650")

    admin_login(page)
    page.goto("/pharmacies/manage/list/?status=approved")
    page.get_by_placeholder(re.compile("Search by pharmacy name")).fill(p.registration_number)
    page.get_by_role("button", name="Search").click()
    page.wait_for_load_state()
    row = page.locator("tr", has_text=p.pharmacy_name)
    row.get_by_role("button", name="Revoke").click()
    page.wait_for_load_state()
    expect(page.locator(".alert-success.alert-dismissible")).to_contain_text("1 pending request(s) were cancelled")

    req.refresh_from_db()
    assert req.status == "CANCELLED"
    # customer sees it as cancelled and got a notification
    c = new_context().new_page()
    login(c, cust.username)
    c.goto("/requests/my-requests/?status=CANCELLED")
    expect(c.locator("tbody tr", has_text="Dolo 650")).to_be_visible()
    c.goto("/accounts/notifications/")
    expect(c.get_by_text(re.compile("no longer approved"))).to_be_visible()
    # owner notified
    o = new_context().new_page()
    login(o, p.owner.username)
    o.goto("/accounts/notifications/")
    expect(o.get_by_text(re.compile("has been revoked"))).to_be_visible()
    # hidden from public search
    o.goto(f"/medicines/search/?q={p.pharmacy_name}")
    o.goto(f"/medicines/search/?q=Dolo&pincode={p.pincode}")
    expect(o.locator("#resultsList", has_text=p.pharmacy_name)).to_have_count(0)
    assert Notification.objects.filter(user=p.owner, message__contains="revoked").count() == 1


def test_admin_medicine_catalogue_add_edit_archive(page):
    name = f"E2E Testamol {uid()}"
    admin_login(page)
    page.goto("/medicines/manage/")
    page.get_by_role("link", name=re.compile("Add")).first.click()
    page.wait_for_url(re.compile(r"/medicines/add/$"))
    page.locator("#id_medicine_name").fill(name)
    page.locator("#id_generic_name").fill("Testacetamol")
    page.locator("#id_strength").fill("250mg")
    page.locator("#id_dosage_form").select_option("Tablet")
    page.locator("#id_category").select_option("Antipyretic")
    page.locator("#id_description").fill("Made by the e2e test")
    page.locator("main form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/medicines/manage/$"))
    expect(page.locator(".alert-success.alert-dismissible")).to_contain_text(name)

    # duplicate is rejected
    page.goto("/medicines/add/")
    page.locator("#id_medicine_name").fill(name.upper())
    page.locator("#id_generic_name").fill("Testacetamol")
    page.locator("#id_strength").fill("250MG")
    page.locator("#id_dosage_form").select_option("Tablet")
    page.locator("main form button[type=submit]").click()
    page.wait_for_load_state()
    assert url_path(page) == "/medicines/add/"
    expect(page.locator("main")).to_contain_text("already exists")

    # edit
    page.goto(f"/medicines/manage/?q={name}")
    page.locator("tr", has_text=name).get_by_role("link", name="Edit").click()
    page.locator("#id_strength").fill("300mg")
    page.locator("main form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/medicines/manage/$"))
    page.goto(f"/medicines/manage/?q={name}")
    expect(page.locator("tr", has_text=name)).to_contain_text("300mg")

    # archive: hidden from the add-stock form and public search
    page.locator("tr", has_text=name).get_by_role("link", name="Edit").click()
    page.locator("#id_is_active").uncheck()
    page.locator("main form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/medicines/manage/$"))
    page.goto(f"/medicines/manage/?q={name}")
    expect(page.locator("tr", has_text=name)).to_contain_text("Archived")
    from medicines.models import Medicine
    assert Medicine.objects.get(medicine_name=name).is_active is False


def test_admin_users_and_requests_lists(page):
    cust = make_customer()
    p = make_pharmacy()
    make_stock(p, "Pan 40", 20)
    make_request(cust, p, "Pan 40")
    admin_login(page)

    page.goto("/pharmacies/manage/users/")
    page.get_by_placeholder(re.compile("Search by username")).fill(cust.username)
    page.get_by_role("button", name="Search").click()
    page.wait_for_load_state()
    expect(page.locator("tbody tr", has_text=cust.username)).to_be_visible()
    page.goto("/pharmacies/manage/users/?role=pharmacy")
    expect(page.locator("tbody")).not_to_contain_text("customer1")

    page.goto("/pharmacies/manage/requests/")
    page.get_by_placeholder(re.compile("Search by patient")).fill(cust.username)
    page.get_by_role("button", name="Search").click()
    page.wait_for_load_state()
    expect(page.locator("tbody tr", has_text="Pan 40")).to_be_visible()
    page.get_by_role("link", name="Confirmed", exact=True).click()
    page.wait_for_load_state()
    expect(page.locator("tbody", has_text=cust.username)).to_have_count(0)


def test_django_admin_login(page):
    page.goto("/admin/")
    assert "/admin/login/" in page.url
    page.locator("#id_username").fill(ADMIN[0])
    page.locator("#id_password").fill(ADMIN[1])
    page.get_by_role("button", name="Log in").click()
    page.wait_for_load_state()
    expect(page.locator("#site-name, h1").first).to_be_visible()
    expect(page.get_by_text("Site administration")).to_be_visible()
    page.locator("a[href='/admin/pharmacies/pharmacy/']").first.click()
    page.wait_for_load_state()
    expect(page.locator("#result_list")).to_contain_text("Apollo")
