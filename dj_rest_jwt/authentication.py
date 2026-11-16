from allauth.headless.contrib.rest_framework.authentication import JWTTokenAuthentication
from rest_framework import exceptions
from rest_framework.authentication import get_authorization_header

from .transport import csrf_failure_reason, get_access_cookie


class JWTAuthentication(JWTTokenAuthentication):
    """
    DRF authentication for the project's own API.

    ``Authorization: Bearer`` (native apps) or the httpOnly access cookie
    (browser SPAs). Cookie-authenticated unsafe requests must pass CSRF,
    because the browser attaches cookies on its own.
    """

    def authenticate(self, request):
        if get_authorization_header(request):
            return super().authenticate(request)
        raw = get_access_cookie(request._request)
        if raw is None:
            return None
        reason = csrf_failure_reason(request._request)
        if reason:
            raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")
        return self.authenticate_credentials(raw)

    def authenticate_header(self, request):
        # Makes DRF answer 401 (not 403) when credentials are missing or
        # expired, which is the client's signal to refresh and retry.
        return 'Bearer realm="api"'
