"""
Regression tests for the security fixes in the hardening pass.

Each test here maps to a specific weakness that was found and closed; they're
grouped in one module so it's obvious what would break if a fix were reverted.
"""
import json
import time
from unittest.mock import patch

import pyotp
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from dj_rest_jwt.mfa.models import Authenticator
from dj_rest_jwt.mfa.recovery_codes import RecoveryCodes
from dj_rest_jwt.mfa.totp import TOTP, generate_totp_secret
from dj_rest_jwt.mfa.utils import (consume_ephemeral_token,
                                   create_ephemeral_token,
                                   verify_ephemeral_token)

from .mixins import APIClient, TestsMixin
from .utils import override_api_settings

try:
    from django.urls import reverse
except ImportError:  # pragma: no cover
    from django.core.urlresolvers import reverse  # noqa

User = get_user_model()


@override_settings(ROOT_URLCONF='tests.mfa_urls')
class MFAVerifyThrottlingTests(TestsMixin, TestCase):
    """
    The second-factor exchange used to carry only a `throttle_scope`, which
    does nothing unless a project wires up ScopedRateThrottle - so a 6-digit
    code could be brute forced without limit.
    """
    USERNAME = 'throttled'
    PASS = 'testpassword123!'
    EMAIL = 'throttled@example.com'

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(self.USERNAME, self.EMAIL, self.PASS)
        self.login_url = reverse('rest_login')
        self.mfa_verify_url = reverse('mfa_verify')
        self.secret = generate_totp_secret()
        TOTP.activate(self.user, self.secret)
        RecoveryCodes.activate(self.user)
        cache.clear()

    def test_mfa_verify_endpoint_is_throttled_by_default(self):
        from dj_rest_jwt.mfa.views import MFAVerifyView
        throttles = [t.__class__.__name__ for t in MFAVerifyView().get_throttles()]
        self.assertIn('MFAVerifyRateThrottle', throttles)

    def test_brute_forcing_the_second_factor_is_rate_limited(self):
        with override_api_settings(RATE_LIMIT_MFA_VERIFY='3/min'):
            response = self.post(
                self.login_url,
                data={'username': self.USERNAME, 'password': self.PASS},
                status_code=200,
            )
            ephemeral_token = response.json['ephemeral_token']

            for _ in range(3):
                self.post(
                    self.mfa_verify_url,
                    data={'ephemeral_token': ephemeral_token, 'code': '000000'},
                    status_code=400,
                )

            self.post(
                self.mfa_verify_url,
                data={'ephemeral_token': ephemeral_token, 'code': '000000'},
                status_code=429,
            )

    def test_throttle_follows_the_ephemeral_token_not_just_the_ip(self):
        """Rotating source addresses must not buy an attacker extra guesses."""
        with override_api_settings(RATE_LIMIT_MFA_VERIFY='3/min'):
            response = self.post(
                self.login_url,
                data={'username': self.USERNAME, 'password': self.PASS},
                status_code=200,
            )
            ephemeral_token = response.json['ephemeral_token']

            for i in range(3):
                self.post(
                    self.mfa_verify_url,
                    data={'ephemeral_token': ephemeral_token, 'code': '000000'},
                    REMOTE_ADDR=f'10.0.0.{i}',
                    status_code=400,
                )

            self.post(
                self.mfa_verify_url,
                data={'ephemeral_token': ephemeral_token, 'code': '000000'},
                REMOTE_ADDR='10.0.0.99',
                status_code=429,
            )


