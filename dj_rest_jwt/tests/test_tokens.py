from datetime import timedelta
from unittest import mock

import time_machine
from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from dj_rest_jwt.signals import refresh_token_reused

from .helpers import AUTH, PASSWORD, Api, make_user, totp_code


def bearer_get(path, access):
    return Client().get(path, HTTP_AUTHORIZATION=f"Bearer {access}")


@override_settings(DJ_REST_JWT={"REFRESH_REUSE_GRACE_SECONDS": 0})
class RefreshReuseTests(TestCase):

    def setUp(self):
        make_user()

    def test_reuse_of_a_rotated_token_ends_the_session(self):
        api = Api(header=True)
        api.login()
        stolen = api.refresh
        self.assertEqual(api.refresh_tokens()[0].status_code, 200)

        received = []
        refresh_token_reused.connect(lambda **kw: received.append(kw), weak=False)
        thief = Api(header=True)
        thief.refresh = stolen
        with mock.patch("time.time", return_value=__import__("time").time() + 1):
            self.assertEqual(thief.refresh_tokens()[0].status_code, 401)

        self.assertEqual(len(received), 1)
        self.assertEqual(api.refresh_tokens()[0].status_code, 401, "the whole session must be dead")
        self.assertEqual(bearer_get("/api/me", api.access).status_code, 401)

    @override_settings(DJ_REST_JWT={"REFRESH_REUSE_GRACE_SECONDS": 10})
    def test_reuse_inside_the_grace_window_is_refused_but_not_fatal(self):
        api = Api(header=True)
        api.login()
        first = api.refresh
        api.refresh_tokens()
        other_tab = Api(header=True)
        other_tab.refresh = first
        resp, body = other_tab.refresh_tokens()
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(body["errors"][0]["code"], "token_rotated")
        self.assertEqual(api.refresh_tokens()[0].status_code, 200)

    @override_settings(DJ_REST_JWT={"REFRESH_REUSE_GRACE_SECONDS": 10})
    def test_losing_a_refresh_race_in_cookie_mode_keeps_the_new_cookies(self):
        api = Api()
        api.login()
        stale = api.cookie("refresh_token")
        self.assertEqual(api.refresh_tokens()[0].status_code, 200)
        fresh = api.cookie("refresh_token")

        api.c.cookies["refresh_token"] = stale      # the other tab's in-flight request
        api.c.cookies["refresh_token"]["path"] = f"{AUTH}/tokens/refresh"
        resp, _ = api.refresh_tokens()
        self.assertEqual(resp.status_code, 409)
        self.assertNotIn("refresh_token", resp.cookies, "must not clear the winner's cookies")

        api.c.cookies["refresh_token"] = fresh
        api.c.cookies["refresh_token"]["path"] = f"{AUTH}/tokens/refresh"
        self.assertEqual(api.call("get", "/api/me")[0].status_code, 200)
        self.assertEqual(api.refresh_tokens()[0].status_code, 200)

    def test_garbage_refresh_token_is_just_401(self):
        api = Api(header=True)
        api.refresh = "not-a-jwt"
        self.assertEqual(api.refresh_tokens()[0].status_code, 401)


class SessionTests(TestCase):

    def setUp(self):
        make_user()

    def test_revoking_another_device_kills_its_tokens_immediately(self):
        phone, laptop = Api(header=True), Api(header=True)
        phone.login()
        laptop.login()
        resp, body = laptop.call("get", f"{AUTH}/auth/sessions")
        others = [s["id"] for s in body["data"] if not s["is_current"]]
        self.assertEqual(len(others), 1)

        resp, body = laptop.call("delete", f"{AUTH}/auth/sessions", {"sessions": others})
        self.assertEqual(resp.status_code, 200, body)
        self.assertEqual(laptop.call("get", "/api/me")[0].status_code, 200, "changer stays signed in")
        self.assertEqual(phone.call("get", "/api/me")[0].status_code, 401, "other devices are out at once")
        self.assertEqual(phone.refresh_tokens()[0].status_code, 401)
        self.assertEqual(phone.refresh_tokens()[0].status_code, 401)
        self.assertEqual(laptop.call("get", "/api/me")[0].status_code, 200)

    def test_pending_login_token_is_dead_once_login_completes(self):
        """The X-Session-Token handed out mid-login must not become a credential."""
        from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret
        from django.contrib.auth import get_user_model

        secret = generate_totp_secret()
        TOTP.activate(get_user_model().objects.get(), secret)
        api = Api()
        api.login()
        pending = api.session_token
        self.assertTrue(pending)
        api.call("post", f"{AUTH}/auth/2fa/authenticate", {"code": totp_code(secret)})
        self.assertIsNotNone(api.cookie("access_token"))

        resp = Client().get(f"{AUTH}/auth/session", HTTP_X_SESSION_TOKEN=pending)
        self.assertNotEqual(resp.status_code, 200)

    def test_password_change_signs_out_other_devices(self):
        phone, laptop = Api(header=True), Api(header=True)
        phone.login()
        laptop.login()
        laptop.call("post", f"{AUTH}/auth/reauthenticate", {"password": PASSWORD})
        resp, body = laptop.call("post", f"{AUTH}/account/password/change",
                                 {"current_password": PASSWORD, "new_password": "Another-Strong-77-Pass"})
        self.assertEqual(resp.status_code, 200, body)
        self.assertEqual(laptop.call("get", "/api/me")[0].status_code, 200, "changer stays signed in")
        self.assertEqual(phone.call("get", "/api/me")[0].status_code, 401, "other devices are out at once")
        self.assertEqual(phone.refresh_tokens()[0].status_code, 401)


class StaySignedInTests(TestCase):
    """Google/Instagram-style sliding sessions."""

    def setUp(self):
        make_user()

    def test_returning_every_few_days_stays_signed_in_for_six_months(self):
        with time_machine.travel(timezone.now(), tick=False) as clock:
            api = Api()
            api.login()
            for _ in range(60):
                clock.shift(timedelta(days=3))
                self.assertEqual(api.call("get", "/api/me")[0].status_code, 401)   # access expired
                resp, body = api.refresh_tokens()
                self.assertEqual(resp.status_code, 200, body)
                self.assertEqual(api.call("get", "/api/me")[0].status_code, 200)

    def test_away_longer_than_the_refresh_lifetime_must_log_in(self):
        with time_machine.travel(timezone.now(), tick=False) as clock:
            api = Api()
            api.login()
            clock.shift(timedelta(seconds=settings.HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN + 60))
            self.assertEqual(api.refresh_tokens()[0].status_code, 401)
