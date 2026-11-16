from io import StringIO

from django.conf import settings
from django.core.checks import run_checks
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings


def ids(**kwargs):
    silenced = set(settings.SILENCED_SYSTEM_CHECKS)
    return {m.id for m in run_checks(**kwargs) if m.id and m.id.startswith("dj_rest_jwt") and m.id not in silenced}


class SystemCheckTests(SimpleTestCase):

    def test_test_settings_are_clean(self):
        self.assertEqual(ids(), set())

    def test_preset_hashers_pass(self):
        from dj_rest_jwt import defaults
        with override_settings(PASSWORD_HASHERS=defaults.PASSWORD_HASHERS, SILENCED_SYSTEM_CHECKS=[]):
            self.assertNotIn("dj_rest_jwt.W008", ids())

    @override_settings(HEADLESS_JWT_PRIVATE_KEY="")
    def test_missing_key(self):
        self.assertIn("dj_rest_jwt.E002", ids())

    def test_missing_transport_middleware(self):
        middleware = [m for m in settings.MIDDLEWARE if "dj_rest_jwt" not in m]
        with override_settings(MIDDLEWARE=middleware):
            self.assertIn("dj_rest_jwt.E005", ids())

    @override_settings(HEADLESS_CLIENTS=("browser", "app"))
    def test_browser_client_warns(self):
        self.assertIn("dj_rest_jwt.W001", ids())

    @override_settings(HEADLESS_JWT_STATEFUL_VALIDATION_ENABLED=False)
    def test_stateless_validation_warns(self):
        self.assertIn("dj_rest_jwt.W003", ids())

    @override_settings(SESSION_COOKIE_AGE=60)
    def test_session_shorter_than_refresh_warns(self):
        self.assertIn("dj_rest_jwt.W005", ids())

    @override_settings(SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies")
    def test_cookie_sessions_are_an_error(self):
        self.assertIn("dj_rest_jwt.E004", ids())

    @override_settings(ACCOUNT_RATE_LIMITS=False)
    def test_disabled_rate_limits_warn(self):
        self.assertIn("dj_rest_jwt.W007", ids())

    @override_settings(HEADLESS_FRONTEND_URLS={})
    def test_missing_frontend_urls(self):
        self.assertIn("dj_rest_jwt.E008", ids())

    @override_settings(SOCIALACCOUNT_EMAIL_AUTHENTICATION=True)
    def test_email_authentication_warns(self):
        self.assertIn("dj_rest_jwt.W009", ids())

    @override_settings(ROOT_URLCONF="dj_rest_jwt.tests.urls_without_admin_login")
    def test_admin_login_not_mounted(self):
        self.assertIn("dj_rest_jwt.E009", ids())

    def test_deploy_checks(self):
        with override_settings(DJ_REST_JWT={"COOKIE_SECURE": False}):
            found = ids(include_deployment_checks=True)
        self.assertIn("dj_rest_jwt.W010", found)
        self.assertIn("dj_rest_jwt.W011", found)       # LocMemCache in tests


class GenerateKeyTests(SimpleTestCase):

    def test_prints_a_usable_private_key(self):
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        out = StringIO()
        call_command("generate_jwt_key", "--bits", "2048", stdout=out)
        key = load_pem_private_key(out.getvalue().encode(), password=None)
        self.assertEqual(key.key_size, 2048)


class EmailFlowTests(SimpleTestCase):
    """email_flows() and the frontend URLs each choice needs."""

    CODE_ONLY_URLS = {"account_reset_password": "x", "account_signup": "x"}

    def test_codes_need_no_link_pages(self):
        from dj_rest_jwt.defaults import email_flows
        with override_settings(HEADLESS_FRONTEND_URLS=self.CODE_ONLY_URLS, **email_flows()):
            self.assertNotIn("dj_rest_jwt.E008", ids())

    def test_links_need_their_pages(self):
        from dj_rest_jwt.defaults import email_flows
        flows = email_flows(verification="link", password_reset="link")
        self.assertFalse(flows["MFA_PASSKEY_SIGNUP_ENABLED"], "passkey signup needs code verification")
        with override_settings(HEADLESS_FRONTEND_URLS=self.CODE_ONLY_URLS, **flows):
            messages = [m for m in run_checks() if m.id == "dj_rest_jwt.E008"]
            self.assertEqual(len(messages), 1)
            self.assertIn("account_confirm_email", messages[0].msg)
            self.assertIn("account_reset_password_from_key", messages[0].msg)

    def test_bad_choice_is_rejected(self):
        from dj_rest_jwt.defaults import email_flows
        with self.assertRaises(ValueError):
            email_flows(verification="magic")


class CopyEmailTemplatesTests(SimpleTestCase):

    def test_copies_and_never_overwrites(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            call_command("copy_email_templates", tmp, "--only", "email_confirmation", stdout=StringIO())
            target = Path(tmp, "account/email/email_confirmation_message.txt")
            self.assertTrue(target.exists())
            self.assertFalse(Path(tmp, "account/email/password_reset_code_message.txt").exists())
            target.write_text("mine")
            call_command("copy_email_templates", tmp, stdout=StringIO())
            self.assertEqual(target.read_text(), "mine")
            self.assertTrue(Path(tmp, "mfa/email/totp_activated_subject.txt").exists())
