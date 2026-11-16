"""
allauth's JWT token strategy, extended with:

1. The access cookie as a credential, so allauth's own endpoints (password
   change, MFA management, sessions, ...) work for a browser SPA that never
   sees its tokens. Cookie-authenticated requests must pass CSRF.
2. Refresh-token reuse detection. allauth already refuses a rotated refresh
   token; reuse is additionally treated as theft and ends the session, which
   also cuts off whoever holds the newer token.

Set ``HEADLESS_TOKEN_STRATEGY = "dj_rest_jwt.strategy.JWTTokenStrategy"``.

Note: this uses ``allauth.headless.tokens.strategies.jwt.internal``, which is
not public API. The supported allauth range is pinned in pyproject.toml and the test
suite exercises every function used here.
"""
import logging
import time

from allauth.core import context
from allauth.headless import app_settings as headless_settings
from allauth.headless.tokens.strategies.jwt import JWTTokenStrategy as AllauthJWTTokenStrategy
from allauth.headless.tokens.strategies.jwt import internal

from . import conf
from .signals import refresh_token_reused
from .transport import csrf_failure_reason, get_access_cookie

logger = logging.getLogger("dj_rest_jwt.security")

ROTATED_KEY = "dj_rest_jwt_rotated"


def end_session(session):
    """End a session everywhere: the usersessions row and the session store."""
    from django.apps import apps

    if apps.is_installed("allauth.usersessions"):
        from allauth.usersessions.models import UserSession

        row = UserSession.objects.filter(session_key=session.session_key).first()
        if row is not None:
            row.end()
            return
    session.delete()


class JWTTokenStrategy(AllauthJWTTokenStrategy):

    def get_session_token(self, request):
        ret = super().get_session_token(request)
        if ret:
            return ret
        raw = get_access_cookie(request)
        if raw is None or csrf_failure_reason(request):
            return None
        result = internal.validate_access_token(raw)
        if result is None:
            return None
        return internal.session_key_from_sid(result.payload["sid"])

    def recently_rotated(self, refresh_token):
        """
        True if this refresh token was rotated within the grace window, i.e.
        another tab or request refreshed first. The client should retry with
        the newer tokens instead of treating the session as over.
        """
        payload = internal.decode_token(refresh_token, "refresh")
        session = internal.get_token_session(payload) if payload else None
        if session is None:
            return False
        rotated_at = session.get(ROTATED_KEY, {}).get(payload["jti"])
        return rotated_at is not None and time.time() - rotated_at <= conf.get("REFRESH_REUSE_GRACE_SECONDS")

    def refresh_token(self, refresh_token):
        payload = internal.decode_token(refresh_token, "refresh")
        result = super().refresh_token(refresh_token)
        if payload is None:
            return result

        session = internal.get_token_session(payload)
        if session is None:
            return result

        now = time.time()
        rotated = dict(session.get(ROTATED_KEY, {}))

        if result is not None:
            if headless_settings.JWT_ROTATE_REFRESH_TOKEN:
                horizon = now - headless_settings.JWT_REFRESH_TOKEN_EXPIRES_IN
                rotated = {jti: ts for jti, ts in rotated.items() if ts > horizon}
                rotated[payload["jti"]] = now
                session[ROTATED_KEY] = rotated
                session.save()
            return result

        rotated_at = rotated.get(payload["jti"])
        if rotated_at is None:
            return None
        if now - rotated_at <= conf.get("REFRESH_REUSE_GRACE_SECONDS"):
            return None

        logger.warning("Refresh token reuse detected; ending session for user %s", payload.get("sub"))
        end_session(session)
        refresh_token_reused.send(
            sender=self.__class__, user_id=payload.get("sub"), request=getattr(context, "request", None),
        )
        return None
