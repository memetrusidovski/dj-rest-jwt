"""
System checks for settings that silently weaken the setup.

Errors are configurations that don't work. Warnings are configurations that
work but drop a protection; silence one with SILENCED_SYSTEM_CHECKS if you
mean it. Deploy-only checks run under ``manage.py check --deploy``.
"""
from django.conf import settings
from django.core.checks import Error, Tags, Warning, register
from django.urls import NoReverseMatch, reverse

from . import conf

STRATEGY = "dj_rest_jwt.strategy.JWTTokenStrategy"
TRANSPORT_MIDDLEWARE = "dj_rest_jwt.middleware.TokenTransportMiddleware"


def required_frontend_urls():
    """The frontend routes allauth's emails link to, given the code/link choices."""
    names = ["account_reset_password", "account_signup"]   # "unknown account" emails
    if not _setting("ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED", False):
        names.insert(0, "account_confirm_email")
    if not _setting("ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED", False):
        names.append("account_reset_password_from_key")
    return names


def _setting(name, default=None):
    return getattr(settings, name, default)


def _strategy_ok():
    from allauth.headless import app_settings as headless_settings

    from .strategy import JWTTokenStrategy

    return isinstance(headless_settings.TOKEN_STRATEGY, JWTTokenStrategy)


@register(Tags.security)
def check_tokens(app_configs, **kwargs):
    errors = []
    if not _strategy_ok():
        errors.append(Error(
            "HEADLESS_TOKEN_STRATEGY is not dj-rest-jwt's JWT strategy (or a subclass).",
            hint=f'Set HEADLESS_TOKEN_STRATEGY = "{STRATEGY}".',
            id="dj_rest_jwt.E001",
        ))
    algorithm = _setting("HEADLESS_JWT_ALGORITHM", "RS256")
    if algorithm.startswith("RS") and not _setting("HEADLESS_JWT_PRIVATE_KEY"):
        errors.append(Error(
            "HEADLESS_JWT_PRIVATE_KEY is empty; no JWT can be signed.",
            hint="Run `manage.py generate_jwt_key` and load the output from your secrets/environment.",
            id="dj_rest_jwt.E002",
        ))
    if "app" not in tuple(_setting("HEADLESS_CLIENTS", ("browser", "app"))):
        errors.append(Error(
            'HEADLESS_CLIENTS does not include "app"; JWTs are only issued to the app client.',
            id="dj_rest_jwt.E003",
        ))
    if "browser" in tuple(_setting("HEADLESS_CLIENTS", ("browser", "app"))):
        errors.append(Warning(
            'HEADLESS_CLIENTS includes "browser", which authenticates with session cookies.',
            hint='Use HEADLESS_CLIENTS = ("app",) unless you deliberately want session auth.',
            id="dj_rest_jwt.W001",
        ))
    if not _setting("HEADLESS_ONLY", False):
        errors.append(Warning(
            "HEADLESS_ONLY is False, so allauth's server-rendered account pages are reachable.",
            id="dj_rest_jwt.W002",
        ))
    if not _setting("HEADLESS_JWT_STATEFUL_VALIDATION_ENABLED", False):
        errors.append(Warning(
            "Stateful JWT validation is off: logout and session revocation leave access tokens "
            "valid until they expire.",
            hint="Set HEADLESS_JWT_STATEFUL_VALIDATION_ENABLED = True.",
            id="dj_rest_jwt.W003",
        ))
    if not _setting("HEADLESS_JWT_ROTATE_REFRESH_TOKEN", True):
        errors.append(Warning(
            "Refresh token rotation is off, which also disables refresh-token reuse detection.",
            id="dj_rest_jwt.W004",
        ))
    return errors


@register(Tags.security)
def check_sessions(app_configs, **kwargs):
    errors = []
    refresh = _setting("HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN", 86400)
    if _setting("SESSION_COOKIE_AGE", 1209600) < refresh:
        errors.append(Warning(
            "SESSION_COOKIE_AGE is shorter than HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN; the session "
            "behind a refresh token will expire first and sign users out early.",
            hint="Set SESSION_COOKIE_AGE = HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN.",
            id="dj_rest_jwt.W005",
        ))
    engine = _setting("SESSION_ENGINE", "django.contrib.sessions.backends.db")
    if engine == "django.contrib.sessions.backends.db" and _setting("HEADLESS_JWT_STATEFUL_VALIDATION_ENABLED"):
        errors.append(Warning(
            "Stateful JWT validation reads the session on every request, and SESSION_ENGINE is the "
            "plain database backend.",
            hint='Use "django.contrib.sessions.backends.cached_db" with a shared cache.',
            id="dj_rest_jwt.W006",
        ))
    if engine == "django.contrib.sessions.backends.signed_cookies":
        errors.append(Error(
            "The signed_cookies session engine has no server-side store, so JWT sessions "
            "cannot be looked up or revoked.",
            id="dj_rest_jwt.E004",
        ))
    return errors


