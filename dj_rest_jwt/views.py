import json

from allauth.headless import app_settings as headless_settings
from allauth.headless.account.views import ChangePasswordView as AllauthChangePasswordView
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from . import conf
from .transport import clear_token_cookies, csrf_failure_reason, set_token_cookies, uses_cookies


def _error(status, code="invalid_token"):
    return JsonResponse({"status": status, "errors": [{"code": code}]}, status=status)


@method_decorator(csrf_exempt, name="dispatch")
class TokenRefreshView(View):
    """
    Replaces allauth's ``tokens/refresh`` so the refresh token can live in an
    httpOnly cookie. Same request/response shape as allauth's.

    cookie transport: the refresh token comes from the cookie (CSRF-checked)
    and the new pair goes back as cookies. header transport: body in, body
    out, cookies ignored.

    409 ``token_rotated``: this refresh token was just rotated by a parallel
    refresh. Not a failure; retry with the current tokens.
    """

    def post(self, request):
        cookies = uses_cookies(request)
        if cookies:
            token = request.COOKIES.get(conf.get("REFRESH_COOKIE_NAME"))
            if not token:
                return _error(401)
            if csrf_failure_reason(request):
                return _error(403, "csrf_failed")
        else:
            try:
                data = json.loads(request.body or b"{}")
            except ValueError:
                data = {}
            token = data.get("refresh_token") if isinstance(data, dict) else None
            if not token:
                return _error(400, "required")

        strategy = headless_settings.TOKEN_STRATEGY
        result = strategy.refresh_token(token)
        if result is None and getattr(strategy, "recently_rotated", None) and strategy.recently_rotated(token):
            # Lost a race with another tab/request that refreshed first. Keep
            # the cookies (they already hold the winner's tokens); the client
            # retries with those.
            return _error(409, "token_rotated")
        if result is None:
            response = _error(401)
            if cookies:
                clear_token_cookies(response)
            return response

        access, refresh = result
        if cookies:
            response = JsonResponse({"status": 200, "data": {}})
            set_token_cookies(request, response, access, refresh)
            return response
        payload = {"access_token": access}
        if refresh != token:
            payload["refresh_token"] = refresh
        return JsonResponse({"status": 200, "data": payload})


class ChangePasswordView(AllauthChangePasswordView):
    """
    allauth's password change, but the device that made the change stays
    signed in.

    Changing the password rotates the session key (Django's
    update_session_auth_hash), which orphans the JWTs that pointed at the old
    key. Every *other* device should be cut off by that; this one should not.
    So when the key rotates, mint a fresh pair for the new session and hand
    it out the same way a login does (the transport middleware delivers it).
    """

    def post(self, request, *args, **kwargs):
        before = request.session.session_key
        response = super().post(request, *args, **kwargs)
        if response.status_code != 200 or request.session.session_key == before:
            return response
        tokens = headless_settings.TOKEN_STRATEGY.create_access_token_payload(request)
        if not tokens:
            return response
        body = json.loads(response.content)
        body.setdefault("meta", {}).update(tokens)
        response.content = json.dumps(body)
        response["Content-Length"] = str(len(response.content))
        return response
