"""2. Registration, login, logout, password reset, profile edit, change password."""
import re
import time

from playwright.sync_api import expect

from helpers import PASSWORD, alerts, login, logout, make_customer, uid, url_path


def _fill_customer(page, username, password=PASSWORD, confirm=None, email=None):
    page.goto("/accounts/register/customer/")
    page.get_by_placeholder("First Name").fill("Asha")
    page.get_by_placeholder("Last Name").fill("Rao")
    page.get_by_placeholder("e.g. john_doe").fill(username)
    page.get_by_placeholder("name@example.com").fill(email or f"{username}@e2e.test")
    page.get_by_placeholder("+91 9876543210").fill("+91 9876543210")
    page.locator("#id_cust_password").fill(password)
    page.locator("#id_cust_confirm_password").fill(confirm if confirm is not None else password)
    page.locator("main form button[type=submit]").click()
    page.wait_for_load_state()


def test_customer_registration_valid_then_login(page):
    username = uid("newcust")
    _fill_customer(page, username)
    assert url_path(page).startswith("/accounts/login/")
    expect(page.locator(".alert-success.alert-dismissible")).to_contain_text("Account created successfully")
    login(page, username)
    assert url_path(page) == "/dashboard/customer/"


def test_customer_registration_duplicate_username(page):
    _fill_customer(page, "customer1", email=f"{uid()}@e2e.test")
    assert url_path(page) == "/accounts/register/customer/"
    expect(page.get_by_text("This username is already taken.")).to_be_visible()


def test_customer_registration_weak_password(page):
    _fill_customer(page, uid("weak"), password="12345", confirm="12345")
    assert url_path(page) == "/accounts/register/customer/"
    body = page.locator("form").inner_text()
    assert "too short" in body or "too common" in body or "entirely numeric" in body


def test_customer_registration_mismatched_passwords(page):
    _fill_customer(page, uid("mm"), password=PASSWORD, confirm=PASSWORD + "x")
    assert url_path(page) == "/accounts/register/customer/"
    expect(page.get_by_text("Passwords do not match.")).to_be_visible()


def _fill_pharmacy(page, tag, pincode="500001", lat="17.400000", lng="78.400000"):
    page.goto("/accounts/register/pharmacy/")
    page.get_by_placeholder("Owner First Name").fill("Ravi")
    page.get_by_placeholder("Owner Last Name").fill("Kumar")
    page.get_by_placeholder("Username for login").fill(f"{tag}_owner")
    page.get_by_placeholder("owner@pharmacy.com").fill(f"{tag}@e2e.test")
    page.get_by_placeholder("Owner mobile number").fill("+91 9123456789")
    page.locator("#id_pharm_password").fill(PASSWORD)
    page.locator("#id_pharm_confirm_password").fill(PASSWORD)
    page.get_by_placeholder("e.g. City Life Pharmacy").fill(f"Reg Test {tag}")
    page.get_by_placeholder("e.g. DL-PH-2024-9988").fill(f"REG-{tag}")
    page.get_by_placeholder("Building, Street, Landmark").fill("12 Market Road")
    page.get_by_placeholder("e.g. Hyderabad").fill("Hyderabad")
    page.get_by_placeholder("e.g. Telangana").fill("Telangana")
    page.get_by_placeholder("500001").fill(pincode)
    page.get_by_placeholder("Pharmacy phone").fill("+91 9123400000")
    page.get_by_placeholder("17.385044").fill(lat)
    page.get_by_placeholder("78.486671").fill(lng)
    page.locator("main form button[type=submit]").click()
    page.wait_for_load_state()


def test_pharmacy_registration_valid(page):
    from pharmacies.models import Pharmacy
    tag = uid("reg")
    _fill_pharmacy(page, tag)
    assert url_path(page).startswith("/accounts/login/")
    expect(page.locator(".alert-success.alert-dismissible")).to_contain_text("Pharmacy registration submitted")
    p = Pharmacy.objects.get(registration_number=f"REG-{tag}")
    assert p.approval_status == "PENDING" and not p.is_approved
    login(page, f"{tag}_owner")
    assert url_path(page) == "/dashboard/pharmacy/"
    expect(page.get_by_text("Pending Approval").first).to_be_visible()


def test_pharmacy_registration_bad_pincode(page):
    tag = uid("badpin")
    _fill_pharmacy(page, tag, pincode="01234")
    assert url_path(page) == "/accounts/register/pharmacy/"
    expect(page.get_by_text("Enter a valid 6-digit PIN code")).to_be_visible()


def _invalid_or_error(page, selector, server_text):
    """Out-of-range numbers are rejected by the browser (HTML5) or by the server."""
    if url_path(page) != "/accounts/register/pharmacy/":
        return False
    msg = page.locator(selector).evaluate("el => el.validationMessage")
    return bool(msg) or page.get_by_text(server_text).count() > 0