@register(Tags.security)
def check_middleware(app_configs, **kwargs):
    errors = []
    middleware = list(_setting("MIDDLEWARE", []))
    if TRANSPORT_MIDDLEWARE not in middleware:
        errors.append(Error(
            f"{TRANSPORT_MIDDLEWARE} is not in MIDDLEWARE; tokens would be left in response bodies "
            "and session tokens would leak.",
            id="dj_rest_jwt.E005",
        ))
    if conf.COOKIE in conf.get("TRANSPORTS") and "django.middleware.csrf.CsrfViewMiddleware" not in middleware:
        errors.append(Error(
            "Cookie transport needs django.middleware.csrf.CsrfViewMiddleware to issue CSRF cookies.",
            id="dj_rest_jwt.E006",
        ))
    if "allauth.account.middleware.AccountMiddleware" not in middleware:
        errors.append(Error(
            "allauth.account.middleware.AccountMiddleware is not in MIDDLEWARE.",
            id="dj_rest_jwt.E007",
        ))
    return errors


@register(Tags.security)
def check_accounts(app_configs, **kwargs):
    errors = []
    if _setting("ACCOUNT_RATE_LIMITS", None) is False:
        errors.append(Warning(
            "ACCOUNT_RATE_LIMITS = False disables login, signup and password-reset rate limiting.",
            id="dj_rest_jwt.W007",
        ))
    if _setting("HEADLESS_ONLY", False):
        frontend = _setting("HEADLESS_FRONTEND_URLS", {}) or {}
        missing = [name for name in required_frontend_urls() if name not in frontend]
        if missing:
            errors.append(Error(
                f"HEADLESS_FRONTEND_URLS is missing {', '.join(missing)}; emails that link to these "
                "pages will crash.",
                hint="Point each at the route in your frontend that handles it.",
                id="dj_rest_jwt.E008",
            ))
    hashers = _setting("PASSWORD_HASHERS", [])
    if hashers and not any(name in hashers[0] for name in ("Argon2", "Scrypt")):
        errors.append(Warning(
            "The first PASSWORD_HASHERS entry is not Argon2 or scrypt.",
            hint='Put "django.contrib.auth.hashers.Argon2PasswordHasher" first (pip install argon2-cffi).',
            id="dj_rest_jwt.W008",
        ))
    if _setting("SOCIALACCOUNT_EMAIL_AUTHENTICATION", False):
        errors.append(Warning(
            "SOCIALACCOUNT_EMAIL_AUTHENTICATION lets a social provider sign in to an existing local "
            "account by matching email; one provider that doesn't verify emails is an account takeover.",
            id="dj_rest_jwt.W009",
        ))
    return errors


@register(Tags.security, Tags.urls)
def check_admin_login(app_configs, **kwargs):
    from django.apps import apps

    if not conf.get("ADMIN_LOGIN") or not apps.is_installed("django.contrib.admin"):
        return []
    try:
        reverse("account_login")
        reverse("mfa_authenticate")
    except NoReverseMatch:
        return [Error(
            "The admin login is routed through allauth, but dj_rest_jwt.admin_login is not mounted.",
            hint='Add path("admin/", include("dj_rest_jwt.admin_login")) before admin.site.urls, '
                 'or set DJ_REST_JWT["ADMIN_LOGIN"] = False.',
            id="dj_rest_jwt.E009",
        )]
    return []


@register(Tags.security, deploy=True)
def check_deploy(app_configs, **kwargs):
    errors = []
    if conf.COOKIE in conf.get("TRANSPORTS") and not conf.get("COOKIE_SECURE"):
        errors.append(Warning(
            'DJ_REST_JWT["COOKIE_SECURE"] is False; auth cookies would be sent over plain HTTP.',
            id="dj_rest_jwt.W010",
        ))
    backend = _setting("CACHES", {}).get("default", {}).get("BACKEND", "")
    if backend.endswith(("LocMemCache", "DummyCache")):
        errors.append(Warning(
            "The default cache is per-process (or a no-op), so rate limits and cached sessions are "
            "not shared between workers.",
            hint="Use Redis or Memcached.",
            id="dj_rest_jwt.W011",
        ))
    return errors
