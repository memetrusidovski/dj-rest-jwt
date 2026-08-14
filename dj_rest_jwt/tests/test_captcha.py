from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from dj_rest_jwt.captcha import verify_captcha

from .mixins import TestsMixin
from .utils import override_api_settings

User = get_user_model()

REGISTRATION_DATA = {
    'username': 'captchauser',
    'password1': 'super-secret-pass-123',
    'password2': 'super-secret-pass-123',
}


@override_settings(ROOT_URLCONF='tests.urls')
class HoneypotTests(TestsMixin, TestCase):
    def setUp(self):
        self.init()

    def test_registration_succeeds_when_honeypot_left_blank(self):
        self.post(self.register_url, data=REGISTRATION_DATA, status_code=201)

    def test_registration_rejected_when_honeypot_filled(self):
        payload = dict(REGISTRATION_DATA, website='http://spam.example')
        self.post(self.register_url, data=payload, status_code=400)
        self.assertEqual(User.objects.filter(username='captchauser').count(), 0)

    @override_api_settings(ENABLE_HONEYPOT=False)
    def test_honeypot_field_absent_when_disabled(self):
        payload = dict(REGISTRATION_DATA, website='http://spam.example')
        # with honeypot disabled, an extraneous 'website' field is just ignored
        self.post(self.register_url, data=payload, status_code=201)


@override_settings(ROOT_URLCONF='tests.urls')
class RegistrationCaptchaTests(TestsMixin, TestCase):
    def setUp(self):
        self.init()
        self._captcha_ctx = override_api_settings(ENABLE_CAPTCHA=True, CAPTCHA_SECRET_KEY='test-secret')
        self._captcha_ctx.__enter__()
        self.addCleanup(self._captcha_ctx.__exit__, None, None, None)

    def test_registration_requires_captcha_token_when_enabled(self):
        self.post(self.register_url, data=REGISTRATION_DATA, status_code=400)
        self.assertIn('captcha_token', self.response.json)

    @patch('dj_rest_jwt.captcha.requests.post')
    def test_registration_succeeds_with_valid_captcha(self, mock_post):
        mock_post.return_value.json.return_value = {'success': True}
        payload = dict(REGISTRATION_DATA, captcha_token='good-token')
        self.post(self.register_url, data=payload, status_code=201)

    @patch('dj_rest_jwt.captcha.requests.post')
    def test_registration_rejected_with_failed_captcha(self, mock_post):
        mock_post.return_value.json.return_value = {'success': False}
        payload = dict(REGISTRATION_DATA, captcha_token='bad-token')
        self.post(self.register_url, data=payload, status_code=400)
        self.assertEqual(User.objects.filter(username='captchauser').count(), 0)


class VerifyCaptchaUnitTests(TestCase):
    @override_api_settings(ENABLE_CAPTCHA=True, CAPTCHA_SECRET_KEY='test-secret')
    @patch('dj_rest_jwt.captcha.requests.post')
    def test_recaptcha_v3_respects_min_score(self, mock_post):
        with override_api_settings(CAPTCHA_BACKEND='recaptcha_v3', CAPTCHA_RECAPTCHA_V3_MIN_SCORE=0.5):
            mock_post.return_value.json.return_value = {'success': True, 'score': 0.2}
            self.assertFalse(verify_captcha('tok', remote_ip='127.0.0.1'))

            mock_post.return_value.json.return_value = {'success': True, 'score': 0.9}
            self.assertTrue(verify_captcha('tok', remote_ip='127.0.0.1'))

    @override_api_settings(ENABLE_CAPTCHA=True, CAPTCHA_SECRET_KEY='test-secret')
    @patch('dj_rest_jwt.captcha.requests.post', side_effect=requests.ConnectionError('network down'))
    def test_verify_captcha_fails_closed_on_network_error(self, mock_post):
        self.assertFalse(verify_captcha('tok'))

    def test_verify_captcha_returns_false_for_empty_token(self):
        with override_api_settings(ENABLE_CAPTCHA=True, CAPTCHA_SECRET_KEY='test-secret'):
            self.assertFalse(verify_captcha(''))