def test_pharmacy_registration_lat_lng_out_of_range(page):
    from pharmacies.models import Pharmacy
    tag = uid("badlat")
    _fill_pharmacy(page, tag, lat="95", lng="78.4")
    assert _invalid_or_error(page, "input[name=latitude]", "less than or equal to 90")
    tag2 = uid("badlng")
    _fill_pharmacy(page, tag2, lat="17.4", lng="-200")
    assert _invalid_or_error(page, "input[name=longitude]", "greater than or equal to -180")
    assert not Pharmacy.objects.filter(registration_number__in=[f"REG-{tag}", f"REG-{tag2}"]).exists()


def test_login_valid_and_wrong_password(page):
    u = make_customer()
    login(page, u.username, "wrong-password", expect_ok=False)
    assert url_path(page) == "/accounts/login/"
    expect(page.locator(".alert-danger.alert-dismissible")).to_contain_text("Invalid username or password")
    login(page, u.username)
    assert url_path(page) == "/dashboard/customer/"


def test_login_lockout_after_five_failures(page, monitor):
    monitor.allow(429, r"/accounts/login/")
    u = make_customer()
    for _ in range(5):
        login(page, u.username, "nope-nope", expect_ok=False)
        expect(page.locator(".alert-danger.alert-dismissible")).to_contain_text("Invalid username or password")
    login(page, u.username, PASSWORD, expect_ok=False)  # even the right password is blocked now
    expect(page.locator(".alert-danger.alert-dismissible")).to_contain_text("Too many failed login attempts")
    assert url_path(page) == "/accounts/login/"


def test_logout_button(page):
    u = make_customer()
    login(page, u.username)
    logout(page)
    assert url_path(page) == "/"
    expect(page.get_by_role("link", name="Sign In")).to_be_visible()
    page.goto("/dashboard/customer/")
    assert url_path(page).startswith("/accounts/login/")


def test_password_reset_flow(page, server_log_path):
    u = make_customer()
    page.goto("/accounts/login/")
    page.get_by_role("link", name=re.compile("Forgot", re.I)).click()
    page.wait_for_url(re.compile(r"/accounts/password-reset/$"))
    page.locator("#id_email").fill(u.email)
    page.locator("main form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/password-reset/done/$"))
    expect(page.locator("h3")).to_have_text("Check Your Email")

    # The console email backend writes the mail to the server log.
    link = None
    for _ in range(20):
        found = re.findall(r"http://[^\s]+/accounts/password-reset-confirm/[^\s]+/", server_log_path.read_text())
        if found:
            link = found[-1]
            break
        time.sleep(0.25)
    assert link, "reset email not found in server log"
    page.goto(link)
    new_pw = PASSWORD + "R"
    page.locator("#id_reset_new_password1").fill(new_pw)
    page.locator("#id_reset_new_password2").fill(new_pw)
    page.locator("main form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/password-reset/complete/$"))
    expect(page.locator("h3")).to_have_text("Password Successfully Reset")
    login(page, u.username, new_pw)


def test_profile_edit(page):
    u = make_customer()
    login(page, u.username)
    page.locator("a.dropdown-toggle:has(.bi-person-circle)").click()
    page.get_by_role("link", name="My Profile").click()
    page.wait_for_url(re.compile(r"/accounts/profile/$"))
    page.locator("#id_first_name").fill("Meera")
    page.locator("#id_phone_number").fill("+91 9000011111")
    page.locator("form:has(input[value=user]) button[type=submit]").click()
    page.wait_for_load_state()
    expect(page.locator(".alert-success.alert-dismissible")).to_contain_text("Personal profile updated")
    expect(page.locator("#id_first_name")).to_have_value("Meera")
    expect(page.locator("#id_phone_number")).to_have_value("+91 9000011111")
    # invalid phone is rejected
    page.locator("#id_phone_number").fill("abc")
    page.locator("form:has(input[value=user]) button[type=submit]").click()
    page.wait_for_load_state()
    expect(page.locator(".alert-danger.alert-dismissible")).to_contain_text("Please correct the errors")


def test_change_password(page):
    u = make_customer()
    login(page, u.username)
    page.goto("/accounts/profile/")
    page.get_by_role("link", name=re.compile("Change Password", re.I)).first.click()
    page.wait_for_url(re.compile(r"/accounts/password-change/$"))
    new_pw = PASSWORD + "C"
    page.locator("#id_old_password").fill(PASSWORD)
    page.locator("#id_new_password1").fill(new_pw)
    page.locator("#id_new_password2").fill(new_pw)
    page.locator("main form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/password-change/done/$"))
    expect(page.locator("h3")).to_have_text("Password Successfully Changed")
    logout(page)
    login(page, u.username, PASSWORD, expect_ok=False)
    expect(page.locator(".alert-danger.alert-dismissible")).to_be_visible()
    login(page, u.username, new_pw)
