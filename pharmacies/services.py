import logging
import math
from typing import Any, Dict, List, Optional, Tuple
from django.core.paginator import EmptyPage, Page, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Q, QuerySet
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
        qs = qs.filter(pincode__icontains=pincode.strip())

    pharmacies_list: List[Pharmacy] = list(qs)

    has_user_coords = is_valid_coordinate(user_lat, user_lng)
    user_coords_dict: Optional[Dict[str, float]] = None

    if has_user_coords:
        u_lat = float(user_lat)
        u_lng = float(user_lng)
        user_coords_dict = {'lat': u_lat, 'lng': u_lng}

        for p in pharmacies_list:
            if is_valid_coordinate(p.latitude, p.longitude):
                p.distance_km = calculate_haversine_distance(
                    u_lat, u_lng, p.latitude, p.longitude
                )
            else:
                p.distance_km = None

        # Filter by radius if provided and valid
        if radius_km not in (None, '', 'all'):
            try:
                max_radius = float(radius_km)
                if max_radius > 0:
                    pharmacies_list = [
                        p for p in pharmacies_list
                        if p.distance_km is not None and p.distance_km <= max_radius
                    ]
            except (ValueError, TypeError):
                pass

        # Sort by nearest distance first
        if sort_by == 'distance' or not sort_by:
            pharmacies_list.sort(
                key=lambda p: (
                    p.distance_km is None,
                    p.distance_km if p.distance_km is not None else float('inf'),
                    p.pharmacy_name
                )
            )
        elif sort_by == 'name':
            pharmacies_list.sort(key=lambda p: p.pharmacy_name.lower())
        else:
            pharmacies_list.sort(key=lambda p: p.created_at, reverse=True)
    else:
        for p in pharmacies_list:
            p.distance_km = None
        if sort_by == 'name':
            pharmacies_list.sort(key=lambda p: p.pharmacy_name.lower())
        else:
            pharmacies_list.sort(key=lambda p: p.created_at, reverse=True)

    # Prepare map pins for Leaflet.js
    map_pins: List[Dict[str, Any]] = []
    for p in pharmacies_list:
        if is_valid_coordinate(p.latitude, p.longitude):
            map_pins.append({
                'id': p.id,
                'name': p.pharmacy_name,
                'address': f"{p.address}, {p.city} - {p.pincode}",
                'phone': p.phone_number,
                'lat': float(p.latitude),
                'lng': float(p.longitude),
                'distance_km': getattr(p, 'distance_km', None),
                'is_approved': p.is_approved,
            })

    total_results = len(pharmacies_list)

    # Paginate results
    paginator = Paginator(pharmacies_list, per_page)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

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

    inventory_items = Inventory.objects.filter(pharmacy=pharmacy).select_related('medicine').order_by('-updated_at')

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
