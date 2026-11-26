"""
Takes real screenshots of MediFind for the report, saved to docs/screenshots/.

Run from the project folder (needs requirements-dev.txt and `python -m playwright install chromium`):

    python scripts/take_screenshots.py

It builds a temporary database (migrate + seed_data), adds one partially answered request and an
approval history, starts the app on port 8010 (and a DEBUG=False copy on 8011 for the 404 page),
and saves the screenshots at 1366x768. db.sqlite3 is never touched. Map tiles come from the real
OpenStreetMap server, so it needs internet.
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
PORT, PORT_404 = 8010, 8011
PY = str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable

TMP = Path(tempfile.mkdtemp(prefix="medifind_shots_"))
ENV = {**os.environ, "DEBUG": "True", "DATABASE_URL": f"sqlite:///{TMP / 'shots.sqlite3'}"}
ENV_404 = {**ENV, "DEBUG": "False", "SECRET_KEY": "screenshots-only-not-secret", "ALLOWED_HOSTS": "127.0.0.1",
           "SECURE_SSL_REDIRECT": "False", "USE_MANIFEST_STATIC": "False"}

# Same optional system-library folder as e2e/conftest.py (Chromium on no-sudo Linux setups).
_extra_libs = Path.home() / ".local/pwlibs/root/usr/lib/x86_64-linux-gnu"
if _extra_libs.is_dir():
    os.environ["LD_LIBRARY_PATH"] = f"{_extra_libs}:{os.environ.get('LD_LIBRARY_PATH', '')}"


def manage(*args):
    subprocess.run([PY, "manage.py", *args], cwd=ROOT, env=ENV, check=True, stdout=subprocess.DEVNULL)


def start_server(port, env):
    proc = subprocess.Popen([PY, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.time() + 30
    while time.time() < end:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return proc
        time.sleep(0.2)
    proc.terminate()
    raise RuntimeError(f"server did not start on port {port}")


def prepare_data():
    """Adds a partial answer and an approval history to the seeded data (through the app's services)."""
    os.environ.update({"DEBUG": "True", "DATABASE_URL": ENV["DATABASE_URL"],
                       "DJANGO_SETTINGS_MODULE": "config.settings",
                       # Playwright's sync API runs an event loop; the ORM is used from plain code only.
                       "DJANGO_ALLOW_ASYNC_UNSAFE": "true"})
    sys.path.insert(0, str(ROOT))
    import django
    django.setup()
    from accounts.models import User
    from inventory.models import Inventory
    from pharmacies.models import Pharmacy
    from requests_app.services import create_availability_inquiry, respond_to_availability_inquiry

    apollo = Pharmacy.objects.get(owner__username="apollo_owner")
    item = (Inventory.objects.filter(pharmacy=apollo, medicine__medicine_name__icontains="Dolo").first()
            or Inventory.objects.filter(pharmacy=apollo).first())
    customer = User.objects.get(username="customer1")
    req = create_availability_inquiry(customer, apollo, item.medicine, 100, "Needed for my family this week.")
    respond_to_availability_inquiry(req.pk, apollo, "PARTIAL", "60 strips ready at the counter; rest on Monday.",
                                    available_quantity=60)
    # One new pending request so the owner's inbox has something to answer.
    medplus_item = Inventory.objects.filter(pharmacy__owner__username="medplus_owner").first()
    create_availability_inquiry(customer, medplus_item.pharmacy, medplus_item.medicine, 2, "Will pick up tonight.")
    return item.pharmacy.pk, item.medicine.pk


def approve_metro():
    from accounts.models import User
    from pharmacies.models import Pharmacy
    from pharmacies.services import set_pharmacy_approval
    admin = User.objects.get(username="admin")
    metro = Pharmacy.objects.get(owner__username="pending_owner")
    set_pharmacy_approval(metro.pk, True, admin)
    set_pharmacy_approval(metro.pk, False, admin, reason="Licence copy expired; please upload the renewed licence.")
    set_pharmacy_approval(metro.pk, True, admin, reason="Renewed licence checked.")
    return metro.pk


def main():
    from playwright.sync_api import sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    manage("migrate", "--noinput")
    manage("seed_data")
    pharmacy_id, medicine_id = prepare_data()
    server = start_server(PORT, ENV)
    server_404 = start_server(PORT_404, ENV_404)
    base = f"http://127.0.0.1:{PORT}"
    hyderabad = {"latitude": 17.4065, "longitude": 78.4772}
    saved = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()

            def new_page():
                ctx = browser.new_context(viewport={"width": 1366, "height": 768}, base_url=base,
                                          geolocation=hyderabad, permissions=["geolocation"])
                return ctx.new_page()

            def shot(page, name, full_page=False):
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(800)  # map tiles and charts finish drawing
                page.screenshot(path=str(OUT / f"{name}.png"), full_page=full_page)
                saved.append(name)

            def login(page, username, password):
                page.goto("/accounts/login/")
                page.get_by_placeholder("Enter your username").fill(username)
                page.get_by_placeholder("Enter your password").fill(password)
                page.locator("form button[type=submit]").first.click()
                page.wait_for_load_state()

            # Visitor
            page = new_page()
            page.goto("/")
            shot(page, "01_home")
            page.goto(f"/medicines/search/?q=Dolo&lat={hyderabad['latitude']}&lng={hyderabad['longitude']}"
                      "&sort=distance")
            page.locator("#btnMapView").click()
            page.locator("#mapContainer").scroll_into_view_if_needed()
            page.evaluate("window.scrollBy(0, -120)")
            shot(page, "02_search_results_map")
            page.goto(f"/medicines/{medicine_id}/?lat={hyderabad['latitude']}&lng={hyderabad['longitude']}"
                      "&sort=distance")
            shot(page, "03_medicine_detail_distances", full_page=True)

            # Customer
            page = new_page()
            login(page, "customer1", "password123")
            page.goto(f"/requests/create/{pharmacy_id}/{medicine_id}/")
            shot(page, "04_customer_request_form")
            page.goto("/requests/my-requests/")
            shot(page, "05_my_requests_partial")

            # Pharmacy owner
            page = new_page()
            login(page, "apollo_owner", "password123")
            page.goto("/dashboard/pharmacy/")
            shot(page, "06_pharmacy_dashboard")
            page.goto("/requests/pharmacy-inbox/?status=ALL")
            shot(page, "07_pharmacy_inbox")

            # Admin
            page = new_page()
            login(page, "admin", "admin123")
            page.goto("/dashboard/admin-portal/")
            shot(page, "08_admin_dashboard")
            metro_id = approve_metro()
            page.goto("/pharmacies/manage/list/")
            shot(page, "09_pharmacy_verification")
            page.goto(f"/pharmacies/{metro_id}/")
            page.get_by_text("Approval history").first.scroll_into_view_if_needed()
            page.evaluate("window.scrollBy(0, -150)")
            shot(page, "10_approval_history")

            # 404 page (needs DEBUG=False, so it comes from the second server)
            page = new_page()
            page.goto(f"http://127.0.0.1:{PORT_404}/this-page-does-not-exist/")
            shot(page, "11_page_not_found")
            browser.close()
    finally:
        for proc in (server, server_404):
            proc.terminate()
            proc.wait(timeout=10)

    print(f"Saved {len(saved)} screenshots to {OUT}:")
    for name in saved:
        print(f"  {name}.png")


if __name__ == "__main__":
    main()
