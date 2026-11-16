"""
How tokens travel between server and client.

Two transports, chosen per request:

``cookie`` (browser SPAs, the default)
    Tokens are set as httpOnly cookies and never appear in a response body.
    The access cookie authenticates requests; unsafe methods must pass CSRF.

``header`` (native apps; the client sends ``X-Auth-Transport: header``)
    Tokens are returned in the JSON body and sent back as
    ``Authorization: Bearer``. Cookies are neither set nor honoured.

The two never mix: a header-mode request is not authenticated by a cookie and
cannot read cookie-held tokens, so asking for header mode from a browser gets
an attacker nothing the cookies were protecting.
"""
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.urls import NoReverseMatch, reverse

from . import conf

REQUEST_HEADER = "HTTP_X_AUTH_TRANSPORT"


def allowed_transports():
    return tuple(conf.get("TRANSPORTS"))


def get_transport(request):
    allowed = allowed_transports()
    asked = (request.META.get(REQUEST_HEADER) or "").strip().lower()
    if asked in allowed:
        return asked
    default = conf.get("DEFAULT_TRANSPORT")
    return default if default in allowed else allowed[0]


def uses_cookies(request):
    return get_transport(request) == conf.COOKIE


def refresh_cookie_path():
    path = conf.get("REFRESH_COOKIE_PATH")
    if path:
        return path
    try:
        return reverse("dj_rest_jwt:token_refresh")
    except NoReverseMatch:
        return "/"


def _cookie_kwargs():
    return {
        "secure": conf.get("COOKIE_SECURE"),
        "httponly": True,
        "samesite": conf.get("COOKIE_SAMESITE"),
        "domain": conf.get("COOKIE_DOMAIN"),
    }


def set_token_cookies(request, response, access_token, refresh_token=None):
    from allauth.headless import app_settings as headless_settings

    response.set_cookie(
        conf.get("ACCESS_COOKIE_NAME"),
        access_token,
        max_age=headless_settings.JWT_ACCESS_TOKEN_EXPIRES_IN,
        path="/",
        **_cookie_kwargs(),
    )
    if refresh_token:
        response.set_cookie(
            conf.get("REFRESH_COOKIE_NAME"),
            refresh_token,
            max_age=headless_settings.JWT_REFRESH_TOKEN_EXPIRES_IN,
            path=refresh_cookie_path(),
            **_cookie_kwargs(),
        )
    # Cookie auth needs CSRF on unsafe methods; make sure the SPA has a
    # csrftoken cookie to echo back in X-CSRFToken.
    get_token(request)


def clear_token_cookies(response):
    kwargs = {"samesite": conf.get("COOKIE_SAMESITE"), "domain": conf.get("COOKIE_DOMAIN")}
    response.delete_cookie(conf.get("ACCESS_COOKIE_NAME"), path="/", **kwargs)
    response.delete_cookie(conf.get("REFRESH_COOKIE_NAME"), path=refresh_cookie_path(), **kwargs)


def get_access_cookie(request):
    """The access token from the cookie, or None if this request may not use one."""
    if not uses_cookies(request) or "HTTP_AUTHORIZATION" in request.META:
        # An Authorization header that failed validation must not be rescued
        # by a cookie.
        return None
    return request.COOKIES.get(conf.get("ACCESS_COOKIE_NAME")) or None


def csrf_failure_reason(request):
    """None if the request passes Django's CSRF check, else the reason."""
    check = CsrfViewMiddleware(lambda req: None)
    check.process_request(request)
    return check.process_view(request, None, (), {})
