"""4. Pharmacy owner: dashboard/charts, approval notice, stock CRUD, inventory list, inbox, profile, revoked."""
import re

from playwright.sync_api import expect

from helpers import login, make_customer, make_pharmacy, make_request, make_stock, uid, url_path


def owner_login(page, pharmacy):
    login(page, pharmacy.owner.username)
    assert url_path(page) == "/dashboard/pharmacy/"


def chart_data(page):
    page.wait_for_function("() => window.Chart && Chart.getChart('inventoryDoughnutChart')")
    return page.evaluate("Chart.getChart('inventoryDoughnutChart').data.datasets[0].data")


def test_dashboard_and_chart_seeded_pharmacy(page):
    from inventory.models import Inventory
    login(page, "apollo_owner", "password123")
    expect(page.locator("h2")).to_contain_text("Apollo Healthcare Store")
    expect(page.get_by_text("Verified Partner")).to_be_visible()
    data = chart_data(page)
    assert sum(data) == Inventory.objects.filter(pharmacy__owner__username="apollo_owner").count()


def test_dashboard_brand_new_pharmacy_no_stock(page):
    p = make_pharmacy()
    owner_login(page, p)
    assert chart_data(page) == [0, 0, 0]
    expect(page.get_by_text("No Inventory Stocked")).to_be_visible()
    page.get_by_role("link", name="Add Medicine Stock").click()
    page.wait_for_url(re.compile(r"/inventory/add/$"))


def test_approval_notification(page, new_context):
    p = make_pharmacy(approved=False)
    owner_login(page, p)
    expect(page.get_by_text("Pending Approval").first).to_be_visible()

    admin = new_context().new_page()
    login(admin, "admin", "admin123")
    admin.goto(f"/pharmacies/manage/list/?status=pending&q={p.registration_number}")
    admin.locator("tr", has_text=p.pharmacy_name).get_by_role("button", name="Approve").click()
    admin.wait_for_load_state()
    expect(admin.locator(".alert-success.alert-dismissible")).to_contain_text("has been approved")

    page.reload()
    bell = page.locator("a[title=Notifications] .badge")
    expect(bell).to_have_text("1")
    page.locator("a[title=Notifications]").click()
    page.wait_for_url(re.compile(r"/accounts/notifications/"))
    expect(page.get_by_text(re.compile("has been approved by the MediFind administrator"))).to_be_visible()
    page.goto("/dashboard/pharmacy/")
    expect(page.get_by_text("Verified Partner")).to_be_visible()


def _status_of(page, medicine):
    return page.locator("tbody tr", has_text=medicine).locator(
        ".badge-in-stock, .badge-low-stock, .badge-out-stock").inner_text()


def test_add_stock_set_quantity_and_delete(page):
    p = make_pharmacy()
    owner_login(page, p)
    page.get_by_role("link", name=re.compile("Add Stock")).first.click()
    page.wait_for_url(re.compile(r"/inventory/add/$"))
    page.locator("#id_medicine").select_option(label="Dolo 650 (650mg) - Tablet")
    page.locator("#id_quantity").fill("25")
    page.locator("main form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/inventory/$"))
    expect(page.locator(".alert-success.alert-dismissible")).to_contain_text("Added Dolo 650 (25 units)")
    assert _status_of(page, "Dolo 650") == "In Stock"

    for qty, label in (("10", "Low Stock"), ("0", "Out of Stock")):
        page.locator("tbody tr", has_text="Dolo 650").get_by_role("link", name="Update").click()
        page.wait_for_url(re.compile(r"/inventory/\d+/edit/$"))
        page.locator("#id_quantity").fill(qty)
        page.locator("main form button[type=submit]").click()
        page.wait_for_url(re.compile(r"/inventory/$"))
        expect(page.locator(".alert-success.alert-dismissible")).to_contain_text(f"stock to {qty} units")
        assert _status_of(page, "Dolo 650") == label

    # negative quantity is blocked by the browser (min=0) and nothing changes
    page.locator("tbody tr", has_text="Dolo 650").get_by_role("link", name="Update").click()
    page.locator("#id_quantity").fill("-5")
    page.locator("main form button[type=submit]").click()
    assert re.search(r"/inventory/\d+/edit/$", page.url)
    assert page.locator("#id_quantity").evaluate("el => el.validationMessage")

    # adding the same medicine again updates the quantity
    page.goto("/inventory/add/")
    page.locator("#id_medicine").select_option(label="Dolo 650 (650mg) - Tablet")
    page.locator("#id_quantity").fill("40")
    page.locator("main form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/inventory/$"))
    expect(page.locator(".alert-info.alert-dismissible")).to_contain_text("already in your inventory")
    assert _status_of(page, "Dolo 650") == "In Stock"

    # public view follows the owner's stock
    page.goto(f"/pharmacies/{p.pk}/")
    expect(page.locator("tbody tr", has_text="Dolo 650")).to_contain_text("40")

    # delete
    page.goto("/inventory/")
    page.locator("tbody tr", has_text="Dolo 650").locator("a[title='Remove Record']").click()
    page.wait_for_url(re.compile(r"/inventory/\d+/delete/$"))
    page.locator("main form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/inventory/$"))
    expect(page.locator(".alert-success.alert-dismissible")).to_contain_text("Removed 'Dolo 650'")
    expect(page.locator("tbody tr", has_text="Dolo 650")).to_have_count(0)


