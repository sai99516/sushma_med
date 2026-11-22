"""
Regression tests for review finding N1: stored XSS in Leaflet map popups.

Pharmacy name/address/phone are typed by pharmacy owners. The map JavaScript
builds popup HTML from them, so every value must go through escapeHtml()
from static/js/map_popup.js.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import Inventory
from medicines.models import Medicine
from pharmacies.models import Pharmacy

User = get_user_model()

PAYLOAD = '<img src=x onerror=alert(1)>'
BASE_DIR = Path(settings.BASE_DIR)
HELPER_JS = BASE_DIR / 'static' / 'js' / 'map_popup.js'
MAP_TEMPLATES = [
    'templates/pharmacies/detail.html',
    'templates/medicines/detail.html',
    'templates/pharmacies/discovery.html',
    'templates/medicines/search.html',
]
# Interpolations that never carry server/user data.
SAFE_INTERPOLATIONS = {'msg', 'distBadge'}


class EscapeHtmlFunctionTest(TestCase):
    @unittest.skipUnless(shutil.which('node'), 'node is not installed')
    def test_escape_html_escapes_dangerous_characters(self):
        script = (
            "const {escapeHtml} = require(%s);"
            "console.log(JSON.stringify(["
            "escapeHtml(%s), escapeHtml(null), escapeHtml(undefined), escapeHtml(12.5),"
            "escapeHtml(\"a'b\\\"c`d&e\")]));"
        ) % (json.dumps(str(HELPER_JS)), json.dumps(PAYLOAD))
        out = subprocess.run(['node', '-e', script], capture_output=True, text=True, check=True)
        result = json.loads(out.stdout)
        self.assertEqual(result[0], '&lt;img src=x onerror=alert(1)&gt;')
        self.assertEqual(result[1], '')
        self.assertEqual(result[2], '')
        self.assertEqual(result[3], '12.5')
        self.assertEqual(result[4], 'a&#39;b&quot;c&#96;d&amp;e')


class MapTemplatesEscapeTest(TestCase):
    def test_every_popup_interpolation_is_escaped(self):
        for rel in MAP_TEMPLATES:
            source = (BASE_DIR / rel).read_text(encoding='utf-8')
            for expr in re.findall(r'\$\{([^}]*)\}', source):
                expr = expr.strip()
                if expr in SAFE_INTERPOLATIONS:
                    continue
                self.assertTrue(
                    expr.startswith('escapeHtml('),
                    f'{rel}: unescaped interpolation ${{{expr}}} in map JavaScript',
                )
            # String concatenation into HTML: ' + value + '
            for name in re.findall(r"'\s*\+\s*([A-Za-z_][\w.]*)\s*\+\s*'", source):
                self.fail(f'{rel}: unescaped concatenation of {name} into HTML')

    def test_base_template_loads_escape_helper(self):
        source = (BASE_DIR / 'templates/base.html').read_text(encoding='utf-8')
        self.assertIn("js/map_popup.js", source)


class MaliciousPharmacyRenderTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username='xss_admin', email='xss_admin@test.com', password='AdminPass123!', role='ADMIN'
        )
        owner = User.objects.create_user(
            username='xss_owner', email='xss_owner@test.com', password='OwnerPass123!', role='PHARMACY'
        )
        cls.pharmacy = Pharmacy.objects.create(
            owner=owner, pharmacy_name=PAYLOAD, registration_number='REG-XSS-1',
            address=PAYLOAD, city='Hyderabad', state='Telangana', pincode='500001',
            phone_number='"><svg onload=1>', latitude='17.385044', longitude='78.486671',
            is_approved=True,
        )
        cls.pending = Pharmacy.objects.create(
            owner=owner, pharmacy_name=PAYLOAD, registration_number='REG-XSS-2',
            address=PAYLOAD, city='Hyderabad', state='Telangana', pincode='500001',
            phone_number='123', latitude='17.4', longitude='78.4', is_approved=False,
        )
        cls.medicine = Medicine.objects.create(
            medicine_name='XssMed', generic_name='Xss', strength='1mg', dosage_form='Tablet', category='Other'
        )
        Inventory.objects.create(pharmacy=cls.pharmacy, medicine=cls.medicine, quantity=20)

    def assert_no_raw_payload(self, response):
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn(PAYLOAD, html)
        self.assertNotIn('<svg onload=1>', html)
        self.assertIn('js/map_popup.js', html)

    def test_public_pages_do_not_render_payload_raw(self):
        self.assert_no_raw_payload(self.client.get(reverse('search_medicines'), {'q': 'XssMed'}))
        self.assert_no_raw_payload(self.client.get(reverse('pharmacy_discovery')))
        self.assert_no_raw_payload(self.client.get(reverse('pharmacy_detail', args=[self.pharmacy.id])))
        self.assert_no_raw_payload(self.client.get(reverse('medicine_detail', args=[self.medicine.id])))

    def test_admin_view_of_pending_pharmacy_does_not_render_payload_raw(self):
        self.client.force_login(self.admin)
        self.assert_no_raw_payload(self.client.get(reverse('pharmacy_detail', args=[self.pending.id])))
