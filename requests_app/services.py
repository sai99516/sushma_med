import logging
from datetime import timedelta
from typing import Dict, Tuple
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from .models import AvailabilityRequest, Notification

# Answers a pharmacy can give (manual testing M3 added PARTIAL).
ANSWER_STATUSES = ('CONFIRMED', 'PARTIAL', 'UNAVAILABLE')

logger = logging.getLogger('medfind')


# Review N9: simple per-customer limit on new availability requests.
REQUEST_RATE_LIMIT_COUNT = getattr(settings, 'REQUEST_RATE_LIMIT_COUNT', 10)
REQUEST_RATE_LIMIT_WINDOW_MINUTES = getattr(settings, 'REQUEST_RATE_LIMIT_WINDOW_MINUTES', 60)


def create_availability_inquiry(
    customer,
    pharmacy: Pharmacy,
    medicine: Medicine,
    quantity_requested: int,
    request_message: str = ''
) -> AvailabilityRequest:
    """
    Creates a new customer availability request and notifies the recipient pharmacy owner.
    Review N9/N24: the pharmacy must list the medicine (Inventory row), the customer may not
    have another PENDING request for the same pharmacy+medicine, and there is a simple
    per-customer rate limit. Everything runs in one transaction.
    Raises ValidationError with a user-safe message when a rule is broken.
    """
    from inventory.models import Inventory

    with transaction.atomic():
        if not pharmacy.is_approved:
            raise ValidationError("This pharmacy is not accepting requests right now.")

        if not Inventory.objects.filter(pharmacy=pharmacy, medicine=medicine).exists():
            raise ValidationError("This pharmacy does not list this medicine, so it cannot be requested here.")

        # Lock the customer row so two parallel submits cannot both pass the checks below.
        get_user_model().objects.select_for_update().filter(pk=customer.pk).first()

        if AvailabilityRequest.objects.filter(
            customer=customer, pharmacy=pharmacy, medicine=medicine, status='PENDING'
        ).exists():
            raise ValidationError(
                "You already have a pending request for this medicine at this pharmacy. "
                "Please wait for the pharmacy to answer it."
            )

        since = timezone.now() - timedelta(minutes=REQUEST_RATE_LIMIT_WINDOW_MINUTES)
        recent = AvailabilityRequest.objects.filter(customer=customer, created_at__gte=since).count()
        if recent >= REQUEST_RATE_LIMIT_COUNT:
            raise ValidationError(
                "You have sent too many requests in a short time. Please try again later."
            )

        req = AvailabilityRequest.objects.create(
            customer=customer,
            pharmacy=pharmacy,
            medicine=medicine,
            quantity_requested=quantity_requested,
            request_message=request_message,
            status='PENDING'
        )

        # Dispatch notification to pharmacy owner
        Notification.objects.create(
            user=pharmacy.owner,
            request=req,
            message=f"New availability request for '{medicine.medicine_name}' ({quantity_requested} units) from {customer.username}."
        )

    logger.info(
        "Availability request #%d created: customer='%s', pharmacy='%s', medicine='%s', qty=%d",
        req.id, customer.username, pharmacy.pharmacy_name, medicine.medicine_name, quantity_requested
    )
    return req


def get_pharmacy_inbox_counts(pharmacy: Pharmacy) -> Dict[str, int]:
    """
    Aggregates pending, confirmed, unavailable, and cancelled request counts in a single query.
    Eliminates redundant round-trips.
    """
    aggregated = AvailabilityRequest.objects.filter(pharmacy=pharmacy).aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status='PENDING')),
        confirmed=Count('id', filter=Q(status='CONFIRMED')),
        partial=Count('id', filter=Q(status='PARTIAL')),
        unavailable=Count('id', filter=Q(status='UNAVAILABLE')),
        cancelled=Count('id', filter=Q(status='CANCELLED')),
    )

    return {
        'total_count': aggregated['total'] or 0,
        'pending_count': aggregated['pending'] or 0,
        'confirmed_count': aggregated['confirmed'] or 0,
        'partial_count': aggregated['partial'] or 0,
        'unavailable_count': aggregated['unavailable'] or 0,
        'cancelled_count': aggregated['cancelled'] or 0,
    }


