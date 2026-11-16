# Protecting your API

The preset makes every DRF view require a valid access token:

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["dj_rest_jwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}
```

`JWTAuthentication` accepts `Authorization: Bearer <access>` (header transport) or the access
cookie (cookie transport, with CSRF required on unsafe methods). Missing or expired credentials
answer `401` with `WWW-Authenticate: Bearer`, which is the JS client's cue to refresh and retry.

Open up individual views as usual:

```python
from rest_framework.permissions import AllowAny

class PublicCatalogView(APIView):
    permission_classes = [AllowAny]
```

`request.user` is the signed-in user, and revocation is immediate (see
[staying signed in](sessions.md)).

## Plain Django views

Write API endpoints as DRF views (`APIView` or `@api_view`) so they get this authentication.
Session authentication is deliberately not enabled for API clients.

## Django Ninja

allauth ships `allauth.headless.contrib.ninja.security.JWTTokenAuth` for Bearer tokens. Cookie
transport for Ninja is not built in yet.
