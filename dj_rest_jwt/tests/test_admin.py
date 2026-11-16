from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret
from django.contrib import admin
from django.test import Client, TestCase

from .helpers import PASSWORD, make_user, totp_code


class AdminLoginTests(TestCase):

    def setUp(self):
        self.staff = make_user(email="admin@example.com", is_staff=True, is_superuser=True)
        self.secret = generate_totp_secret()
        TOTP.activate(self.staff, self.secret)
        self.c = Client(secure=True)

    def test_admin_site_login_is_wrapped_on_startup(self):
        self.assertTrue(getattr(admin.site.login, "_dj_rest_jwt_secured", False))

    def test_admin_login_page_renders(self):
        resp = self.c.get("/admin/auth/login/")
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "signup")

    def test_admin_login_goes_through_allauth_with_mfa(self):
        resp = self.c.get("/admin/", follow=True)
        self.assertEqual(resp.request["PATH_INFO"], "/admin/auth/login/")

        resp = self.c.post("/admin/auth/login/?next=/admin/", {"login": "admin@example.com", "password": PASSWORD})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], "/admin/auth/login/mfa/")
        self.assertEqual(self.c.get("/admin/").status_code, 302, "not in until MFA is done")

        resp = self.c.post("/admin/auth/login/mfa/", {"code": totp_code(self.secret)})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.c.get("/admin/").status_code, 200)

    def test_stock_admin_password_form_no_longer_logs_in(self):
        resp = self.c.post("/admin/login/?next=/admin/", {"username": "admin", "password": PASSWORD})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].startswith("/admin/auth/login/"))
        self.assertEqual(self.c.get("/admin/").status_code, 302)

    def test_non_staff_cannot_reach_the_admin(self):
        make_user(email="eve@example.com")
        self.c.post("/admin/auth/login/", {"login": "eve@example.com", "password": PASSWORD})
        self.assertEqual(self.c.get("/admin/login/").status_code, 403)
        self.assertNotEqual(self.c.get("/admin/").status_code, 200)