def respond_to_availability_inquiry(
    request_id: int,
    pharmacy: Pharmacy,
    status: str,
    pharmacy_response: str,
    available_quantity=None,
) -> AvailabilityRequest:
    """
    Records a pharmacy's availability response and alerts the inquiring customer.
    Review N3/N4/N24: a request can be answered only once, while it is PENDING.
    The status change is a conditional UPDATE (WHERE status='PENDING') inside a
    transaction, so a parallel cancel or second answer cannot be overwritten.
    Review N19: a revoked pharmacy cannot respond.
    Manual testing M3: PARTIAL needs available_quantity between 1 and quantity_requested - 1.
    Manual testing M6: the owner's "new request" notification is marked read.
    """
    if status not in ANSWER_STATUSES:
        raise ValidationError(
            f"Invalid status transition: '{status}'. Pharmacy can only set CONFIRMED, PARTIAL or UNAVAILABLE."
        )

    if pharmacy.approval_status == Pharmacy.STATUS_REVOKED:
        raise ValidationError("Your pharmacy's approval has been revoked, so it cannot answer requests.")

    with transaction.atomic():
        req_obj = get_object_or_404(
            AvailabilityRequest.objects.select_related('customer', 'medicine'),
            pk=request_id,
            pharmacy=pharmacy
        )

        if status == 'PARTIAL':
            max_partial = req_obj.quantity_requested - 1
            if available_quantity is None or not (1 <= available_quantity <= max_partial):
                if max_partial < 1:
                    raise ValidationError(
                        "Partial availability is not possible for a request of 1 unit. Choose Confirm or Unavailable."
                    )
                raise ValidationError(f"Available quantity must be between 1 and {max_partial}.")
        else:
            available_quantity = None

        updated = AvailabilityRequest.objects.filter(
            pk=req_obj.pk, pharmacy=pharmacy, status='PENDING'
        ).update(
            status=status, pharmacy_response=pharmacy_response,
            available_quantity=available_quantity, updated_at=timezone.now(),
        )

        if updated == 0:
            req_obj.refresh_from_db(fields=['status'])
            if req_obj.status == 'CANCELLED':
                raise ValidationError("Cannot respond to a request that has already been cancelled.")
            raise ValidationError("This request has already been answered. A request can be answered only once.")

        req_obj.status = status
        req_obj.pharmacy_response = pharmacy_response
        req_obj.available_quantity = available_quantity

        mark_request_notifications_read(req_obj, pharmacy.owner)

        # Notify customer
        Notification.objects.create(
            user=req_obj.customer,
            request=req_obj,
            message=f"{pharmacy.pharmacy_name} answered your request for '{req_obj.medicine.medicine_name}': {req_obj.status_label}."
        )

    logger.info(
        "Availability request #%d responded by '%s': status=%s",
        req_obj.id, pharmacy.pharmacy_name, status
    )
    return req_obj


def mark_request_notifications_read(req_obj: AvailabilityRequest, user) -> int:
    """Manual testing M6: marks the user's unread notifications about this request as read."""
    return Notification.objects.filter(user=user, request=req_obj, is_read=False).update(is_read=True)


def cancel_availability_inquiry(request_id: int, customer) -> Tuple[bool, str]:
    """
    Cancels a pending inquiry ensuring customer ownership verification.
    Uses a conditional UPDATE so it cannot overwrite a pharmacy answer (review N4).
    """
    req_obj = get_object_or_404(AvailabilityRequest, pk=request_id, customer=customer)
    updated = AvailabilityRequest.objects.filter(
        pk=req_obj.pk, customer=customer, status='PENDING'
    ).update(
        status='CANCELLED', cancel_reason=AvailabilityRequest.CANCEL_CUSTOMER, updated_at=timezone.now()
    )
    if updated:
        logger.info("Availability request #%d cancelled by customer: %s", req_obj.id, customer.username)
        return True, f"Request #{req_obj.id} has been cancelled."
    return False, "Only pending requests can be cancelled."


def cancel_pending_requests_for_medicine(pharmacy: Pharmacy, medicine: Medicine) -> int:
    """
    F6: when a pharmacy removes a medicine from its stock, its PENDING requests for that
    medicine are cancelled (conditional update) and each customer is notified.
    Returns the number of cancelled requests.
    """
    pending = list(
        AvailabilityRequest.objects.filter(pharmacy=pharmacy, medicine=medicine, status='PENDING')
        .select_related('customer')
    )
    if not pending:
        return 0
    AvailabilityRequest.objects.filter(pk__in=[r.pk for r in pending], status='PENDING').update(
        status='CANCELLED',
        cancel_reason=AvailabilityRequest.CANCEL_STOCK_REMOVED,
        pharmacy_response='Automatically cancelled: the pharmacy no longer lists this medicine.',
        updated_at=timezone.now(),
    )
    Notification.objects.bulk_create([
        Notification(
            user=r.customer,
            request=r,
            message=(
                f"Your request for '{medicine.medicine_name}' at {pharmacy.pharmacy_name} was cancelled "
                f"because the pharmacy no longer lists this medicine."
            ),
        )
        for r in pending
    ])
    logger.info("Cancelled %d pending request(s) after stock removal: pharmacy='%s', medicine='%s'",
                len(pending), pharmacy.pharmacy_name, medicine.medicine_name)
    return len(pending)
