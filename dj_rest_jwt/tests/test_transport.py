from django.test import Client, TestCase, override_settings

from .helpers import AUTH, Api, make_user


class CookieTransportTests(TestCase):
    """Browser SPA: no X-Auth-Transport header."""

    def setUp(self):
        make_user()

    def test_login_sets_httponly_cookies_and_hides_every_token(self):
        api = Api()
        resp, body = api.login()
        self.assertEqual(resp.status_code, 200, body)
        self.assertEqual(set(body["meta"]), {"is_authenticated"})

        access, refresh = resp.cookies["access_token"], resp.cookies["refresh_token"]
        for cookie in (access, refresh):
            self.assertTrue(cookie["httponly"])
            self.assertTrue(cookie["secure"])
            self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(access["path"], "/")
        self.assertEqual(refresh["path"], f"{AUTH}/tokens/refresh")
        self.assertIn("csrftoken", resp.cookies)

    def test_drf_endpoint_requires_csrf_on_unsafe_methods(self):
        api = Api()
        api.login()
        self.assertEqual(api.call("get", "/api/me")[0].status_code, 200)
        self.assertEqual(api.c.post("/api/me").status_code, 403)     # no X-CSRFToken
        self.assertEqual(api.call("post", "/api/me", {})[0].status_code, 200)

    def test_allauth_endpoints_accept_the_cookie(self):
        api = Api()
        api.login()
        resp, body = api.call("get", f"{AUTH}/account/authenticators")
        self.assertEqual(resp.status_code, 200, body)

    def test_allauth_endpoints_reject_cookie_without_csrf(self):
        api = Api()
        api.login()
        resp = api.c.post(f"{AUTH}/account/password/change", {"new_password": "x"},
                          content_type="application/json")
        self.assertEqual(resp.status_code, 401)

    def test_refresh_from_cookie_rotates_both_cookies(self):
        api = Api()
        api.login()
        old = api.cookie("access_token"), api.cookie("refresh_token")
        resp, body = api.refresh_tokens()
        self.assertEqual(resp.status_code, 200, body)
        self.assertEqual(body["data"], {})
        self.assertNotEqual(api.cookie("access_token"), old[0])
        self.assertNotEqual(api.cookie("refresh_token"), old[1])

    def test_refresh_ignores_a_refresh_token_in_the_body(self):
        api = Api()
        api.login()
        api.c.cookies.pop("refresh_token")
        resp, _ = api.call("post", f"{AUTH}/tokens/refresh", {"refresh_token": "anything"})
        self.assertEqual(resp.status_code, 401)

    def test_logout_clears_cookies_and_kills_the_access_token(self):
        api = Api()
        api.login()
        access = api.cookie("access_token")
        api.call("delete", f"{AUTH}/auth/session")
        self.assertIsNone(api.cookie("access_token"))
        self.assertIsNone(api.cookie("refresh_token"))
        self.assertEqual(Client().get("/api/me", HTTP_AUTHORIZATION=f"Bearer {access}").status_code, 401)


class HeaderTransportTests(TestCase):
    """Native app: X-Auth-Transport: header, Authorization: Bearer."""

    def setUp(self):
        make_user()

    def test_login_returns_tokens_in_body_and_sets_no_cookies(self):
        api = Api(header=True)
        resp, body = api.login()
        self.assertEqual(resp.status_code, 200, body)
        self.assertIn("access_token", body["meta"])
        self.assertIn("refresh_token", body["meta"])
        self.assertNotIn("session_token", body["meta"])
        self.assertNotIn("access_token", resp.cookies)
        self.assertNotIn("refresh_token", resp.cookies)

    def test_bearer_works_for_drf_and_allauth(self):
        api = Api(header=True)
        api.login()
        self.assertEqual(api.call("get", "/api/me")[0].status_code, 200)
        self.assertEqual(api.call("post", "/api/me", {})[0].status_code, 200)   # no CSRF for Bearer
        self.assertEqual(api.call("get", f"{AUTH}/account/authenticators")[0].status_code, 200)

    def test_refresh_in_body(self):
        api = Api(header=True)
        api.login()
        old = api.refresh
        resp, body = api.refresh_tokens()
        self.assertEqual(resp.status_code, 200, body)
        self.assertNotEqual(api.refresh, old)


class TransportIsolationTests(TestCase):
    """The two transports never leak into each other."""

    def setUp(self):
        make_user()

    def test_header_mode_request_is_not_authenticated_by_cookie(self):
        browser = Api()
        browser.login()
        resp = browser.c.get("/api/me", HTTP_X_AUTH_TRANSPORT="header")
        self.assertEqual(resp.status_code, 401)
        resp = browser.c.get(f"{AUTH}/account/authenticators", HTTP_X_AUTH_TRANSPORT="header")
        self.assertEqual(resp.status_code, 401)

    def test_header_mode_refresh_cannot_read_the_refresh_cookie(self):
        browser = Api()
        browser.login()
        resp = browser.c.post(f"{AUTH}/tokens/refresh", "{}", content_type="application/json",
                              HTTP_X_AUTH_TRANSPORT="header")
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn("access_token", resp.content.decode())

    def test_invalid_bearer_is_not_rescued_by_cookie(self):
        browser = Api()
        browser.login()
        resp = browser.c.get("/api/me", HTTP_AUTHORIZATION="Bearer garbage")
        self.assertEqual(resp.status_code, 401)

    @override_settings(DJ_REST_JWT={"TRANSPORTS": ("cookie",)})
    def test_header_transport_can_be_disabled(self):
        resp, body = Api(header=True).login()
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("access_token", body["meta"])
        self.assertIn("access_token", resp.cookies)

    @override_settings(DJ_REST_JWT={"TRANSPORTS": ("header",)})
    def test_cookie_transport_can_be_disabled(self):
        api = Api()
        resp, body = api.login()
        self.assertIn("access_token", body["meta"])
        self.assertNotIn("access_token", resp.cookies)
