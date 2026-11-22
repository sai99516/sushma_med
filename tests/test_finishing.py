"""Tests for the finishing changes (F1-F9, see MEDIFIND_REVIEW.md "Finishing changes")."""
from django.core.management import call_command
from django.test import TestCase, override_settings

from pharmacies.models import Pharmacy


class SeedPendingPharmacyNameTests(TestCase):
    """F1: the seeded pending pharmacy keeps its name after approval, so the name must not mention a status."""

    @override_settings(DEBUG=True)
    def test_seeded_pending_pharmacy_name_has_no_status(self):
        call_command('seed_data', stdout=open('/dev/null', 'w'))
        pharmacy = Pharmacy.objects.get(owner__username='pending_owner')
        self.assertEqual(pharmacy.approval_status, Pharmacy.STATUS_PENDING)
        self.assertEqual(pharmacy.pharmacy_name, '[DEMO] Metro Life Pharmacy')
