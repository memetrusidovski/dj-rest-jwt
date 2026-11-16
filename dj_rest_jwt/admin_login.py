"""
Django admin sign-in through allauth.

The stock admin login checks a password and nothing else: no rate limits, no
MFA. The admin is the most privileged surface in a project, so it gets the
strongest login. It still runs on a Django session (it is server-rendered),
but that session only exists after allauth's full login flow, MFA included.

``dj_rest_jwt`` wraps ``admin.site.login`` on startup (``ADMIN_LOGIN`` in
``DJ_REST_JWT``, on by default). Mount these views ahead of the admin::

    urlpatterns = [
        path("admin/", include("dj_rest_jwt.admin_login")),
        path("admin/", admin.site.urls),
    ]

and set ``LOGIN_URL = "account_login"`` (the preset does).
"""
from allauth.account import views as account_views
from allauth.account.decorators import secure_admin_login
from allauth.mfa.base import views as mfa_views
from django.urls import path

TEMPLATE = "dj_rest_jwt/admin_login.html"


class AdminLoginView(account_views.LoginView):
    # allauth's stock template links to signup/passkey pages that an API-only
    # project doesn't mount; this one is admin-styled and self-contained.
    template_name = TEMPLATE

    def get_context_data(self, **kwargs):
        # Skip allauth's "entrance" context, which reverses those same pages.
        return super(account_views.LoginView, self).get_context_data(**kwargs)


class AdminMFAView(mfa_views.AuthenticateView):
    template_name = TEMPLATE

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "is_mfa": True}


def secure_admin_site(site=None):
    from django.contrib import admin

    site = site or admin.site
    if not getattr(site.login, "_dj_rest_jwt_secured", False):
        site.login = secure_admin_login(site.login)
        site.login._dj_rest_jwt_secured = True


# allauth looks these views up by these exact names.
urlpatterns = [
    path("auth/login/", AdminLoginView.as_view(), name="account_login"),
    path("auth/login/mfa/", AdminMFAView.as_view(), name="mfa_authenticate"),
    path("auth/logout/", account_views.logout, name="account_logout"),
]