class TOTPReplayTests(TestCase):
    """A TOTP code is valid for a window of ~90s; it must still only work once."""

    def setUp(self):
        self.user = User.objects.create_user('replay', 'replay@example.com', 'pw12345678!')
        self.secret = generate_totp_secret()
        TOTP.activate(self.user, self.secret)

    def _code(self, at=None):
        totp = pyotp.TOTP(self.secret)
        return totp.at(at) if at is not None else totp.now()

    def test_code_cannot_be_replayed(self):
        code = self._code()
        self.assertTrue(TOTP.validate_code(self.user, code))
        self.assertFalse(TOTP.validate_code(self.user, code))

    def test_earlier_window_code_is_rejected_after_a_later_one(self):
        """
        The old implementation only remembered the single last code, so an
        attacker who captured one could replay it as soon as any other code had
        been used in between. Burning the whole window up to the accepted step
        closes that.
        """
        now = time.time()
        previous = self._code(at=now - 30)
        current = self._code(at=now)
        if previous == current:  # pragma: no cover - straddles a step boundary
            self.skipTest('adjacent time steps produced the same code')

        self.assertTrue(TOTP.validate_code(self.user, current))
        self.assertFalse(TOTP.validate_code(self.user, previous))


class TOTPSecretStorageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('crypt', 'crypt@example.com', 'pw12345678!')

    def test_secret_is_not_readable_from_the_database_row(self):
        secret = generate_totp_secret()
        TOTP.activate(self.user, secret)

        auth = Authenticator.objects.get(user=self.user, type=Authenticator.Type.TOTP)
        self.assertNotIn(secret, json.dumps(auth.data))
        # ...but the application can still read it back.
        self.assertEqual(TOTP.get_secret(self.user), secret)

    def test_legacy_signed_secret_is_still_readable_and_gets_upgraded(self):
        from django.core.signing import Signer
        secret = generate_totp_secret()
        legacy = Signer(salt='dj-rest-jwt-mfa-totp-secret').sign(secret)
        Authenticator.objects.create(
            user=self.user,
            type=Authenticator.Type.TOTP,
            data={'secret': legacy},
        )

        self.assertEqual(TOTP.get_secret(self.user), secret)

        self.assertTrue(TOTP.validate_code(self.user, pyotp.TOTP(secret).now()))
        auth = Authenticator.objects.get(user=self.user, type=Authenticator.Type.TOTP)
        self.assertTrue(auth.data['secret'].startswith('enc:'))


class RecoveryCodeStorageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('codes', 'codes@example.com', 'pw12345678!')

    def test_codes_are_hashed_not_recoverable(self):
        codes = RecoveryCodes.activate(self.user)
        auth = Authenticator.objects.get(
            user=self.user, type=Authenticator.Type.RECOVERY_CODES,
        )
        stored = json.dumps(auth.data)
        for code in codes:
            self.assertNotIn(code, stored)

    def test_legacy_seed_codes_still_validate(self):
        """Existing installs must not have everyone's recovery codes invalidated."""
        seed = '00' * 32
        legacy_codes = RecoveryCodes._legacy_codes(seed, 10)
        Authenticator.objects.create(
            user=self.user,
            type=Authenticator.Type.RECOVERY_CODES,
            data={'seed': seed, 'used_mask': 0},
        )

        self.assertEqual(RecoveryCodes.get_unused_count(self.user), 10)
        self.assertTrue(RecoveryCodes.validate_code(self.user, legacy_codes[3]))
        self.assertFalse(RecoveryCodes.validate_code(self.user, legacy_codes[3]))
        self.assertEqual(RecoveryCodes.get_unused_count(self.user), 9)


class EphemeralTokenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('eph', 'eph@example.com', 'pw12345678!')
        cache.clear()

    def test_token_is_single_use(self):
        token = create_ephemeral_token(self.user)
        self.assertEqual(verify_ephemeral_token(token).pk, self.user.pk)

        consume_ephemeral_token(token)

        from dj_rest_jwt.mfa.utils import EphemeralTokenConsumed
        with self.assertRaises(EphemeralTokenConsumed):
            verify_ephemeral_token(token)

    def test_legacy_token_without_a_nonce_still_verifies(self):
        from django.core.signing import TimestampSigner
        token = TimestampSigner(salt='dj-rest-jwt-mfa').sign(str(self.user.pk))
        self.assertEqual(verify_ephemeral_token(token).pk, self.user.pk)


