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


class ApprovalHistoryTests(TestCase):
    """F5: approval changes are stored with who, when, the old/new status and an optional reason."""

    def setUp(self):
        from accounts.models import User
        self.admin = User.objects.create_user(username='boss', email='b@t.test', password='x', role='ADMIN')
        self.pharmacy = _pharmacy('own', 'History Pharmacy', 17.4, 78.4, approved=False)

    def logs(self):
        from pharmacies.models import PharmacyApprovalLog
        return list(PharmacyApprovalLog.objects.filter(pharmacy=self.pharmacy).order_by('pk'))

    def test_approve_then_revoke_with_reason_is_logged(self):
        from pharmacies.services import set_pharmacy_approval
        set_pharmacy_approval(self.pharmacy.pk, True, self.admin)
        set_pharmacy_approval(self.pharmacy.pk, False, self.admin, reason='Licence expired')
        logs = self.logs()
        self.assertEqual([(l.from_status, l.to_status) for l in logs],
                         [('PENDING', 'APPROVED'), ('APPROVED', 'REVOKED')])
        self.assertEqual(logs[1].reason, 'Licence expired')
        self.assertEqual(logs[1].changed_by, self.admin)

    def test_reason_is_sent_to_the_owner(self):
        from pharmacies.services import set_pharmacy_approval
        from requests_app.models import Notification
        set_pharmacy_approval(self.pharmacy.pk, False, self.admin, reason='Licence expired')
        msg = Notification.objects.filter(user=self.pharmacy.owner).latest('pk').message
        self.assertIn('Licence expired', msg)

    def test_no_log_when_nothing_changes(self):
        from pharmacies.services import set_pharmacy_approval
        set_pharmacy_approval(self.pharmacy.pk, True, self.admin)
        set_pharmacy_approval(self.pharmacy.pk, True, self.admin)
        self.assertEqual(len(self.logs()), 1)

    def test_profile_edit_back_to_pending_is_logged(self):
        from pharmacies.forms import PharmacyEditForm
        from pharmacies.services import apply_pharmacy_profile_update, set_pharmacy_approval
        set_pharmacy_approval(self.pharmacy.pk, True, self.admin)
        self.pharmacy.refresh_from_db()
        data = {f: getattr(self.pharmacy, f) for f in PharmacyEditForm.Meta.fields}
        data['address'] = 'New Road 9'
        form = PharmacyEditForm(data, instance=self.pharmacy)
        self.assertTrue(form.is_valid(), form.errors)
        apply_pharmacy_profile_update(form, self.pharmacy.owner)
        last = self.logs()[-1]
        self.assertEqual((last.from_status, last.to_status), ('APPROVED', 'PENDING'))
        self.assertEqual(last.changed_by, self.pharmacy.owner)
        self.assertIn('address', last.reason)

    def test_revoke_form_reason_is_saved_and_trimmed(self):
        from django.urls import reverse
        from pharmacies.services import set_pharmacy_approval
        set_pharmacy_approval(self.pharmacy.pk, True, self.admin)
        self.client.login(username='boss', password='x')
        self.client.post(reverse('toggle_pharmacy_approval', args=[self.pharmacy.pk]),
                         {'action': 'revoke', 'reason': '  ' + 'x' * 600})
        self.assertEqual(len(self.logs()[-1].reason), 500)

    def test_history_visible_to_owner_and_admin_only(self):
        from django.urls import reverse
        from pharmacies.services import set_pharmacy_approval
        set_pharmacy_approval(self.pharmacy.pk, True, self.admin)
        url = reverse('pharmacy_detail', args=[self.pharmacy.pk])
        self.assertNotContains(self.client.get(url), 'Approval history')        # public
        self.client.login(username='boss', password='x')
        self.assertContains(self.client.get(url), 'Approval history')           # admin
        self.client.force_login(self.pharmacy.owner)
        self.assertContains(self.client.get(url), 'Approval history')           # owner


class DeleteStockCancelsRequestsTests(TestCase):
    """F6: deleting a stock row cancels that medicine's PENDING requests at that pharmacy."""

    def test_pending_requests_cancelled_and_customer_notified(self):
        from accounts.models import User
        from django.urls import reverse
        from inventory.models import Inventory
        from medicines.models import Medicine
        from requests_app.models import AvailabilityRequest, Notification
        med = Medicine.objects.create(medicine_name='Dolo 650', generic_name='Paracetamol', strength='650mg')
        other_med = Medicine.objects.create(medicine_name='Pan 40', generic_name='Pantoprazole', strength='40mg')
        pharmacy = _pharmacy('del', 'Delete Pharmacy', 17.4, 78.4)
        item = Inventory.objects.create(pharmacy=pharmacy, medicine=med, quantity=5)
        Inventory.objects.create(pharmacy=pharmacy, medicine=other_med, quantity=5)
        cust = User.objects.create_user(username='c1', email='c1@t.test', password='x')
        pending = AvailabilityRequest.objects.create(customer=cust, pharmacy=pharmacy, medicine=med)
        answered = AvailabilityRequest.objects.create(customer=cust, pharmacy=pharmacy, medicine=med, status='CONFIRMED')
        other = AvailabilityRequest.objects.create(customer=cust, pharmacy=pharmacy, medicine=other_med)

        self.client.force_login(pharmacy.owner)
        resp = self.client.post(reverse('inventory_delete', args=[item.pk]), follow=True)
        self.assertContains(resp, '1 pending request')
        for r in (pending, answered, other):
            r.refresh_from_db()
        self.assertEqual(pending.status, 'CANCELLED')
        self.assertIn('no longer lists', pending.pharmacy_response)
        self.assertEqual(answered.status, 'CONFIRMED')
        self.assertEqual(other.status, 'PENDING')
        self.assertTrue(Notification.objects.filter(user=cust, message__contains='no longer lists').exists())


class OnlyCustomersSendRequestsTests(TestCase):
    """F7: admins pass @customer_required, but they must not send availability requests."""

    def test_admin_cannot_open_or_post_request_form(self):
        from accounts.models import User
        from django.urls import reverse
        from inventory.models import Inventory
        from medicines.models import Medicine
        from requests_app.models import AvailabilityRequest
        med = Medicine.objects.create(medicine_name='Dolo 650', generic_name='Paracetamol', strength='650mg')
        pharmacy = _pharmacy('rq', 'Request Pharmacy', 17.4, 78.4)
        Inventory.objects.create(pharmacy=pharmacy, medicine=med, quantity=5)
        User.objects.create_user(username='boss', email='b@t.test', password='x', role='ADMIN')
        self.client.login(username='boss', password='x')
        url = reverse('create_request', args=[pharmacy.pk, med.pk])
        self.assertRedirects(self.client.get(url), reverse('dashboard'), fetch_redirect_response=False)
        self.client.post(url, {'quantity_requested': 1})
        self.assertFalse(AvailabilityRequest.objects.exists())
