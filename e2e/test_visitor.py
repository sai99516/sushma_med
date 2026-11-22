"""1. Visitor (not logged in): home, search, maps, detail pages, directory, freshness, viewports."""
import re

import pytest
from playwright.sync_api import expect

from helpers import SCREENSHOT_DIR, make_pharmacy, make_stock, medicine_id, ranks, status_texts, uid, url_path



# ------------------------------------------------------------------ home page
def test_home_counts_banner_and_search_box(page):
    from inventory.models import Inventory
    from medicines.models import Medicine
    from pharmacies.models import Pharmacy

    page.goto("/")
    expect(page.locator(".disclaimer-banner")).to_be_visible()
    expect(page.locator(".disclaimer-banner")).to_contain_text("not a guaranteed reservation")

    values = page.locator(".stat-value").all_inner_texts()
    assert values[0].strip() == str(Pharmacy.objects.filter(is_approved=True).count())
    assert values[1].strip() == f"{Medicine.objects.filter(is_active=True).count()}+"
    in_stock = Inventory.objects.filter(pharmacy__is_approved=True, medicine__is_active=True,
                                        availability_status="IN_STOCK").count()
    assert values[2].strip() == f"{in_stock}+"

    # Name search from the hero box
    page.get_by_placeholder(re.compile("Search medicine")).fill("Dolo")
    page.locator("button.btn-search-main").click()
    page.wait_for_url(re.compile(r"/medicines/search/\?q=Dolo"))
    expect(page.locator("h4")).to_contain_text('Results for "Dolo"')
    names = page.locator("#resultsList h5 a").all_inner_texts()
    assert names and all("Dolo" in n for n in names)


def test_home_search_with_pincode(page):
    page.goto("/")
    page.get_by_placeholder(re.compile("Search medicine")).fill("Dolo")
    page.get_by_placeholder("City or Pincode...").fill("500034")
    page.locator("button.btn-search-main").click()
    page.wait_for_url(re.compile(r"/medicines/search/"))
    addrs = page.locator("#resultsList p.small.text-muted.mb-1:has(.bi-geo-alt)").all_inner_texts()
    assert addrs, "pincode search returned nothing"
    assert all("500034" in a for a in addrs)
    # the pincode ended up in the pincode filter, not the city filter
    expect(page.locator("input[name=pincode]")).to_have_value("500034")


# ------------------------------------------------------------------ search page
def _apply(page):
    page.get_by_role("button", name="Apply Filters").click()
    page.wait_for_load_state()


def test_search_each_filter(page):
    from medicines.models import Medicine
    page.goto("/medicines/search/")

    # keyword
    page.get_by_placeholder("Search by name...").fill("Paracetamol")
    _apply(page)
    generics = page.locator("#resultsList p:has-text('Generic:') strong").all_inner_texts()
    assert generics and all("Paracetamol" in g for g in generics)

    # category
    page.get_by_placeholder("Search by name...").fill("")
    page.locator("select[name=category]").select_option("Antibiotics")
    _apply(page)
    cats = page.locator("#resultsList .badge.text-primary").all_inner_texts()
    assert cats and set(c.strip() for c in cats) == {"Antibiotics"}

    # dosage form
    page.locator("select[name=category]").select_option("")
    page.locator("select[name=dosage_form]").select_option("Syrup")
    _apply(page)
    forms = page.locator("#resultsList .badge.text-secondary").all_inner_texts()
    assert forms and set(f.strip() for f in forms) == {"Syrup"}

    # strength
    page.locator("select[name=dosage_form]").select_option("")
    page.get_by_placeholder("e.g. 500mg, 10ml, 1g").fill("650mg")
    _apply(page)
    gens = page.locator("#resultsList p:has-text('Generic:')").all_inner_texts()
    assert gens and all("650mg" in g for g in gens)

    # city
    page.get_by_placeholder("e.g. 500mg, 10ml, 1g").fill("")
    page.locator("select[name=city]").select_option("Bengaluru")
    _apply(page)
    addrs = page.locator("#resultsList p:has(.bi-geo-alt)").all_inner_texts()
    assert addrs and all("Bengaluru" in a for a in addrs)

    # pincode
    page.locator("select[name=city]").select_option("")
    page.get_by_placeholder("e.g. 500034").fill("110001")
    _apply(page)
    addrs = page.locator("#resultsList p:has(.bi-geo-alt)").all_inner_texts()
    assert addrs and all("110001" in a for a in addrs)

    # stock status
    page.get_by_placeholder("e.g. 500034").fill("")
    for value, cls in (("IN_STOCK", "badge-in-stock"), ("LOW_STOCK", "badge-low-stock"),
                       ("OUT_OF_STOCK", "badge-out-stock")):
        page.locator("select[name=status]").select_option(value)
        _apply(page)
        found = status_texts(page)
        assert found and set(found) == {cls}, (value, found)
    assert Medicine.objects.exists()


