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


def _owner(username):
    from accounts.models import User
    return User.objects.create_user(username=username, email=f'{username}@t.test', password='x', role='PHARMACY')


def _pharmacy(username, name, lat, lng, approved=True):
    return Pharmacy.objects.create(
        owner=_owner(username), pharmacy_name=name, registration_number=f'REG-{username}',
        address='Road 1', city='Hyderabad', state='TS', pincode='500001', phone_number='0401234567',
        latitude=lat, longitude=lng, approval_status='APPROVED' if approved else 'PENDING',
    )


class MedicineDetailDistanceTests(TestCase):
    """F3: the medicine detail page shows distances and can sort by them when the user shares a location."""

    def setUp(self):
        from inventory.models import Inventory
        from medicines.models import Medicine
        self.med = Medicine.objects.create(medicine_name='Dolo 650', generic_name='Paracetamol', strength='650mg')
        self.far = _pharmacy('far', 'Far Pharmacy', 17.50, 78.50)      # about 13 km from the user
        self.near = _pharmacy('near', 'Near Pharmacy', 17.39, 78.39)   # about 1 km from the user
        Inventory.objects.create(pharmacy=self.far, medicine=self.med, quantity=50)   # In Stock
        Inventory.objects.create(pharmacy=self.near, medicine=self.med, quantity=5)   # Low Stock

    def url(self, **params):
        from urllib.parse import urlencode
        from django.urls import reverse
        return reverse('medicine_detail', args=[self.med.pk]) + ('?' + urlencode(params) if params else '')

    def test_without_location_no_distance_and_stock_order(self):
        resp = self.client.get(self.url())
        names = [i.pharmacy.pharmacy_name for i in resp.context['stock_records']]
        self.assertEqual(names, ['Far Pharmacy', 'Near Pharmacy'])  # In Stock first
        self.assertTrue(all(i.distance_km is None for i in resp.context['stock_records']))
        self.assertNotContains(resp, 'bi-signpost-split')

    def test_with_location_shows_distance(self):
        resp = self.client.get(self.url(lat='17.385', lng='78.386'))
        records = {i.pharmacy.pharmacy_name: i.distance_km for i in resp.context['stock_records']}
        self.assertLess(records['Near Pharmacy'], 2)
        self.assertGreater(records['Far Pharmacy'], 10)
        self.assertContains(resp, 'bi-signpost-split')
        self.assertTrue(resp.context['has_user_coords'])

    def test_sort_by_distance_puts_nearest_first(self):
        resp = self.client.get(self.url(lat='17.385', lng='78.386', sort='distance'))
        names = [i.pharmacy.pharmacy_name for i in resp.context['stock_records']]
        self.assertEqual(names, ['Near Pharmacy', 'Far Pharmacy'])

    def test_invalid_coordinates_are_ignored(self):
        resp = self.client.get(self.url(lat='999', lng='abc', sort='distance'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['has_user_coords'])


class SplitTemplateTagTests(TestCase):
    """F4: a {{ ... }} tag split over two lines is printed as raw text by Django."""

    def test_navbar_role_badge_renders(self):
        from accounts.models import User
        User.objects.create_user(username='cust', email='c@t.test', password='x', role='CUSTOMER')
        self.client.login(username='cust', password='x')
        resp = self.client.get('/')
        self.assertNotContains(resp, 'user.role|lower')
        self.assertContains(resp, '>customer</span>')

    def test_medicine_detail_timesince_renders(self):
        from django.urls import reverse
        from inventory.models import Inventory
        from medicines.models import Medicine
        med = Medicine.objects.create(medicine_name='Dolo 650', generic_name='Paracetamol', strength='650mg')
        Inventory.objects.create(pharmacy=_pharmacy('p1', 'P1', 17.4, 78.4), medicine=med, quantity=5)
        resp = self.client.get(reverse('medicine_detail', args=[med.pk]))
        self.assertNotContains(resp, 'item.updated_at|timesince')

    def test_no_template_has_a_split_variable_tag(self):
        import re
        from pathlib import Path
        from django.conf import settings
        for path in (Path(settings.BASE_DIR) / 'templates').rglob('*.html'):
            for n, line in enumerate(path.read_text().splitlines(), 1):
                self.assertIsNone(re.search(r'\{\{[^}]*$', line), f'{path}:{n} has a split {{{{ }}}} tag')
