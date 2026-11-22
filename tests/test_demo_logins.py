"""
Regression tests for review finding N2: demo logins (admin / admin123 etc.)
must only be shown when settings.DEBUG is True.
"""
from django.test import TestCase, override_settings
from django.urls import reverse

DEMO_SNIPPETS = ['admin123', 'password123']
PAGES = ['home', 'login', 'search_medicines']


class DemoLoginsVisibilityTest(TestCase):
    @override_settings(DEBUG=False)
    def test_demo_logins_hidden_when_debug_false(self):
        for name in PAGES:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            for snippet in DEMO_SNIPPETS:
                self.assertNotContains(response, snippet, msg_prefix=f'{name}: ')

    @override_settings(DEBUG=True)
    def test_demo_logins_shown_when_debug_true(self):
        for name in PAGES:
            response = self.client.get(reverse(name))
            self.assertContains(response, 'admin123', msg_prefix=f'{name}: ')
