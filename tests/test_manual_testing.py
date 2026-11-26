"""Tests for the manual testing fixes (M1-M7, see MEDIFIND_REVIEW.md "Manual testing fixes")."""
import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.models import Pharmacy
from pharmacies.services import set_pharmacy_approval
from requests_app.models import AvailabilityRequest, Notification
from requests_app.services import (
    cancel_availability_inquiry,
    create_availability_inquiry,
    respond_to_availability_inquiry,
)

BASE_DIR = Path(settings.BASE_DIR)
MAP_TEMPLATES = [
    'templates/pharmacies/discovery.html',
    'templates/medicines/search.html',
    'templates/pharmacies/detail.html',
    'templates/medicines/detail.html',
]


def _user(username, role='CUSTOMER'):
    return User.objects.create_user(username=username, email=f'{username}@t.test', password='x', role=role)


def _pharmacy(username, approved=True):
    return Pharmacy.objects.create(
        owner=_user(username, role='PHARMACY'), pharmacy_name=f'{username} Pharmacy',
        registration_number=f'REG-{username}', address='Road 1', city='Hyderabad', state='TS',
        pincode='500001', phone_number='0401234567', latitude=17.4, longitude=78.4,
        approval_status=Pharmacy.STATUS_APPROVED if approved else Pharmacy.STATUS_PENDING,
    )


class Base(TestCase):
    def setUp(self):
        self.med = Medicine.objects.create(medicine_name='Dolo 650', generic_name='Paracetamol', strength='650mg')
        self.pharmacy = _pharmacy('own')
        self.item = Inventory.objects.create(pharmacy=self.pharmacy, medicine=self.med, quantity=50)
        self.customer = _user('cust')
        self.admin = _user('boss', role='ADMIN')

    def make_req(self, qty=100, status='PENDING'):
        return AvailabilityRequest.objects.create(
            customer=self.customer, pharmacy=self.pharmacy, medicine=self.med,
            quantity_requested=qty, status=status,
        )


class M1MapTileTests(TestCase):
    """M1: OSM tiles need a Referer, and every map must show the OSM attribution."""

    def test_referrer_policy_sends_origin_cross_site(self):
        self.assertEqual(settings.SECURE_REFERRER_POLICY, 'strict-origin-when-cross-origin')
        resp = self.client.get(reverse('home'))
        self.assertEqual(resp['Referrer-Policy'], 'strict-origin-when-cross-origin')

    def test_every_tile_layer_has_referrer_policy_and_attribution(self):
        for path in MAP_TEMPLATES:
            text = (BASE_DIR / path).read_text()
            layers = re.findall(r"L\.tileLayer\(.*?\}\)", text, re.S)
            self.assertEqual(len(layers), 1, path)
            self.assertIn("referrerPolicy: 'strict-origin-when-cross-origin'", layers[0], path)
            self.assertIn('https://www.openstreetmap.org/copyright', layers[0], path)
            self.assertIn('OpenStreetMap</a> contributors', layers[0], path)
            self.assertNotIn('attributionControl: false', text, path)


class M2SystemCancelTests(Base):
    """M2: automatic cancels store their reason and do not say 'Cancelled by Customer'."""

    def test_stock_delete_cancel_shows_pharmacy_removed(self):
        req = self.make_req()
        self.client.force_login(self.pharmacy.owner)
        self.client.post(reverse('inventory_delete', args=[self.item.pk]))
        req.refresh_from_db()
        self.assertEqual((req.status, req.cancel_reason), ('CANCELLED', 'STOCK_REMOVED'))
        self.assertEqual(req.status_label, 'Cancelled: pharmacy removed this medicine')

        self.client.force_login(self.customer)
        resp = self.client.get(reverse('customer_requests'))
        self.assertContains(resp, 'Cancelled: pharmacy removed this medicine')
        self.assertNotContains(resp, 'Cancelled by Customer')

    def test_revoke_cancel_shows_pharmacy_not_approved(self):
        req = self.make_req()
        set_pharmacy_approval(self.pharmacy.pk, False, self.admin)
        req.refresh_from_db()
        self.assertEqual(req.cancel_reason, 'PHARMACY_REVOKED')
        self.client.force_login(self.customer)
        resp = self.client.get(reverse('customer_requests'))
        self.assertContains(resp, 'Cancelled: pharmacy is no longer approved')
        self.assertNotContains(resp, 'Cancelled by Customer')

    def test_customer_cancel_still_says_by_customer(self):
        req = self.make_req()
        ok, _ = cancel_availability_inquiry(req.pk, self.customer)
        self.assertTrue(ok)
        req.refresh_from_db()
        self.assertEqual(req.cancel_reason, 'CUSTOMER')
        self.client.force_login(self.customer)
        self.assertContains(self.client.get(reverse('customer_requests')), 'Cancelled by Customer')