@override_settings(ROOT_URLCONF='tests.urls')
class PasswordChangeRevokesTokensTests(TestsMixin, TestCase):
    USERNAME = 'revoked'
    PASS = 'testpassword123!'
    NEW_PASS = 'anotherpassword456!'
    EMAIL = 'revoked@example.com'

    def setUp(self):
        self.init()
        self.user = User.objects.create_user(self.USERNAME, self.EMAIL, self.PASS)

    def test_refresh_tokens_are_blacklisted_on_password_change(self):
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken, OutstandingToken,
        )
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(self.user)
        self.assertFalse(
            BlacklistedToken.objects.filter(token__jti=refresh['jti']).exists(),
        )

        self.client.force_login(self.user)
        self.post(
            self.password_change_url,
            data={'new_password1': self.NEW_PASS, 'new_password2': self.NEW_PASS},
            status_code=200,
        )

        self.assertTrue(OutstandingToken.objects.filter(user=self.user).exists())
        self.assertTrue(
            BlacklistedToken.objects.filter(token__jti=refresh['jti']).exists(),
        )

    def test_revocation_can_be_switched_off(self):
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(self.user)
        self.client.force_login(self.user)

        with override_api_settings(REVOKE_TOKENS_ON_PASSWORD_CHANGE=False):
            self.post(
                self.password_change_url,
                data={'new_password1': self.NEW_PASS, 'new_password2': self.NEW_PASS},
                status_code=200,
            )

        self.assertFalse(
            BlacklistedToken.objects.filter(token__jti=refresh['jti']).exists(),
        )


class LoginByEmailEdgeCaseTests(TestCase):
    """`get_auth_user_using_orm` is the non-allauth login path."""

    def _serializer(self):
        from django.test import RequestFactory

        from dj_rest_jwt.serializers import LoginSerializer
        return LoginSerializer(context={'request': RequestFactory().post('/')})

    def test_duplicate_emails_do_not_raise(self):
        """
        Django's default User doesn't enforce a unique email, so two accounts
        can share one. That used to surface as an unhandled
        MultipleObjectsReturned - a 500 on the login endpoint.
        """
        User.objects.create_user('dup1', 'dup@example.com', 'pw12345678!')
        User.objects.create_user('dup2', 'dup@example.com', 'pw12345678!')

        result = self._serializer().get_auth_user_using_orm(None, 'dup@example.com', 'pw12345678!')
        self.assertIsNone(result)

    def test_unknown_email_still_runs_the_password_hasher(self):
        """Skipping the hash for unknown accounts leaks their existence by timing."""
        with patch.object(User, 'set_password') as set_password:
            self._serializer().get_auth_user_using_orm(None, 'nobody@example.com', 'pw12345678!')
        set_password.assert_called_once()


