import re
from unittest import mock

from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

from .helpers import (
    AUTH,
    ORIGIN,
    PASSWORD,
    Api,
    VerifyingDevice,
    decode_options,
    encode_credential,
    google_identity,
    google_login,
    make_user,
    pending_flows,
    totp_code,
)

GOOGLE_VERIFY = "allauth.socialaccount.providers.google.views._verify_and_decode"


class SignupTests(TestCase):

    def test_signup_requires_the_emailed_code_then_signs_in(self):
        api = Api()
        resp, body = api.call("post", f"{AUTH}/auth/signup", {"email": "new@example.com", "password": PASSWORD})
        self.assertEqual(resp.status_code, 401, body)
        self.assertEqual(pending_flows(body), ["verify_email"])
        self.assertIsNone(api.cookie("access_token"))

        code = re.search(r"^([A-Z0-9]{4}-[A-Z0-9]{4})$", mail.outbox[-1].body, re.M).group(1)
        resp, body = api.call("post", f"{AUTH}/auth/email/verify", {"key": code})
        self.assertEqual(resp.status_code, 200, body)
        self.assertIsNotNone(api.cookie("access_token"))

    def test_signup_does_not_reveal_existing_accounts(self):
        make_user(email="taken@example.com")
        resp, body = Api().call("post", f"{AUTH}/auth/signup", {"email": "taken@example.com", "password": PASSWORD})
        self.assertEqual(resp.status_code, 401, body)
        self.assertEqual(pending_flows(body), ["verify_email"])


class MFATests(TestCase):

    def setUp(self):
        self.user = make_user()
        self.secret = generate_totp_secret()
        TOTP.activate(self.user, self.secret)

    def test_password_login_is_challenged_for_totp(self):
        api = Api()
        resp, body = api.login()
        self.assertEqual(resp.status_code, 401, body)
        self.assertIn("mfa_authenticate", pending_flows(body))
        self.assertIsNone(api.cookie("access_token"))

        resp, body = api.call("post", f"{AUTH}/auth/2fa/authenticate", {"code": "000000"})
        self.assertEqual(resp.status_code, 400)
        resp, body = api.call("post", f"{AUTH}/auth/2fa/authenticate", {"code": totp_code(self.secret)})
        self.assertEqual(resp.status_code, 200, body)
        self.assertIsNotNone(api.cookie("access_token"))

    def test_google_login_is_challenged_for_totp_too(self):
        SocialAccount.objects.create(user=self.user, provider="google", uid="g-123")
        api = Api()
        with mock.patch(GOOGLE_VERIFY, return_value=google_identity()):
            resp, body = google_login(api)
        self.assertEqual(resp.status_code, 401, body)
        self.assertIn("mfa_authenticate", pending_flows(body))
        self.assertIsNone(api.cookie("access_token"))


class GoogleTests(TestCase):

    def test_new_user_signs_in_with_a_google_id_token(self):
        api = Api()
        with mock.patch(GOOGLE_VERIFY, return_value=google_identity(sub="g-new", email="bob@example.com")):
            resp, body = google_login(api)
        self.assertEqual(resp.status_code, 200, body)
        self.assertIsNotNone(api.cookie("access_token"))
        self.assertTrue(get_user_model().objects.filter(email="bob@example.com").exists())

    def test_google_cannot_take_over_an_existing_password_account(self):
        make_user(email="carol@example.com")
        api = Api()
        with mock.patch(GOOGLE_VERIFY, return_value=google_identity(sub="g-carol", email="carol@example.com")):
            resp, body = google_login(api)
        self.assertEqual(resp.status_code, 401, body)
        self.assertEqual(pending_flows(body), ["verify_email"])
        self.assertIsNone(api.cookie("access_token"))

    def test_native_app_gets_tokens_in_body(self):
        api = Api(header=True)
        with mock.patch(GOOGLE_VERIFY, return_value=google_identity(sub="g-app", email="app@example.com")):
            resp, body = google_login(api)
        self.assertEqual(resp.status_code, 200, body)
        self.assertIn("access_token", body["meta"])


class PasskeyTests(TestCase):

    def test_register_a_passkey_then_sign_in_without_a_password(self):
        user = make_user()
        api = Api()
        api.login()
        device = VerifyingDevice()

        # Step-up: a fresh login doesn't count, allauth wants the password again.
        resp, body = api.call("get", f"{AUTH}/account/authenticators/webauthn?passwordless")
        self.assertEqual(resp.status_code, 401, body)
        self.assertIn("reauthenticate", [f["id"] for f in body["data"]["flows"]])
        self.assertEqual(api.call("post", f"{AUTH}/auth/reauthenticate", {"password": PASSWORD})[0].status_code, 200)

        resp, body = api.call("get", f"{AUTH}/account/authenticators/webauthn?passwordless")
        self.assertEqual(resp.status_code, 200, body)
        cred = device.create(decode_options(body["data"]["creation_options"]), ORIGIN)
        resp, body = api.call("post", f"{AUTH}/account/authenticators/webauthn",
                              {"name": "Laptop", "credential": encode_credential(cred)})
        self.assertEqual(resp.status_code, 200, body)
        self.assertTrue(Authenticator.objects.filter(user=user, type=Authenticator.Type.WEBAUTHN).exists())

        fresh = Api()
        resp, body = fresh.call("get", f"{AUTH}/auth/webauthn/login")
        self.assertEqual(resp.status_code, 200, body)
        assertion = device.get(decode_options(body["data"]["request_options"]), ORIGIN)
        resp, body = fresh.call("post", f"{AUTH}/auth/webauthn/login", {"credential": encode_credential(assertion)})
        self.assertEqual(resp.status_code, 200, body)
        self.assertIsNotNone(fresh.cookie("access_token"))
