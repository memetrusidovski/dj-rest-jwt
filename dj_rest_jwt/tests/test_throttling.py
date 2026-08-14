from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from .mixins import TestsMixin
from .utils import override_api_settings

try:
    from django.urls import reverse
except ImportError:  # pragma: no cover
    from django.core.urlresolvers import reverse  # noqa

User = get_user_model()


@override_settings(ROOT_URLCONF='tests.urls')
class LoginRateThrottleTests(TestsMixin, TestCase):
    USERNAME = 'throttleuser'
    PASS = 'throttlepass123!'
    EMAIL = 'throttle@example.com'

    def setUp(self):
        self.init()
        User.objects.create_user(self.USERNAME, self.EMAIL, self.PASS)
        cache.clear()

    def tearDown(self):
        cache.clear()

    @override_api_settings(RATE_LIMIT_LOGIN='2/min')
    def test_login_is_throttled_after_configured_limit(self):
        payload = {'username': self.USERNAME, 'password': 'wrong-password'}

        self.post(self.login_url, data=payload, status_code=400)
        self.post(self.login_url, data=payload, status_code=400)
        # third request within the window exceeds the 2/min limit
        response = self.post(self.login_url, data=payload, status_code=429)
        self.assertIn('detail', response.json)

    @override_api_settings(RATE_LIMIT_LOGIN='2/min')
    def test_throttle_is_scoped_per_client_ip(self):
        payload = {'username': self.USERNAME, 'password': 'wrong-password'}

        self.post(self.login_url, data=payload, status_code=400)
        self.post(self.login_url, data=payload, status_code=400)
        self.post(self.login_url, data=payload, status_code=429)

        # a different client IP is not affected by the first client's throttling
        response = self.post(
            self.login_url, data=payload, status_code=400,
            REMOTE_ADDR='10.0.0.99',
        )
        self.assertEqual(response.status_code, 400)

    @override_api_settings(RATE_LIMIT_LOGIN=None)
    def test_throttle_disabled_when_rate_is_none(self):
        payload = {'username': self.USERNAME, 'password': 'wrong-password'}

        for _ in range(5):
            self.post(self.login_url, data=payload, status_code=400)