class M3PartialAvailabilityTests(Base):
    """M3: the owner can answer 'Partially Available' with 1..requested-1 units, once."""

    def respond(self, req, **data):
        self.client.force_login(self.pharmacy.owner)
        return self.client.post(reverse('respond_request', args=[req.pk]), data)

    def test_partial_answer_saved_and_customer_sees_x_of_y(self):
        req = self.make_req(qty=100)
        self.respond(req, status='PARTIAL', available_quantity='60', pharmacy_response='Rest on Monday')
        req.refresh_from_db()
        self.assertEqual((req.status, req.available_quantity), ('PARTIAL', 60))
        self.assertTrue(Notification.objects.filter(user=self.customer, message__contains='60 of 100 available').exists())

        self.client.force_login(self.customer)
        resp = self.client.get(reverse('customer_requests'))
        self.assertContains(resp, '60 of 100 available')
        resp = self.client.get(reverse('customer_requests'), {'status': 'PARTIAL'})
        self.assertEqual([r.pk for r in resp.context['requests']], [req.pk])
        self.assertEqual(resp.context['counts']['partial'], 1)

    def test_partial_quantity_bounds(self):
        for bad in ('', '0', '100', '150'):
            req = self.make_req(qty=100)
            resp = self.respond(req, status='PARTIAL', available_quantity=bad)
            self.assertEqual(resp.status_code, 200, bad)  # form shown again with an error
            req.refresh_from_db()
            self.assertEqual(req.status, 'PENDING', bad)
            req.delete()

    def test_partial_not_possible_for_one_unit(self):
        req = self.make_req(qty=1)
        with self.assertRaises(ValidationError):
            respond_to_availability_inquiry(req.pk, self.pharmacy, 'PARTIAL', '', available_quantity=1)
        resp = self.respond(req, status='PARTIAL', available_quantity='1')
        self.assertEqual(resp.status_code, 200)
        req.refresh_from_db()
        self.assertEqual(req.status, 'PENDING')

    def test_partial_answer_only_once(self):
        req = self.make_req(qty=10)
        respond_to_availability_inquiry(req.pk, self.pharmacy, 'PARTIAL', '', available_quantity=4)
        with self.assertRaises(ValidationError):
            respond_to_availability_inquiry(req.pk, self.pharmacy, 'CONFIRMED', '')
        req.refresh_from_db()
        self.assertEqual((req.status, req.available_quantity), ('PARTIAL', 4))

    def test_confirm_clears_available_quantity(self):
        req = self.make_req(qty=10)
        self.respond(req, status='CONFIRMED', available_quantity='4')
        req.refresh_from_db()
        self.assertEqual((req.status, req.available_quantity), ('CONFIRMED', None))

    def test_respond_form_offers_three_choices(self):
        req = self.make_req(qty=10)
        self.client.force_login(self.pharmacy.owner)
        resp = self.client.get(reverse('respond_request', args=[req.pk]))
        for value in ('CONFIRMED', 'PARTIAL', 'UNAVAILABLE'):
            self.assertContains(resp, f'value="{value}"')
        self.assertContains(resp, 'name="available_quantity"')

    def test_admin_monitor_filter_and_inbox_count(self):
        req = self.make_req(qty=10)
        respond_to_availability_inquiry(req.pk, self.pharmacy, 'PARTIAL', '', available_quantity=3)
        self.make_req(qty=5, status='CONFIRMED')
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('admin_request_monitor'), {'status': 'PARTIAL'})
        self.assertEqual([r.pk for r in resp.context['requests']], [req.pk])
        self.assertContains(resp, '3 of 10 available')
        self.assertContains(resp, '?status=PARTIAL')
        self.assertEqual(self.client.get(reverse('admin_dashboard')).context['completed_requests'], 2)

        self.client.force_login(self.pharmacy.owner)
        resp = self.client.get(reverse('pharmacy_inbox'), {'status': 'ALL'})
        self.assertEqual(resp.context['partial_count'], 1)
        self.assertContains(resp, 'Partial: 3 of 10')


