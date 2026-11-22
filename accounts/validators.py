import re

from django.core.exceptions import ValidationError

_PHONE_ALLOWED = re.compile(r'^\+?[0-9\s\-().]+$')


def validate_phone_number(value):
    """
    Lenient phone validation for Indian and international numbers.
    Allows an optional leading "+", digits, spaces, dashes, dots and brackets,
    with 7 to 15 digits in total (E.164 maximum is 15).
    Examples: "+91 98765 43210", "040-11112222", "(020) 1234-5678".
    """
    if not value:
        return
    value = str(value).strip()
    digits = re.sub(r'\D', '', value)
    if not _PHONE_ALLOWED.match(value) or not (7 <= len(digits) <= 15):
        raise ValidationError(
            "Enter a valid phone number (7-15 digits; +, spaces, dashes and brackets are allowed).",
            code='invalid_phone',
        )


_PINCODE = re.compile(r'^[1-9][0-9]{5}$')


def validate_pincode(value):
    """Indian PIN code: exactly 6 digits, not starting with 0 (review P5)."""
    if value and not _PINCODE.match(str(value).strip()):
        raise ValidationError("Enter a valid 6-digit PIN code (e.g. 500001).", code='invalid_pincode')
