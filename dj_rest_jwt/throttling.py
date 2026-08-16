import hashlib

from django.utils.encoding import force_bytes
from rest_framework.throttling import SimpleRateThrottle

from .app_settings import api_settings


class ConfigurableRateThrottle(SimpleRateThrottle):
    """
    Rate limiting for auth endpoints that works with zero configuration.

    Unlike DRF's ScopedRateThrottle, the rate isn't read from the project's
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] (which most projects never set,
    leaving auth endpoints unthrottled) - it comes from dj_rest_jwt's own
    settings, which ship with sane defaults and are overridable via REST_AUTH.
    """
    rate_setting_name = None

    def get_rate(self):
        return getattr(api_settings, self.rate_setting_name)

    def get_cache_key(self, request, view):
        if self.rate is None:
            return None
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class LoginRateThrottle(ConfigurableRateThrottle):
    scope = 'dj_rest_jwt_login'
    rate_setting_name = 'RATE_LIMIT_LOGIN'


class RegisterRateThrottle(ConfigurableRateThrottle):
    scope = 'dj_rest_jwt_register'
    rate_setting_name = 'RATE_LIMIT_REGISTER'


class PasswordResetRateThrottle(ConfigurableRateThrottle):
    scope = 'dj_rest_jwt_password_reset'
    rate_setting_name = 'RATE_LIMIT_PASSWORD_RESET'


class SensitiveAccountActionRateThrottle(ConfigurableRateThrottle):
    """Used for authenticated, security-sensitive actions: logout, password change."""
    scope = 'dj_rest_jwt_sensitive_action'
    rate_setting_name = 'RATE_LIMIT_SENSITIVE_ACTION'


class MFAVerifyRateThrottle(ConfigurableRateThrottle):
    """
    Guards the second-factor exchange.

    The caller is unauthenticated at this point (they hold an ephemeral token,
    not a session), so `get_cache_key` also buckets by the ephemeral token:
    rotating source IPs must not buy an attacker extra guesses against one
    account's 6-digit code.
    """
    scope = 'dj_rest_jwt_mfa_verify'
    rate_setting_name = 'RATE_LIMIT_MFA_VERIFY'

    def get_cache_key(self, request, view):
        if self.rate is None:
            return None
        token = ''
        if isinstance(getattr(request, 'data', None), dict):
            token = request.data.get('ephemeral_token') or ''
        if token:
            # Hash it: the raw token is a bearer credential and cache keys leak
            # into logs and monitoring far too easily.
            ident = hashlib.sha256(force_bytes(token)).hexdigest()
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class CredentialActionRateThrottle(ConfigurableRateThrottle):
    """Enrolling or removing an authenticator/passkey."""
    scope = 'dj_rest_jwt_credential_action'
    rate_setting_name = 'RATE_LIMIT_CREDENTIAL_ACTION'


class PasskeyChallengeRateThrottle(ConfigurableRateThrottle):
    """Unauthenticated issuance of WebAuthn challenges."""
    scope = 'dj_rest_jwt_passkey_challenge'
    rate_setting_name = 'RATE_LIMIT_PASSKEY_CHALLENGE'
