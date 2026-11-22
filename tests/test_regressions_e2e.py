"""Regression tests for bugs found by the end-to-end browser tests (E1, E2)."""
import re

from django.test import SimpleTestCase

from requests_app.forms import MAX_REQUEST_QUANTITY, AvailabilityRequestCreateForm


class RequestQuantityInputTests(SimpleTestCase):
    """E2: the browser must get min=1 / max=1000 and a single value attribute."""

    def test_quantity_input_attributes(self):
        html = str(AvailabilityRequestCreateForm()['quantity_requested'])
        self.assertIn('min="1"', html)
        self.assertIn(f'max="{MAX_REQUEST_QUANTITY}"', html)
        self.assertEqual(len(re.findall(r'\bvalue="', html)), 1, html)
        self.assertIn('value="1"', html)


class AdminUnloadListenerTests(SimpleTestCase):
    """E1: the admin script served to browsers must not register an 'unload' listener."""

    def test_related_object_lookups_uses_pagehide(self):
        from django.contrib.staticfiles import finders
        path = finders.find('admin/js/admin/RelatedObjectLookups.js')
        with open(path, encoding='utf-8') as fh:
            source = fh.read()
        self.assertNotIn("addEventListener('unload'", source)
        self.assertIn("addEventListener('pagehide'", source)
        self.assertIn('dismissChildPopups', source)