class DeploymentCheckTests(TestCase):
    """`manage.py check` should catch setting combinations that quietly
    disable a protection."""

    def _run(self, check):
        return {w.id for w in check(app_configs=None)}

    def test_samesite_none_without_csrf_is_flagged(self):
        from dj_rest_jwt.checks import check_cookie_csrf_configuration

        with override_api_settings(
            USE_JWT=True,
            JWT_AUTH_COOKIE='access',
            JWT_AUTH_SAMESITE='None',
            JWT_AUTH_COOKIE_USE_CSRF=False,
            JWT_AUTH_SECURE=True,
        ):
            self.assertIn('dj_rest_jwt.W001', self._run(check_cookie_csrf_configuration))

        with override_api_settings(
            USE_JWT=True,
            JWT_AUTH_COOKIE='access',
            JWT_AUTH_SAMESITE='None',
            JWT_AUTH_COOKIE_USE_CSRF=True,
            JWT_AUTH_SECURE=True,
        ):
            self.assertNotIn('dj_rest_jwt.W001', self._run(check_cookie_csrf_configuration))

    def test_samesite_none_without_secure_is_flagged(self):
        from dj_rest_jwt.checks import check_cookie_csrf_configuration

        with override_api_settings(
            USE_JWT=True,
            JWT_AUTH_COOKIE='access',
            JWT_AUTH_SAMESITE='None',
            JWT_AUTH_COOKIE_USE_CSRF=True,
            JWT_AUTH_SECURE=False,
        ):
            self.assertIn('dj_rest_jwt.W002', self._run(check_cookie_csrf_configuration))

    def test_nothing_flagged_when_cookies_are_not_in_use(self):
        from dj_rest_jwt.checks import check_cookie_csrf_configuration

        with override_api_settings(
            USE_JWT=True, JWT_AUTH_COOKIE=None, JWT_AUTH_REFRESH_COOKIE=None,
        ):
            self.assertEqual(self._run(check_cookie_csrf_configuration), set())

    @override_settings(INSTALLED_APPS=[
        'django.contrib.contenttypes', 'django.contrib.auth', 'dj_rest_jwt',
    ])
    def test_revocation_without_blacklist_app_is_flagged(self):
        from dj_rest_jwt.checks import check_token_revocation_configuration

        with override_api_settings(USE_JWT=True, REVOKE_TOKENS_ON_PASSWORD_CHANGE=True):
            self.assertIn(
                'dj_rest_jwt.W004', self._run(check_token_revocation_configuration),
            )


class QRCodeGenerationTests(TestCase):
    def test_activation_returns_a_qr_data_uri(self):
        from dj_rest_jwt.mfa.views import TOTPActivateView

        uri = TOTPActivateView._generate_qr_data_uri('otpauth://totp/Test:me?secret=ABCDEFGH')
        self.assertTrue(uri.startswith('data:image/svg+xml;base64,'))

    def test_missing_qrcode_dependency_degrades_gracefully(self):
        """qrcode is an optional extra; without it activation just omits the QR."""
        import sys

        from dj_rest_jwt.mfa.views import TOTPActivateView

        # A None entry in sys.modules makes the import raise ImportError, which
        # is far safer than patching builtins.__import__ globally.
        with patch.dict(sys.modules, {'qrcode': None, 'qrcode.image.svg': None}):
            self.assertEqual(TOTPActivateView._generate_qr_data_uri('otpauth://x'), '')


@override_settings(ROOT_URLCONF='tests.urls')
class UserDetailsUpdateTests(TestsMixin, TestCase):
    """
    Saving your own profile must not fail on your own username.

    allauth's `clean_username` rejects any name that already exists, with no
    notion of which user is being edited - so submitting an unchanged username
    was reported as "already taken", by yourself.
    """
    USERNAME = 'profileowner'
    PASS = 'testpassword123!'
    EMAIL = 'profileowner@example.com'

    def setUp(self):
        self.init()
        self.user = User.objects.create_user(self.USERNAME, self.EMAIL, self.PASS)
        self.client.force_login(self.user)

    def test_put_with_unchanged_username_succeeds(self):
        self.send_request(
            'put',
            self.user_url,
            data={'username': self.USERNAME, 'first_name': 'Ada', 'last_name': 'Lovelace'},
            status_code=200,
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Ada')
        self.assertEqual(self.user.username, self.USERNAME)

    def test_username_taken_by_someone_else_is_still_rejected(self):
        User.objects.create_user('someoneelse', 'other@example.com', self.PASS)
        self.send_request(
            'put',
            self.user_url,
            data={'username': 'someoneelse', 'first_name': '', 'last_name': ''},
            status_code=400,
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, self.USERNAME)

    def test_changing_to_a_free_username_succeeds(self):
        self.send_request(
            'put',
            self.user_url,
            data={'username': 'brandnew', 'first_name': '', 'last_name': ''},
            status_code=200,
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'brandnew')