class M4StatusTextTests(Base):
    """M4: the response column text matches the status."""

    def test_texts(self):
        pending = self.make_req()
        cancelled = AvailabilityRequest.objects.create(
            customer=self.customer, pharmacy=self.pharmacy, medicine=self.med,
            status='CANCELLED', cancel_reason='CUSTOMER',
        )
        self.client.force_login(self.customer)
        resp = self.client.get(reverse('customer_requests'), {'status': 'CANCELLED'})
        self.assertNotContains(resp, 'Waiting for pharmacist review')
        self.assertContains(resp, 'Cancelled by Customer. No response needed.')
        resp = self.client.get(reverse('customer_requests'), {'status': 'PENDING'})
        self.assertContains(resp, 'Waiting for pharmacist review')
        AvailabilityRequest.objects.filter(pk=pending.pk).update(status='UNAVAILABLE')
        resp = self.client.get(reverse('customer_requests'), {'status': 'UNAVAILABLE'})
        self.assertNotContains(resp, 'Waiting for pharmacist review')
        self.assertContains(resp, 'The pharmacy answered without a note.')
        self.assertTrue(cancelled.pk)


class M5AllCountTests(Base):
    """M5: the 'All (N)' buttons show the total of all records, not the filtered count."""

    def setUp(self):
        super().setUp()
        _pharmacy('pend', approved=False)
        self.make_req()
        self.make_req(status='CONFIRMED')
        self.client.force_login(self.admin)

    def test_pharmacy_portal(self):
        resp = self.client.get(reverse('admin_pharmacy_list'), {'status': 'pending'})
        self.assertEqual(resp.context['total_count'], 1)
        self.assertContains(resp, f'All ({Pharmacy.objects.count()})')

    def test_user_management(self):
        resp = self.client.get(reverse('admin_user_list'), {'role': 'customer'})
        all_users = User.objects.exclude(role='ADMIN').count()
        self.assertNotEqual(resp.context['total_count'], all_users)
        self.assertContains(resp, f'All Users ({all_users})')

    def test_request_monitor(self):
        resp = self.client.get(reverse('admin_request_monitor'), {'status': 'CONFIRMED'})
        self.assertEqual(resp.context['total_count'], 1)
        self.assertContains(resp, 'All (2)')


class M6OwnerNotificationReadTests(Base):
    """M6: the owner's 'new request' notification is marked read when the request is opened or answered."""

    def new_request(self):
        req = create_availability_inquiry(self.customer, self.pharmacy, self.med, 5)
        notif = Notification.objects.get(user=self.pharmacy.owner, request=req)
        self.assertFalse(notif.is_read)
        return req, notif

    def test_opening_marks_read(self):
        req, notif = self.new_request()
        other = Notification.objects.create(user=self.pharmacy.owner, message='unrelated')
        self.client.force_login(self.pharmacy.owner)
        self.client.get(reverse('respond_request', args=[req.pk]))
        notif.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(notif.is_read)
        self.assertFalse(other.is_read)

    def test_answering_marks_read(self):
        req, notif = self.new_request()
        respond_to_availability_inquiry(req.pk, self.pharmacy, 'CONFIRMED', '')
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)
        # The customer's answer notification stays unread.
        self.assertTrue(Notification.objects.filter(user=self.customer, request=req, is_read=False).exists())


class M7MigrationCountDocsTests(TestCase):
    """M7: every migration count in the docs matches the real number of migration files."""

    def test_docs_match_real_count(self):
        real = sum(
            1 for p in BASE_DIR.glob('*/migrations/[0-9][0-9][0-9][0-9]_*.py')
            if '.venv' not in p.parts
        )
        docs = [BASE_DIR / 'README.md', BASE_DIR / 'MEDIFIND_PRESENTATION.md', *(BASE_DIR / 'docs').glob('*.md')]
        found = []
        for doc in docs:
            text = doc.read_text()
            found += re.findall(r'(\d+) migrations\b', text, re.I)
            found += re.findall(r'Migrations \((\d+)\)', text)
        self.assertTrue(found)
        self.assertEqual({int(n) for n in found}, {real})