def test_search_sort_order_in_low_out_across_all_pages(page):
    page.goto("/medicines/search/")
    seen = []
    for _ in range(30):
        seen += ranks(status_texts(page))
        nxt = page.locator(".pagination a.page-link", has_text="Next")
        if nxt.count() == 0:
            break
        nxt.click()
        page.wait_for_load_state()
    assert len(seen) > 10
    assert seen == sorted(seen), f"status order broken: {seen}"
    assert set(seen) == {0, 1, 2}


def test_search_sort_order_for_one_medicine(page):
    """Three pharmacies with the same medicine at 0, 5 and 50 units: In > Low > Out."""
    pin = "560099"
    for qty in (0, 5, 50):
        make_stock(make_pharmacy(pincode=pin, city="Bengaluru", lat=12.9, lng=77.6), "Dolo 650", qty)
    page.goto(f"/medicines/search/?q=Dolo&pincode={pin}")
    assert status_texts(page) == ["badge-in-stock", "badge-low-stock", "badge-out-stock"]


def test_search_reset_filters_and_no_results(page):
    page.goto("/medicines/search/?q=Dolo&city=Hyderabad&status=IN_STOCK")
    page.get_by_role("link", name="Reset All", exact=True).click()
    page.wait_for_load_state()
    assert url_path(page) == "/medicines/search/"
    expect(page.locator("input[name=q]")).to_have_value("")
    expect(page.locator("select[name=city]")).to_have_value("")

    page.get_by_placeholder("Search by name...").fill("zzznosuchmedicine")
    _apply(page)
    expect(page.get_by_text("No Matching Medicine Stock Found")).to_be_visible()
    page.get_by_role("link", name="Reset All Filters").click()
    page.wait_for_load_state()
    assert url_path(page) == "/medicines/search/"
    expect(page.locator("#resultsList .med-card").first).to_be_visible()


def test_search_pagination_keeps_filters(page):
    page.goto("/medicines/search/?status=IN_STOCK")
    expect(page.locator(".pagination .page-item.active")).to_have_text("1")
    first_page = page.locator("#resultsList h5 a").all_inner_texts()
    assert len(first_page) == 10
    page.locator(".pagination a.page-link", has_text="Next").click()
    page.wait_for_load_state()
    expect(page.locator(".pagination .page-item.active")).to_have_text("2")
    assert "status=IN_STOCK" in page.url and "page=2" in page.url
    assert set(status_texts(page)) == {"badge-in-stock"}
    page.locator(".pagination a.page-link", has_text="Last").click()
    page.wait_for_load_state()
    last = page.locator(".pagination .page-item.active").inner_text()
    assert int(last) >= 2
    page.locator(".pagination a.page-link", has_text="First").click()
    page.wait_for_load_state()
    expect(page.locator(".pagination .page-item.active")).to_have_text("1")
    assert page.locator("#resultsList h5 a").all_inner_texts() == first_page


