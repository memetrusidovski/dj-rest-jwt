"""
Settings, read from the ``DJ_REST_JWT`` dict.

Everything allauth already has a setting for (token lifetimes, rate limits,
MFA, ...) stays an allauth setting; see ``dj_rest_jwt.defaults``.
"""
from django.conf import settings

COOKIE = "cookie"
HEADER = "header"

DEFAULTS = {
    # Which token transports clients may use. Browser SPAs get "cookie"
    # (httpOnly cookies, never readable by script); native apps opt into
    # "header" (tokens in the JSON body, sent back as Authorization: Bearer)
    # with the X-Auth-Transport request header. Drop one to forbid it.
    "TRANSPORTS": (COOKIE, HEADER),
    # Used when a request does not ask for a transport.
    "DEFAULT_TRANSPORT": COOKIE,
    "ACCESS_COOKIE_NAME": "access_token",
    "REFRESH_COOKIE_NAME": "refresh_token",
    "COOKIE_SECURE": True,
    "COOKIE_SAMESITE": "Lax",
    "COOKIE_DOMAIN": None,
    # The refresh cookie is only sent to the refresh endpoint. Derived from
    # where the URLs are mounted when None.
    "REFRESH_COOKIE_PATH": None,
    # Two tabs refreshing at the same moment both present the same refresh
    # token; the loser must not be treated as a thief. Reuse inside this
    # window answers 409 token_rotated (client retries with the new tokens);
    # reuse after it ends the whole session.
    "REFRESH_REUSE_GRACE_SECONDS": 10,
    # Route Django admin sign-in through allauth (rate limits + MFA). Needs
    # dj_rest_jwt.admin_login mounted; see that module.
    "ADMIN_LOGIN": True,
    # Signup anti-spam (see dj_rest_jwt.signup).
    "HONEYPOT_FIELD_NAME": "website",
    "CAPTCHA_BACKEND": None,            # None | "turnstile" | "recaptcha_v3" | "hcaptcha"
    "CAPTCHA_SECRET_KEY": None,
    "CAPTCHA_RECAPTCHA_V3_MIN_SCORE": 0.5,
}


def get(name):
    user = getattr(settings, "DJ_REST_JWT", {}) or {}
    return user.get(name, DEFAULTS[name])
