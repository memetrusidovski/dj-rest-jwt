from unittest import mock

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .helpers import AUTH, PASSWORD, Api

CAPTCHA = {"CAPTCHA_BACKEND": "turnstile", "CAPTCHA_SECRET_KEY": "secret"}


def signup(**extra):
    return Api().call("post", f"{AUTH}/auth/signup", {"email": "new@example.com", "password": PASSWORD, **extra})


def captcha_reply(success):
    reply = mock.Mock()
    reply.json.return_value = {"success": success}
    return reply


class HoneypotTests(TestCase):

    def test_filled_honeypot_rejects_signup(self):
        resp, body = signup(website="http://spam.example")
        self.assertEqual(resp.status_code, 400, body)
        self.assertFalse(get_user_model().objects.exists())

    def test_empty_honeypot_is_fine(self):
        resp, body = signup(website="")
        self.assertEqual(resp.status_code, 401, body)   # pending email verification
        self.assertTrue(get_user_model().objects.exists())


@override_settings(DJ_REST_JWT=CAPTCHA)
class CaptchaTests(TestCase):

    def test_missing_token_is_rejected(self):
        resp, body = signup()
        self.assertEqual(resp.status_code, 400, body)
        self.assertEqual(body["errors"][0]["param"], "captcha_token")

    def test_valid_token_passes(self):
        with mock.patch("dj_rest_jwt.signup.requests.post", return_value=captcha_reply(True)) as post:
            resp, body = signup(captcha_token="tok")
        self.assertEqual(resp.status_code, 401, body)
        self.assertEqual(post.call_args.kwargs["data"]["response"], "tok")

    def test_rejected_token_fails(self):
        with mock.patch("dj_rest_jwt.signup.requests.post", return_value=captcha_reply(False)):
            resp, body = signup(captcha_token="tok")
        self.assertEqual(resp.status_code, 400, body)
        self.assertFalse(get_user_model().objects.exists())

    def test_provider_outage_fails_closed(self):
        with mock.patch("dj_rest_jwt.signup.requests.post", side_effect=requests.ConnectionError):
            resp, body = signup(captcha_token="tok")
        self.assertEqual(resp.status_code, 400, body)
