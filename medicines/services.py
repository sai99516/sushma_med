import logging
from typing import Any, Dict, List, Optional, Tuple
from django.core.paginator import Page
from django.db.models import Case, F, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404
from inventory.models import Inventory
from pharmacies.services import (
    bounding_box,
    calculate_haversine_distance,
    haversine_expression,
    is_valid_coordinate,
    paginate,
    parse_radius,
)
from .models import Medicine

logger = logging.getLogger('medfind')

MAX_MAP_PINS = 100

# Review known #3: sort by an explicit rank, not by the status text.
STOCK_RANK = Case(
    When(availability_status='IN_STOCK', then=Value(0)),
    When(availability_status='LOW_STOCK', then=Value(1)),
    default=Value(2),
    output_field=IntegerField(),
)


def search_medicine_inventory(
    query: str = '',
    category: str = '',
    dosage_form: str = '',
    strength: str = '',
    city: str = '',
    pincode: str = '',
    stock_status: str = '',
    radius_km: Optional[Any] = None,
    user_lat: Optional[Any] = None,
    user_lng: Optional[Any] = None,
    sort_by: str = '',
    page: int = 1,
    per_page: int = 10,
) -> Tuple[Page, bool, List[Dict[str, Any]], int, Optional[Dict[str, float]]]:
    """
    Searches inventory records for approved pharmacies matching search filters.
    Calculates proximity distances, applies radius bounds, extracts map pin metadata,
    and paginates results.
    """
    # Base queryset: strictly include stock only from verified/approved pharmacies!
    inventory_qs = Inventory.objects.filter(
        pharmacy__is_approved=True,
        medicine__is_active=True,
    ).select_related('medicine', 'pharmacy')

    if query:
        inventory_qs = inventory_qs.filter(
            Q(medicine__medicine_name__icontains=query) |
            Q(medicine__generic_name__icontains=query) |
            Q(medicine__strength__icontains=query) |
            Q(medicine__dosage_form__icontains=query) |
            Q(medicine__category__icontains=query) |
            Q(medicine__description__icontains=query) |
            Q(pharmacy__pharmacy_name__icontains=query)
        )

    if category:
        inventory_qs = inventory_qs.filter(medicine__category=category)

    if dosage_form:
        inventory_qs = inventory_qs.filter(medicine__dosage_form=dosage_form)

    if strength:
        inventory_qs = inventory_qs.filter(medicine__strength__icontains=strength)

    if city:
        inventory_qs = inventory_qs.filter(pharmacy__city__icontains=city.strip())

    if pincode:
        inventory_qs = inventory_qs.filter(pharmacy__pincode=pincode.strip())  # Review N14: exact match

    if stock_status:
        inventory_qs = inventory_qs.filter(availability_status=stock_status)

    # Review known #3: explicit rank In Stock -> Low Stock -> Out of Stock.
    inventory_qs = inventory_qs.annotate(stock_rank=STOCK_RANK)

    has_user_coords = is_valid_coordinate(user_lat, user_lng)
    user_coords_dict: Optional[Dict[str, float]] = None

    # Review N7: bounding box + Haversine + ordering + pagination in the database.
    if has_user_coords:
        u_lat = float(user_lat)
        u_lng = float(user_lng)
        user_coords_dict = {'lat': u_lat, 'lng': u_lng}
        inventory_qs = inventory_qs.annotate(
            distance_db=haversine_expression('pharmacy__latitude', 'pharmacy__longitude', u_lat, u_lng)
        )
        max_radius = parse_radius(radius_km)
        if max_radius is not None:
            min_lat, max_lat, min_lng, max_lng = bounding_box(u_lat, u_lng, max_radius)
            inventory_qs = inventory_qs.filter(
                pharmacy__latitude__gte=min_lat, pharmacy__latitude__lte=max_lat,
                pharmacy__longitude__gte=min_lng, pharmacy__longitude__lte=max_lng,
            ).filter(distance_db__lte=max_radius)

    if has_user_coords and sort_by == 'distance':
        inventory_qs = inventory_qs.order_by(
            F('distance_db').asc(nulls_last=True), 'stock_rank', '-updated_at', 'pk'
        )
    else:
        inventory_qs = inventory_qs.order_by('stock_rank', '-updated_at', 'pk')

    page_obj = paginate(inventory_qs, page, per_page)
    total_results = page_obj.paginator.count

    # Distances and map pins only for the current page (at most MAX_MAP_PINS).
    map_pins: List[Dict[str, Any]] = []
    seen_pharmacies = set()
    for item in page_obj:
        p = item.pharmacy
        if has_user_coords and is_valid_coordinate(p.latitude, p.longitude):
            item.distance_km = calculate_haversine_distance(u_lat, u_lng, p.latitude, p.longitude)
        else:
            item.distance_km = None
        if p.id in seen_pharmacies or len(map_pins) >= MAX_MAP_PINS:
            continue
        seen_pharmacies.add(p.id)
        if is_valid_coordinate(p.latitude, p.longitude):
            map_pins.append({
                'id': p.id,
                'name': p.pharmacy_name,
                'address': f"{p.address}, {p.city}",
                'phone': p.phone_number,
                'lat': float(p.latitude),
                'lng': float(p.longitude),
                'medicine': item.medicine.medicine_name,
                'status': item.get_availability_status_display(),
                'freshness_tier': item.freshness_tier,
                'freshness_label': item.freshness_label,
                'distance_km': item.distance_km,
            })

    logger.info(
        "Medicine search executed: query='%s', category='%s', city='%s', radius='%s', results_count=%d",
        query, category, city, radius_km, total_results
    )
    return page_obj, has_user_coords, map_pins, total_results, user_coords_dict


