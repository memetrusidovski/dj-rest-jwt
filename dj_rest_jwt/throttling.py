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
