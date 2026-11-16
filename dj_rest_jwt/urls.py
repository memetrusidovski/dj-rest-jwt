"""
Mount with ``path("api/auth/", include("dj_rest_jwt.urls"))`` to get
``/api/auth/v1/auth/login``, ``/api/auth/v1/tokens/refresh`` and so on.

This is allauth's own app-client URL tree (``build_urlpatterns``) without the
``_allauth/app/`` prefix. allauth binds the client to each view when it is
built, not by path, so nothing depends on the prefix; the ``headless``
namespace is kept so allauth's reverse() calls still resolve. New allauth
endpoints appear here automatically.
"""
from allauth.headless.constants import Client
from allauth.headless.urls import build_urlpatterns
from django.urls import include, path

from .views import ChangePasswordView, TokenRefreshView

app_name = "dj_rest_jwt"

# Our overrides of allauth views. They sit in the same "headless" namespace,
# ahead of allauth's own patterns, so they shadow them and the transport
# middleware treats their responses like any other allauth response.
overrides = [
    path("v1/account/password/change", ChangePasswordView.as_api_view(client=Client.APP), name="change_password"),
]

urlpatterns = [
    path("v1/tokens/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    path("", include((overrides + build_urlpatterns(Client.APP), "headless"), namespace="headless")),
]