def test_inventory_search_filter_sort(page):
    p = make_pharmacy()
    for name, qty in (("Dolo 650", 50), ("Pan 40", 3), ("Telma 40", 0), ("Omez 20", 8), ("Cetzine 10mg", 15)):
        make_stock(p, name, qty)
    owner_login(page, p)
    page.goto("/inventory/")
    rows = page.locator("main tbody tr")
    expect(rows).to_have_count(5)

    page.get_by_placeholder(re.compile("Search inventory")).fill("Pan")
    page.get_by_role("button", name="Filter").click()
    page.wait_for_load_state()
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("Pan 40")

    page.get_by_role("link", name="Clear").click()
    page.wait_for_load_state()
    page.locator("main select[name=status]").select_option("LOW_STOCK")
    page.get_by_role("button", name="Filter").click()
    page.wait_for_load_state()
    expect(rows).to_have_count(2)

    page.locator("main select[name=status]").select_option("")
    page.locator("main select[name=sort]").select_option("qty_asc")
    page.get_by_role("button", name="Filter").click()
    page.wait_for_load_state()
    qtys = [int(re.search(r"(\d+) units", t).group(1)) for t in rows.all_inner_texts()]
    assert qtys == sorted(qtys) == [0, 3, 8, 15, 50]
    page.locator("main select[name=sort]").select_option("name")
    page.get_by_role("button", name="Filter").click()
    page.wait_for_load_state()
    names = [t.split("\n")[0].strip() for t in rows.locator("td:first-child").all_inner_texts()]
    assert names == sorted(names, key=str.lower), names


def test_inbox_confirm_decline_and_second_response_blocked(page, new_context):
    p = make_pharmacy()
    make_stock(p, "Dolo 650", 30)
    make_stock(p, "Pan 40", 0)
    cust = make_customer()
    r1 = make_request(cust, p, "Dolo 650", qty=2)
    r2 = make_request(cust, p, "Pan 40")

    owner_login(page, p)
    page.get_by_role("link", name=re.compile("Inquiries")).click()
    page.wait_for_url(re.compile(r"/requests/pharmacy-inbox/"))
    expect(page.locator("tbody tr")).to_have_count(2)

    page.locator("tbody tr", has_text="Dolo 650").get_by_role("link", name="Respond").click()
    page.wait_for_url(re.compile(rf"/requests/{r1.pk}/respond/$"))
    page.locator("#id_status").select_option("CONFIRMED")
    page.locator("#id_pharmacy_response").fill("Held at counter until 7 PM")
    page.locator("main form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/requests/pharmacy-inbox/"))
    expect(page.locator(".alert-success.alert-dismissible")).to_contain_text(f"Request #{r1.pk}")

    page.locator("tbody tr", has_text="Pan 40").get_by_role("link", name="Respond").click()
    page.locator("#id_status").select_option("UNAVAILABLE")
    page.locator("#id_pharmacy_response").fill("Out until Monday")
    page.locator("main form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/requests/pharmacy-inbox/"))

    # second response is blocked
    page.goto(f"/requests/{r1.pk}/respond/")
    page.wait_for_url(re.compile(r"/requests/pharmacy-inbox/"))
    expect(page.locator(".alert-info.alert-dismissible")).to_contain_text("already been answered")
    page.goto("/requests/pharmacy-inbox/?status=ALL")
    expect(page.locator("tbody tr", has_text="Dolo 650")).to_contain_text("Answered")

    r1.refresh_from_db()
    r2.refresh_from_db()
    assert (r1.status, r1.pharmacy_response) == ("CONFIRMED", "Held at counter until 7 PM")
    assert (r2.status, r2.pharmacy_response) == ("UNAVAILABLE", "Out until Monday")

    c = new_context().new_page()
    login(c, cust.username)
    c.goto("/requests/my-requests/")
    expect(c.locator("tbody tr", has_text="Dolo 650")).to_contain_text("Confirmed Available")
    expect(c.locator("tbody tr", has_text="Dolo 650")).to_contain_text("Held at counter until 7 PM")
    expect(c.locator("tbody tr", has_text="Pan 40")).to_contain_text("Reported Unavailable")
    expect(c.locator("a[title=Notifications] .badge")).to_have_text("2")


