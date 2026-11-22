"""Short regression tests for fixes on branch fix/all (N3, N4, N5, N9, known #3, N10)."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from requests_app.models import AvailabilityRequest
from requests_app.services import (
    cancel_availability_inquiry,
    create_availability_inquiry,
    respond_to_availability_inquiry,
)

User = get_user_model()


class FixAllRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('reg_admin', 'reg_admin@t.test', 'AdminPass123!', role='ADMIN')
        cls.customer = User.objects.create_user('reg_cust', 'reg_cust@t.test', 'CustPass123!', role='CUSTOMER')
        cls.owners = [
            User.objects.create_user(f'reg_owner{i}', f'reg_owner{i}@t.test', 'OwnerPass123!', role='PHARMACY')
            for i in range(3)
        ]
        cls.pharmacies = [
            Pharmacy.objects.create(
                owner=o, pharmacy_name=f'Reg Pharmacy {i}', registration_number=f'REG-FIX-{i}',
                address='1 Road', city='Hyderabad', state='Telangana', pincode=f'50000{i}',
                phone_number='040-11112222', is_approved=True,
            )
            for i, o in enumerate(cls.owners)
        ]
        cls.pharmacy = cls.pharmacies[0]
        cls.med = Medicine.objects.create(
            medicine_name='RegMed 500', generic_name='Regium', strength='500mg', dosage_form='Tablet', category='Other'
        )
        # Out, Low, In: created in the "wrong" order on purpose.
        for pharm, qty in zip(cls.pharmacies, [0, 5, 50]):
            Inventory.objects.create(pharmacy=pharm, medicine=cls.med, quantity=qty)

    def _request(self):
        return create_availability_inquiry(self.customer, self.pharmacy, self.med, 1)

    def test_n3_request_can_be_answered_only_once(self):
        req = self._request()
        respond_to_availability_inquiry(req.pk, self.pharmacy, 'CONFIRMED', 'ok')
        with self.assertRaises(ValidationError):
            respond_to_availability_inquiry(req.pk, self.pharmacy, 'UNAVAILABLE', 'changed')
        req.refresh_from_db()
        self.assertEqual(req.status, 'CONFIRMED')

    def test_n4_cancelled_request_cannot_be_overwritten(self):
        req = self._request()
        ok, _ = cancel_availability_inquiry(req.pk, self.customer)
        self.assertTrue(ok)
        with self.assertRaises(ValidationError):
            respond_to_availability_inquiry(req.pk, self.pharmacy, 'CONFIRMED', 'late')
        req.refresh_from_db()
        self.assertEqual(req.status, 'CANCELLED')

    def test_n5_double_approve_keeps_pharmacy_approved(self):
        pending = Pharmacy.objects.create(
            owner=User.objects.create_user('reg_pend', 'reg_pend@t.test', 'OwnerPass123!', role='PHARMACY'),
            pharmacy_name='Pending Reg', registration_number='REG-PEND', address='2 Road', city='Pune',
            state='MH', pincode='411001', phone_number='020-11112222',
        )
        self.client.force_login(self.admin)
        url = reverse('toggle_pharmacy_approval', args=[pending.pk])
        self.client.post(url, {'action': 'approve'})
        self.client.post(url, {'action': 'approve'})
        pending.refresh_from_db()
        self.assertTrue(pending.is_approved)
        self.assertEqual(pending.approval_status, Pharmacy.STATUS_APPROVED)

    def test_known3_search_order_in_low_out(self):
        resp = self.client.get(reverse('search_medicines'), {'q': 'RegMed'})
        statuses = [item.availability_status for item in resp.context['results']]
        self.assertEqual(statuses, ['IN_STOCK', 'LOW_STOCK', 'OUT_OF_STOCK'])

    def test_n10_home_box_digits_go_to_pincode(self):
        resp = self.client.get(reverse('search_medicines'), {'q': 'RegMed', 'city': '500001'})
        self.assertEqual(resp.context['pincode'], '500001')
        self.assertEqual(resp.context['city'], '')
        self.assertEqual([i.pharmacy.pk for i in resp.context['results']], [self.pharmacies[1].pk])

    def test_n9_duplicate_pending_request_blocked(self):
        self._request()
        with self.assertRaises(ValidationError):
            self._request()
        self.client.force_login(self.customer)
        self.client.post(
            reverse('create_request', args=[self.pharmacy.pk, self.med.pk]), {'quantity_requested': 1}
        )
        self.assertEqual(
            AvailabilityRequest.objects.filter(customer=self.customer, status='PENDING').count(), 1
        )