def test_search_geolocation_allowed(new_context):
    ctx = new_context(geolocation={"latitude": 17.4156, "longitude": 78.4347}, permissions=["geolocation"])
    page = ctx.new_page()
    page.goto("/medicines/search/?q=Dolo")
    page.locator("#btnGeoLocation").click()
    page.wait_for_url(re.compile(r"lat=17\.4156"))
    assert "sort=distance" in page.url
    expect(page.locator("#geoFeedback")).to_contain_text("Coordinates linked")
    dists = [float(re.search(r"([\d.]+) km", t).group(1))
             for t in page.locator("#resultsList .badge:has(.bi-signpost-split)").all_inner_texts()]
    assert dists and dists == sorted(dists)
    assert dists[0] < 1.0  # Apollo Banjara Hills is right at the mocked location
    # radius filter needs coordinates
    page.locator("select[name=radius]").select_option("5")
    _apply(page)
    dists = [float(re.search(r"([\d.]+) km", t).group(1))
             for t in page.locator("#resultsList .badge:has(.bi-signpost-split)").all_inner_texts()]
    assert dists and max(dists) <= 5
    # clear location
    page.locator("#geoFeedback a", has_text="Clear").click()
    page.wait_for_load_state()
    expect(page.locator("#btnGeoLocation")).to_contain_text("Use My Location")


def test_search_geolocation_denied(new_context):
    ctx = new_context(permissions=[])
    page = ctx.new_page()
    page.goto("/medicines/search/?q=Dolo")
    page.locator("#btnGeoLocation").click()
    expect(page.locator("#geoFeedback")).to_contain_text("Location permission denied", timeout=15000)
    assert "lat=" not in page.url


# ------------------------------------------------------------------ maps
def test_search_map_toggle_pins_popup_and_pin_on_map(page):
    page.goto("/medicines/search/?q=Dolo")
    expect(page.locator("#mapContainer")).to_be_hidden()
    page.locator("#btnMapView").click()
    expect(page.locator("#mapContainer")).to_be_visible()
    expect(page.locator("#btnMapView")).to_have_class(re.compile("active"))
    pins = page.locator("#map .leaflet-marker-icon")
    expect(pins.first).to_be_visible()
    n_pins = len(page.evaluate("JSON.parse(document.getElementById('map-pins-data').textContent)"))
    assert pins.count() == n_pins > 0

    pins.first.click(force=True)
    popup = page.locator(".leaflet-popup-content")
    expect(popup).to_be_visible()
    expect(popup).to_contain_text("Dolo 650")
    expect(popup).to_contain_text("Pharmacy-reported")

    page.locator("#btnListView").click()
    expect(page.locator("#mapContainer")).to_be_hidden()

    first_card = page.locator("#resultsList .med-card").first
    pharmacy = first_card.locator("h6 a").inner_text().strip()
    first_card.get_by_role("button", name="Pin on Map").click()
    expect(page.locator("#mapContainer")).to_be_visible()
    # the earlier marker popup is closed when the new one opens
    expect(popup).to_have_count(1)
    expect(popup).to_contain_text(pharmacy)
    expect(popup).to_contain_text("Dolo 650")


def test_medicine_detail_and_map(page):
    page.goto("/medicines/search/?q=Dolo")
    page.locator("#resultsList h5 a").first.click()
    page.wait_for_url(re.compile(r"/medicines/\d+/$"))
    expect(page.locator("h3")).to_have_text("Dolo 650")
    expect(page.get_by_text("Paracetamol").first).to_be_visible()
    locations = int(re.search(r"\d+", page.locator("h4 .badge").inner_text()).group())
    assert locations >= 5
    expect(page.locator("#map .leaflet-marker-icon").first).to_be_visible()
    assert page.locator("#map .leaflet-marker-icon").count() == locations
    page.locator("#map .leaflet-marker-icon").first.click(force=True)
    expect(page.locator(".leaflet-popup-content")).to_be_visible()
    expect(page.locator("a:has-text('Login to Request')").first).to_be_visible()