def get_search_filter_options() -> Tuple[List[str], List[str], List[str]]:
    """
    Retrieves distinct categories, approved pharmacy cities, and dosage forms for search dropdowns.
    Optimized: queries Pharmacy directly using the (is_approved, city) composite index,
    avoiding an expensive full-table scan and join across the entire Inventory table.
    """
    from pharmacies.models import Pharmacy
    categories = [choice[0] for choice in Medicine.CATEGORY_CHOICES]
    dosage_forms = [choice[0] for choice in Medicine.DOSAGE_FORM_CHOICES]
    raw_cities = (
        Pharmacy.objects.filter(is_approved=True)
        .order_by('city')
        .values_list('city', flat=True)
        .distinct()
    )
    cities = sorted(list({c.strip() for c in raw_cities if c and c.strip()}))
    return categories, cities, dosage_forms


def get_medicine_detail_data(medicine_id: int, user_lat: Optional[Any] = None, user_lng: Optional[Any] = None,
                             sort_by: str = ''):
    """
    Retrieves medicine details, approved pharmacy stock and map pins.
    With a valid user location (F3) each row gets distance_km, and sort_by='distance'
    puts the nearest pharmacy first. Returns (medicine, stock_records, map_pins, user_coords).
    """
    medicine = get_object_or_404(Medicine, pk=medicine_id, is_active=True)
    stock_qs = Inventory.objects.filter(
        medicine=medicine,
        pharmacy__is_approved=True
    ).select_related('pharmacy').annotate(stock_rank=STOCK_RANK)

    user_coords: Optional[Dict[str, float]] = None
    if is_valid_coordinate(user_lat, user_lng):
        user_coords = {'lat': float(user_lat), 'lng': float(user_lng)}
    if user_coords and sort_by == 'distance':
        stock_qs = stock_qs.annotate(
            distance_db=haversine_expression('pharmacy__latitude', 'pharmacy__longitude',
                                             user_coords['lat'], user_coords['lng'])
        ).order_by(F('distance_db').asc(nulls_last=True), 'stock_rank', '-updated_at')
    else:
        stock_qs = stock_qs.order_by('stock_rank', '-updated_at')

    stock_records = list(stock_qs)  # a list, so distance_km set below survives template iteration
    map_pins = []
    for item in stock_records:
        p = item.pharmacy
        item.distance_km = None
        if user_coords:
            item.distance_km = calculate_haversine_distance(
                user_coords['lat'], user_coords['lng'], p.latitude, p.longitude
            )
        if is_valid_coordinate(p.latitude, p.longitude):  # review N8: keeps 0.0
            map_pins.append({
                'id': p.id,
                'name': p.pharmacy_name,
                'address': f"{p.address}, {p.city}",
                'phone': p.phone_number,
                'lat': float(p.latitude),
                'lng': float(p.longitude),
                'medicine': medicine.medicine_name,
                'status': item.get_availability_status_display(),
                'distance_km': item.distance_km,
            })

    return medicine, stock_records, map_pins, user_coords
