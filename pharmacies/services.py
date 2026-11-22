import logging
import math
from typing import Any, Dict, List, Optional, Tuple
from django.core.paginator import EmptyPage, Page, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import ExpressionWrapper, F, FloatField, Q, QuerySet, Value
from django.db.models.functions import ASin, Cast, Cos, Least, Lower, Power, Radians, Sin, Sqrt
from django.shortcuts import get_object_or_404
from django.utils import timezone
from requests_app.models import Notification
from .models import Pharmacy

logger = logging.getLogger('medfind')


def is_valid_coordinate(lat: Any, lon: Any) -> bool:
    """
    Validates whether latitude and longitude are valid decimal degree geographic coordinates.
    Latitude must be between -90.0 and 90.0 degrees.
    Longitude must be between -180.0 and 180.0 degrees.
    Rejects None, empty strings, non-numeric values, NaN, and Inf.
    """
    if lat is None or lon is None:
        return False
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (ValueError, TypeError):
        return False
    if math.isnan(lat_f) or math.isnan(lon_f) or math.isinf(lat_f) or math.isinf(lon_f):
        return False
    return -90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0


def calculate_haversine_distance(lat1: Any, lon1: Any, lat2: Any, lon2: Any) -> Optional[float]:
    """
    Calculate the great circle distance between two geographic coordinates
    (in decimal degrees) using the standard Haversine formula:
        a = sin²(Δφ/2) + cos(φ1) * cos(φ2) * sin²(Δλ/2)
        c = 2 * atan2(√a, √(1-a))
        Distance = R * c
    Where R = 6371.0 km (Earth's volumetric mean radius).

    Returns:
        float: Distance in kilometers rounded to two decimal places,
               or None if coordinates are missing, non-numeric, or outside valid ranges.
    """
    if not is_valid_coordinate(lat1, lon1) or not is_valid_coordinate(lat2, lon2):
        return None

    lat1_f = float(lat1)
    lon1_f = float(lon1)
    lat2_f = float(lat2)
    lon2_f = float(lon2)

    # Earth's volumetric mean radius in kilometers
    R = 6371.0

    dlat = math.radians(lat2_f - lat1_f)
    dlon = math.radians(lon2_f - lon1_f)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1_f)) * math.cos(math.radians(lat2_f)) *
         math.sin(dlon / 2.0) ** 2)

    # Clamp 'a' to [0.0, 1.0] to guard against floating-point precision domain errors
    a = max(0.0, min(1.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    distance = R * c
    return round(distance, 2)


EARTH_RADIUS_KM = 6371.0


def bounding_box(lat: float, lng: float, radius_km: float) -> Tuple[float, float, float, float]:
    """
    Review N7: cheap lat/lng box around a point, used as a DB filter before the
    exact Haversine distance. Slightly larger than the circle (110 km per degree).
    Returns (min_lat, max_lat, min_lng, max_lng).
    """
    dlat = radius_km / 110.0
    cos_lat = max(math.cos(math.radians(lat)), 0.01)
    dlng = radius_km / (110.0 * cos_lat)
    return (
        max(lat - dlat, -90.0), min(lat + dlat, 90.0),
        max(lng - dlng, -180.0), min(lng + dlng, 180.0),
    )


def haversine_expression(lat_field: str, lng_field: str, user_lat: float, user_lng: float):
    """
    Review N7: Haversine distance (km) as a database expression so filtering by
    radius, ordering by distance and pagination all happen in the database.
    Works on SQLite (Django registers the math functions) and PostgreSQL.
    """
    lat2 = Radians(Cast(F(lat_field), FloatField()))
    lng2 = Radians(Cast(F(lng_field), FloatField()))
    lat1 = math.radians(user_lat)
    lng1 = math.radians(user_lng)
    a = (
        Power(Sin((lat2 - Value(lat1)) / Value(2.0)), 2)
        + Value(math.cos(lat1)) * Cos(lat2) * Power(Sin((lng2 - Value(lng1)) / Value(2.0)), 2)
    )
    return ExpressionWrapper(
        Value(2.0 * EARTH_RADIUS_KM) * ASin(Least(Sqrt(a), Value(1.0))),
        output_field=FloatField(),
    )


def parse_radius(radius_km: Any) -> Optional[float]:
    """Returns a positive radius in km, or None for '', 'all' or invalid input."""
    if radius_km in (None, '', 'all'):
        return None
    try:
        value = float(radius_km)
    except (ValueError, TypeError):
        return None
    if math.isnan(value) or math.isinf(value) or value <= 0:
        return None
    return value


def paginate(queryset_or_list, page: Any, per_page: int) -> Page:
    paginator = Paginator(queryset_or_list, per_page)
    try:
        if int(page) < 1:  # page=0 or negative -> first page, not the last (review P7)
            page = 1
    except (TypeError, ValueError):
        page = 1
    try:
        return paginator.page(page)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)


def get_pharmacy_filter_options() -> Tuple[List[str], List[str]]:
    """
    Retrieves distinct approved pharmacy cities and pincodes for search filters.
    """
    approved = Pharmacy.objects.filter(is_approved=True)
    raw_cities = approved.order_by('city').values_list('city', flat=True).distinct()
    raw_pincodes = approved.order_by('pincode').values_list('pincode', flat=True).distinct()
    cities = sorted(list({c.strip() for c in raw_cities if c and c.strip()}))
    pincodes = sorted(list({p.strip() for p in raw_pincodes if p and p.strip()}))
    return cities, pincodes


def discover_nearby_pharmacies(
    user_lat: Optional[Any] = None,
    user_lng: Optional[Any] = None,
    radius_km: Optional[Any] = None,
    city: str = '',
    pincode: str = '',
    search_query: str = '',
    sort_by: str = 'distance',
    only_approved: bool = True,
    page: int = 1,
    per_page: int = 10,
) -> Tuple[Page, bool, List[Dict[str, Any]], int, Optional[Dict[str, float]]]:
    """
    Discovers approved pharmacies with distance calculations, radius filtering,
    manual city/pincode criteria, and Leaflet map pin metadata.
    """
    # Base queryset: strictly enforce approved pharmacies in public discovery
    # Note: select_related('owner') omitted here to prevent unnecessary JOINs on public queries
    qs = Pharmacy.objects.all()
    if only_approved:
        qs = qs.filter(is_approved=True)

    if search_query:
        qs = qs.filter(
            Q(pharmacy_name__icontains=search_query) |
            Q(address__icontains=search_query)
        )  # Review N26: licence number is not searchable publicly.

    if city:
        qs = qs.filter(city__icontains=city.strip())

    if pincode:
        qs = qs.filter(pincode=pincode.strip())  # Review N14: exact match

    has_user_coords = is_valid_coordinate(user_lat, user_lng)
    user_coords_dict: Optional[Dict[str, float]] = None

    # Review N7: filtering, distance, ordering and pagination run in the database.
    if has_user_coords:
        u_lat = float(user_lat)
        u_lng = float(user_lng)
        user_coords_dict = {'lat': u_lat, 'lng': u_lng}
        qs = qs.annotate(distance_db=haversine_expression('latitude', 'longitude', u_lat, u_lng))

        max_radius = parse_radius(radius_km)
        if max_radius is not None:
            min_lat, max_lat, min_lng, max_lng = bounding_box(u_lat, u_lng, max_radius)
            qs = qs.filter(
                latitude__gte=min_lat, latitude__lte=max_lat,
                longitude__gte=min_lng, longitude__lte=max_lng,
            ).filter(distance_db__lte=max_radius)

        if sort_by == 'distance' or not sort_by:
            qs = qs.order_by(F('distance_db').asc(nulls_last=True), 'pharmacy_name', 'pk')
        elif sort_by == 'name':
            qs = qs.order_by(Lower('pharmacy_name'), 'pk')
        else:
            qs = qs.order_by('-created_at', 'pk')
    else:
        if sort_by == 'name':
            qs = qs.order_by(Lower('pharmacy_name'), 'pk')
        else:
            qs = qs.order_by('-created_at', 'pk')

    page_obj = paginate(qs, page, per_page)
    total_results = page_obj.paginator.count

    # Distances and map pins only for the current page (review N7).
    map_pins: List[Dict[str, Any]] = []
    for p in page_obj:
        if has_user_coords and is_valid_coordinate(p.latitude, p.longitude):
            p.distance_km = calculate_haversine_distance(u_lat, u_lng, p.latitude, p.longitude)
        else:
            p.distance_km = None
        if is_valid_coordinate(p.latitude, p.longitude):
            map_pins.append({
                'id': p.id,
                'name': p.pharmacy_name,
                'address': f"{p.address}, {p.city} - {p.pincode}",
                'phone': p.phone_number,
                'lat': float(p.latitude),
                'lng': float(p.longitude),
                'distance_km': p.distance_km,
                'is_approved': p.is_approved,
            })

    logger.info(
        "Pharmacy discovery executed: query='%s', city='%s', pincode='%s', radius='%s', results=%d",
        search_query, city, pincode, radius_km, total_results
    )

    return page_obj, has_user_coords, map_pins, total_results, user_coords_dict


def get_pharmacy_for_user(user) -> Optional[Pharmacy]:
    """
    Retrieves the Pharmacy entity associated with an authenticated user.
    """
    if not user.is_authenticated:
        return None
    # Review N11: owner is a OneToOneField (related_name='pharmacy').
    try:
        return user.pharmacy
    except Pharmacy.DoesNotExist:
        return None


def _cancel_pending_requests_for_revoked(pharmacy: Pharmacy) -> int:
    """Review N19: on revoke, cancel the pharmacy's PENDING requests and tell each customer."""
    from requests_app.models import AvailabilityRequest
    pending = list(
        AvailabilityRequest.objects.select_for_update()
        .filter(pharmacy=pharmacy, status='PENDING')
        .select_related('customer', 'medicine')
    )
    if not pending:
        return 0
    AvailabilityRequest.objects.filter(pk__in=[r.pk for r in pending], status='PENDING').update(
        status='CANCELLED',
        pharmacy_response='Automatically cancelled: this pharmacy is no longer approved on MediFind.',
        updated_at=timezone.now(),
    )
    Notification.objects.bulk_create([
        Notification(
            user=r.customer,
            message=(
                f"Your request for '{r.medicine.medicine_name}' at {pharmacy.pharmacy_name} was cancelled "
                f"because the pharmacy is no longer approved on MediFind."
            ),
        )
        for r in pending
    ])
    return len(pending)


def set_pharmacy_approval(pharmacy_id: int, approve: bool, admin_user) -> Tuple[Pharmacy, bool, str]:
    """
    Review N5/N24: explicitly sets approval (approve=True) or revokes it (approve=False).
    Idempotent: if the pharmacy is already in the wanted state nothing changes and
    no notification is sent. Runs in a transaction with a row lock.
    Returns (pharmacy, changed, message).
    """
    with transaction.atomic():
        pharmacy = get_object_or_404(
            Pharmacy.objects.select_for_update().select_related('owner'), pk=pharmacy_id
        )
        target = Pharmacy.STATUS_APPROVED if approve else Pharmacy.STATUS_REVOKED

        if pharmacy.approval_status == target:
            state = "approved" if approve else "revoked"
            return pharmacy, False, f"Pharmacy '{pharmacy.pharmacy_name}' is already {state}. No change made."

        # Note: revoking a PENDING application also records it as REVOKED (rejected).
        pharmacy.approval_status = target
        pharmacy.save(update_fields=['approval_status'])

        cancelled = 0
        if approve:
            owner_msg = (
                f"Your pharmacy '{pharmacy.pharmacy_name}' has been approved by the MediFind administrator. "
                f"It is now visible in public search."
            )
            result_msg = f"Pharmacy '{pharmacy.pharmacy_name}' has been approved."
        else:
            cancelled = _cancel_pending_requests_for_revoked(pharmacy)
            owner_msg = (
                f"The approval of your pharmacy '{pharmacy.pharmacy_name}' has been revoked by the MediFind "
                f"administrator. It is hidden from public search and cannot update stock or answer requests."
            )
            result_msg = f"Approval for pharmacy '{pharmacy.pharmacy_name}' has been revoked."
            if cancelled:
                result_msg += f" {cancelled} pending request(s) were cancelled and the customers notified."

        Notification.objects.create(user=pharmacy.owner, message=owner_msg)

        logger.info(
            "Pharmacy approval set: '%s' (id=%d) -> %s by admin '%s' (cancelled_requests=%d)",
            pharmacy.pharmacy_name, pharmacy.id, target, getattr(admin_user, 'username', '?'), cancelled
        )
        return pharmacy, True, result_msg


def apply_pharmacy_profile_update(form, user) -> Tuple[Pharmacy, bool]:
    """
    Review known #5: saves a pharmacy profile form. If the pharmacy is APPROVED and a
    sensitive field (name, address, city, pincode, lat/lng) changed, it goes back to
    PENDING and needs a new admin approval. Returns (pharmacy, needs_reapproval).
    """
    with transaction.atomic():
        pharmacy = form.save(commit=False)
        sensitive_changed = [f for f in form.changed_data if f in Pharmacy.SENSITIVE_FIELDS]
        needs_reapproval = bool(sensitive_changed) and pharmacy.approval_status == Pharmacy.STATUS_APPROVED
        if needs_reapproval:
            pharmacy.approval_status = Pharmacy.STATUS_PENDING
        pharmacy.save()
        if needs_reapproval:
            Notification.objects.create(
                user=pharmacy.owner,
                message=(
                    f"You changed {', '.join(sensitive_changed)} of '{pharmacy.pharmacy_name}'. "
                    f"The pharmacy is hidden from public search until an administrator approves it again."
                ),
            )
            logger.info(
                "Pharmacy id=%d sent back to PENDING after sensitive edit (%s) by '%s'",
                pharmacy.id, ', '.join(sensitive_changed), user.username
            )
    return pharmacy, needs_reapproval


def get_pharmacy_detail_data(pharmacy_id: int, user) -> Tuple[Optional[Pharmacy], Optional[QuerySet], Optional[Dict[str, Any]], bool]:
    """
    Retrieves pharmacy profile, inventory records, and map pin.
    Enforces privacy rule: unapproved pharmacies are only visible to owner or admins.
    Uses select_related('owner') to check ownership without secondary queries.
    Returns (pharmacy, inventory_items, map_pin, is_authorized).
    """
    from inventory.models import Inventory
    pharmacy = get_object_or_404(Pharmacy.objects.select_related('owner'), pk=pharmacy_id)

    if not pharmacy.is_approved:
        is_owner_or_admin = user.is_authenticated and (user == pharmacy.owner or getattr(user, 'is_admin_user', False))
        if not is_owner_or_admin:
            return pharmacy, None, None, False

    inventory_items = Inventory.objects.filter(
        pharmacy=pharmacy, medicine__is_active=True
    ).select_related('medicine').order_by('-updated_at', 'pk')

    map_pin = None
    if is_valid_coordinate(pharmacy.latitude, pharmacy.longitude):  # review N8: keeps 0.0
        map_pin = {
            'id': pharmacy.id,
            'name': pharmacy.pharmacy_name,
            'address': f"{pharmacy.address}, {pharmacy.city}",
            'phone': pharmacy.phone_number,
            'lat': float(pharmacy.latitude),
            'lng': float(pharmacy.longitude),
        }

    return pharmacy, inventory_items, map_pin, True
