"""
Deployment checks for configurations that are individually reasonable but
dangerous in combination - the kind of thing that doesn't show up until someone
is already exploiting it.

Run automatically by `manage.py check` and at startup.
"""
from django.conf import settings
from django.core.checks import Warning, register

from .app_settings import api_settings

W001 = 'dj_rest_jwt.W001'
W002 = 'dj_rest_jwt.W002'
W003 = 'dj_rest_jwt.W003'
W004 = 'dj_rest_jwt.W004'


@register()
def check_cookie_csrf_configuration(app_configs, **kwargs):
    """
    SameSite=None turns off the browser's own CSRF defence for the auth cookie,
    which is exactly the defence JWTCookieAuthentication relies on by default.
    """
    errors = []
    using_cookies = bool(api_settings.JWT_AUTH_COOKIE or api_settings.JWT_AUTH_REFRESH_COOKIE)
    if not (api_settings.USE_JWT and using_cookies):
        return errors

    samesite = (api_settings.JWT_AUTH_SAMESITE or '').lower()
    if samesite == 'none' and not api_settings.JWT_AUTH_COOKIE_USE_CSRF:
        errors.append(Warning(
            "REST_AUTH['JWT_AUTH_SAMESITE'] is 'None' but "
            "JWT_AUTH_COOKIE_USE_CSRF is False.",
            hint=(
                "SameSite=None lets any site send your auth cookie on a "
                "cross-origin request, and cookie authentication then performs "
                "no CSRF check of its own. Set "
                "REST_AUTH['JWT_AUTH_COOKIE_USE_CSRF'] = True, or use "
                "SameSite='Lax'."
            ),
            id=W001,
        ))

    if samesite == 'none' and not api_settings.JWT_AUTH_SECURE:
        errors.append(Warning(
            "REST_AUTH['JWT_AUTH_SAMESITE'] is 'None' but JWT_AUTH_SECURE is False.",
            hint='Browsers reject SameSite=None cookies that are not marked Secure.',
            id=W002,
        ))

    if not api_settings.JWT_AUTH_SECURE and not settings.DEBUG:
        errors.append(Warning(
            "REST_AUTH['JWT_AUTH_SECURE'] is False with DEBUG off.",
            hint=(
                'Auth cookies will be sent over plain HTTP. Set '
                "REST_AUTH['JWT_AUTH_SECURE'] = True in production."
            ),
            id=W003,
        ))

    return errors


@register()
def check_token_revocation_configuration(app_configs, **kwargs):
    """Revocation on password change silently does nothing without the blacklist app."""
    errors = []
    if (
        api_settings.USE_JWT and  # noqa: W504
        api_settings.REVOKE_TOKENS_ON_PASSWORD_CHANGE and  # noqa: W504
        'rest_framework_simplejwt.token_blacklist' not in settings.INSTALLED_APPS
    ):
        errors.append(Warning(
            "REST_AUTH['REVOKE_TOKENS_ON_PASSWORD_CHANGE'] is on but "
            "'rest_framework_simplejwt.token_blacklist' is not in INSTALLED_APPS.",
            hint=(
                'Without it there is nowhere to record a revocation, so refresh '
                'tokens issued before a password change or reset stay valid '
                'until they expire.'
            ),
            id=W004,
        ))
    return errors
