"""Short regression tests for third-pass fixes (P1-P8)."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.forms import PharmacyEditForm
from pharmacies.models import Pharmacy
from requests_app.forms import AvailabilityRequestCreateForm

User = get_user_model()


class LoginRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('rl_user', 'rl_user@t.test', 'RightPass123!', role='CUSTOMER')
        self.other = User.objects.create_user('rl_other', 'rl_other@t.test', 'RightPass123!', role='CUSTOMER')

    def tearDown(self):
        cache.clear()

    def _login(self, username, password, ip='10.0.0.1', xff=None):
        extra = {'REMOTE_ADDR': ip}
        if xff:
            extra['HTTP_X_FORWARDED_FOR'] = xff
        return self.client.post(reverse('login'), {'username': username, 'password': password}, **extra)

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_p1_clients_behind_proxy_are_counted_separately(self):
        for _ in range(5):
            self._login('rl_user', 'wrong', ip='10.9.9.9', xff='203.0.113.5')
        # Same proxy REMOTE_ADDR, different real client: must not be blocked.
        resp = self._login('rl_user', 'RightPass123!', ip='10.9.9.9', xff='198.51.100.7')
        self.assertEqual(resp.status_code, 302)

    def test_p2_stranger_cannot_lock_out_user_by_name(self):
        for _ in range(6):
            self._login('rl_user', 'wrong', ip='10.0.0.66')
        self.assertEqual(self._login('rl_user', 'wrong', ip='10.0.0.66').status_code, 429)
        self.assertEqual(self._login('rl_user', 'RightPass123!', ip='10.0.0.1').status_code, 302)

    @override_settings(LOGIN_RATE_LIMIT_IP_ATTEMPTS=6)
    def test_p3_successful_login_does_not_reset_ip_counter(self):
        for name in ['a1', 'a2', 'a3', 'a4', 'a5']:
            self._login(name, 'wrong')
        self.assertEqual(self._login('rl_other', 'RightPass123!').status_code, 302)
        self.client.logout()
        self._login('a6', 'wrong')
        self.assertEqual(self._login('a7', 'wrong').status_code, 429)


class InputLimitTests(TestCase):
    def test_p4_request_quantity_and_message_limits(self):
        self.assertFalse(AvailabilityRequestCreateForm({'quantity_requested': 999999999}).is_valid())
        self.assertFalse(AvailabilityRequestCreateForm({'quantity_requested': 1, 'request_message': 'x' * 1001}).is_valid())
        self.assertTrue(AvailabilityRequestCreateForm({'quantity_requested': 1000, 'request_message': 'ok'}).is_valid())

    def test_p5_pincode_must_be_six_digits(self):
        base = {'pharmacy_name': 'P', 'address': 'A', 'city': 'C', 'state': 'S', 'phone_number': '040-1234567'}
        for bad in ['abc', '😀', '50001', '0500001', '5000011']:
            self.assertFalse(PharmacyEditForm({**base, 'pincode': bad}).is_valid(), bad)
        self.assertTrue(PharmacyEditForm({**base, 'pincode': '500001'}).is_valid())


class PageAndDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('p3_owner', 'p3_owner@t.test', 'OwnerPass123!', role='PHARMACY')
        cls.pharmacy = Pharmacy.objects.create(
            owner=cls.owner, pharmacy_name='P3 Pharmacy', registration_number='REG-P3', address='1 Road',
            city='Hyderabad', state='TS', pincode='500001', phone_number='040-11112222', is_approved=True,
        )
        meds = [
            Medicine.objects.create(medicine_name=f'P3Med {i}', generic_name='G', strength=f'{i}mg', dosage_form='Tablet')
            for i in range(12)
        ]
        for m in meds:
            Inventory.objects.create(pharmacy=cls.pharmacy, medicine=m, quantity=20)
        Medicine.objects.create(medicine_name='Archived', generic_name='G', strength='1mg', is_active=False)

    def test_p6_owner_profile_has_no_duplicate_ids(self):
        self.client.force_login(self.owner)
        html = self.client.get(reverse('profile')).content.decode()
        self.assertEqual(html.count('id="id_phone_number"'), 1)
        self.assertIn('id="id_pharmacy_phone_number"', html)

    def test_p7_page_zero_shows_first_page(self):
        resp = self.client.get(reverse('search_medicines'), {'q': 'P3Med', 'page': '0'})
        self.assertEqual(resp.context['page_obj'].number, 1)

    def test_p8_catalogue_count_excludes_archived(self):
        self.client.force_login(self.owner)
        resp = self.client.get(reverse('pharmacy_dashboard'))
        self.assertEqual(resp.context['total_catalog_medicines'], 12)
