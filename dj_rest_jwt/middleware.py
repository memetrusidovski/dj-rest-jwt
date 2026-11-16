import json

from .transport import clear_token_cookies, set_token_cookies, uses_cookies


class TokenTransportMiddleware:
    """
    Delivers tokens minted by allauth's headless views in the right transport.

    allauth reports a finished login (password, MFA step, passkey, social
    token, signup, ...) by putting ``access_token``/``refresh_token`` in the
    response's ``meta``. Hooking that one place covers every login path.

    - cookie transport: tokens move into httpOnly cookies, out of the body.
    - header transport: tokens stay in the body.
    - both: ``session_token`` is dropped once JWTs are issued. It is the raw
      session key, a credential that would outlive every access token.
    - ending the current session clears the cookies.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        match = getattr(request, "resolver_match", None)
        if match is None or "headless" not in match.namespaces:
            return response
        cookies = uses_cookies(request)

        if match.url_name == "current_session" and request.method == "DELETE":
            if cookies:
                clear_token_cookies(response)
            return response

        if "application/json" not in response.get("Content-Type", ""):
            return response
        try:
            body = json.loads(response.content)
        except ValueError:
            return response
        meta = body.get("meta") if isinstance(body, dict) else None
        if not isinstance(meta, dict) or "access_token" not in meta:
            return response

        meta.pop("session_token", None)
        if cookies:
            set_token_cookies(request, response, meta.pop("access_token"), meta.pop("refresh_token", None))
        response.content = json.dumps(body)
        response["Content-Length"] = str(len(response.content))
        return response