def test_pharmacy_directory_map_and_detail(page):
    from pharmacies.models import Pharmacy
    page.goto("/pharmacies/")
    approved = Pharmacy.objects.filter(is_approved=True).count()
    expect(page.locator("main p.text-muted.small strong").first).to_have_text(str(approved))
    cards = page.locator("#resultsList .med-card")
    assert cards.count() == min(approved, 9)

    page.locator("#btnMapView").click()
    pins = page.locator("#map .leaflet-marker-icon")
    expect(pins.first).to_be_visible()
    pins.first.click(force=True)
    popup = page.locator(".leaflet-popup-content")
    expect(popup).to_be_visible()
    link = popup.get_by_role("link", name=re.compile("View Store"))
    name = popup.locator("strong").first.inner_text()
    link.click()
    page.wait_for_url(re.compile(r"/pharmacies/\d+/$"))
    expect(page.locator("h3")).to_have_text(name)
    expect(page.locator("#map .leaflet-marker-icon")).to_be_visible()
    expect(page.locator(".leaflet-popup-content")).to_contain_text(name)  # opened on load
    expect(page.locator("table tbody tr").first).to_be_visible()

    # directory search + Pin button
    page.goto("/pharmacies/")
    page.get_by_placeholder(re.compile("Apollo")).fill("Apollo")
    page.get_by_role("button", name="Apply Filters").click()
    page.wait_for_load_state()
    expect(cards).to_have_count(1)
    cards.first.get_by_role("button", name="Pin").click()
    expect(page.locator(".leaflet-popup-content")).to_contain_text("Apollo")


def test_stale_badge_for_old_stock(page):
    pin = "560098"
    old = make_pharmacy(pincode=pin, city="Bengaluru", lat=12.95, lng=77.6, name=f"Old Stock {uid()}")
    new = make_pharmacy(pincode=pin, city="Bengaluru", lat=12.96, lng=77.61, name=f"Fresh Stock {uid()}")
    make_stock(old, "Crocin Advance 500", 40, age_hours=72)
    make_stock(new, "Crocin Advance 500", 40)
    page.goto(f"/medicines/search/?q=Crocin&pincode={pin}")
    cards = page.locator("#resultsList .med-card")
    expect(cards).to_have_count(2)
    old_card = cards.filter(has_text=old.pharmacy_name)
    new_card = cards.filter(has_text=new.pharmacy_name)
    expect(old_card).to_contain_text("Reported >24h ago")
    expect(new_card).not_to_contain_text("Reported >24h ago")
    expect(new_card).to_contain_text("Pharmacy-reported · updated")

    page.goto(f"/medicines/{medicine_id('Crocin Advance 500')}/")
    expect(page.locator(".med-card", has_text=old.pharmacy_name).locator("text=Reported >24h ago")).to_be_visible()


# ------------------------------------------------------------------ viewports
PAGES = ["/", "/medicines/search/?q=Dolo", "/pharmacies/", "/accounts/login/", "/accounts/register/customer/"]


@pytest.mark.parametrize("width,height", [(375, 812), (1280, 900)])
def test_main_pages_fit_viewport(new_context, width, height):
    ctx = new_context(viewport={"width": width, "height": height}, is_mobile=width < 500, has_touch=width < 500)
    page = ctx.new_page()
    extra = [f"/medicines/{medicine_id('Dolo 650')}/"]
    from pharmacies.models import Pharmacy
    extra.append(f"/pharmacies/{Pharmacy.objects.filter(is_approved=True).first().pk}/")
    overflow = []
    for path in PAGES + extra:
        page.goto(path)
        page.wait_for_load_state("networkidle")
        name = re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_") or "home"
        page.screenshot(path=str(SCREENSHOT_DIR / f"viewport_{width}_{name}.png"), full_page=True)
        sw, iw = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        if sw > iw + 1:
            overflow.append(f"{path}: scrollWidth {sw} > {iw}")
        expect(page.locator(".disclaimer-banner")).to_be_visible()
    if width < 500:
        # nav collapses into the hamburger menu
        page.goto("/")
        expect(page.locator(".navbar-toggler")).to_be_visible()
        expect(page.locator("#navbarMain").get_by_role("link", name="Nearby Pharmacies")).to_be_hidden()
        page.locator(".navbar-toggler").click()
        expect(page.locator("#navbarMain").get_by_role("link", name="Nearby Pharmacies")).to_be_visible()
    assert not overflow, "horizontal overflow: " + "; ".join(overflow)