def test_profile_edit_address_sends_back_to_pending(page):
    from pharmacies.models import Pharmacy
    p = make_pharmacy()
    make_stock(p, "Dolo 650", 30)
    owner_login(page, p)

    # phone only: stays approved
    page.locator("a.dropdown-toggle:has(.bi-person-circle)").click()
    page.get_by_role("link", name="Edit Pharmacy Info").click()
    page.wait_for_url(re.compile(r"/pharmacies/profile/edit/$"))
    page.locator("#id_phone_number").fill("+91 9000099999")
    page.locator("main form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/dashboard/pharmacy/$"))
    expect(page.locator(".alert-success.alert-dismissible")).to_contain_text("updated successfully")
    p.refresh_from_db()
    assert p.approval_status == Pharmacy.STATUS_APPROVED

    # address: back to pending, hidden from search
    page.goto("/pharmacies/profile/edit/")
    page.locator("#id_address").fill("99 New Address Road")
    page.locator("main form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/dashboard/pharmacy/$"))
    expect(page.locator(".alert-warning.alert-dismissible")).to_contain_text("hidden from search")
    expect(page.get_by_text("Pending Approval").first).to_be_visible()
    p.refresh_from_db()
    assert p.approval_status == Pharmacy.STATUS_PENDING
    page.goto(f"/medicines/search/?q=Dolo&pincode={p.pincode}")
    expect(page.locator("#resultsList", has_text=p.pharmacy_name)).to_have_count(0)


def test_profile_page_pharmacy_form(page):
    from pharmacies.models import Pharmacy
    p = make_pharmacy()
    owner_login(page, p)
    page.goto("/accounts/profile/")
    page.locator("#id_pharmacy_city").fill("Secunderabad")
    page.locator("form:has(input[value=pharmacy]) button[type=submit]").click()
    page.wait_for_url(re.compile(r"/accounts/profile/$"))
    expect(page.locator(".alert-warning.alert-dismissible")).to_contain_text("hidden from search")
    p.refresh_from_db()
    assert p.city == "Secunderabad" and p.approval_status == Pharmacy.STATUS_PENDING


def test_revoked_pharmacy_cannot_edit_stock(page):
    from pharmacies.models import Pharmacy
    p = make_pharmacy()
    inv = make_stock(p, "Dolo 650", 30)
    cust = make_customer()
    req = make_request(cust, p, "Dolo 650")
    p.approval_status = Pharmacy.STATUS_REVOKED
    p.save()

    owner_login(page, p)
    expect(page.get_by_text("Approval Revoked", exact=True)).to_be_visible()
    page.goto("/inventory/add/")
    page.wait_for_url(re.compile(r"/inventory/$"))
    expect(page.locator(".alert-danger.alert-dismissible")).to_contain_text("revoked")
    page.locator("tbody tr", has_text="Dolo 650").get_by_role("link", name="Update").click()
    page.wait_for_url(re.compile(r"/inventory/$"))
    expect(page.locator(".alert-danger.alert-dismissible")).to_contain_text("stock cannot be changed")
    page.goto(f"/inventory/{inv.pk}/delete/")
    page.wait_for_url(re.compile(r"/inventory/$"))
    inv.refresh_from_db()
    assert inv.quantity == 30
    page.goto("/requests/pharmacy-inbox/")
    expect(page.locator("tbody tr", has_text="Dolo 650")).to_contain_text("Locked")
    page.goto(f"/requests/{req.pk}/respond/")
    page.wait_for_url(re.compile(r"/requests/pharmacy-inbox/"))
    expect(page.locator(".alert-danger.alert-dismissible")).to_contain_text("cannot answer requests")
