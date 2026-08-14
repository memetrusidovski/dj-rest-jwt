from django.conf import settings
from django.urls import path, re_path
from django.views.generic import TemplateView

from .views import RegisterView, VerifyEmailView, ResendEmailVerificationView


urlpatterns = [
    path('', RegisterView.as_view(), name='rest_register'),
    re_path(r'verify-email/?$', VerifyEmailView.as_view(), name='rest_verify_email'),
    re_path(r'resend-email/?$', ResendEmailVerificationView.as_view(), name="rest_resend_email"),

    # This url is used by django-allauth and empty TemplateView is
    # defined just to allow reverse() call inside app, for example when email
    # with verification link is being sent, then it's required to render email
    # content.

    # account_confirm_email - You should override this view to handle it in
    # your API client somehow and then, send post to /verify-email/ endpoint
    # with proper key.
    # If you don't want to use API on that step, then just use ConfirmEmailView
    # view from:
    # django-allauth https://github.com/pennersr/django-allauth/blob/master/allauth/account/views.py
    re_path(
        r'^account-confirm-email/(?P<key>[-:\w]+)/$', TemplateView.as_view(),
        name='account_confirm_email',
    ),
    re_path(
        r'account-email-verification-sent/?$', TemplateView.as_view(),
        name='account_email_verification_sent',
    ),
]

if 'allauth.socialaccount' in settings.INSTALLED_APPS:
    from .social_views import (
        GitHubConnect, GitHubLogin, GoogleConnect, GoogleLogin,
        MicrosoftConnect, MicrosoftLogin,
    )

    # Named rest_<provider>_* (not e.g. "google_login") to avoid colliding with
    # allauth's own browser-redirect OAuth views, which register url names like
    # "google_login" for /accounts/google/login/ when allauth.urls is included.
    urlpatterns += [
        re_path(r'google/login/?$', GoogleLogin.as_view(), name='rest_google_login'),
        re_path(r'google/connect/?$', GoogleConnect.as_view(), name='rest_google_connect'),
        re_path(r'github/login/?$', GitHubLogin.as_view(), name='rest_github_login'),
        re_path(r'github/connect/?$', GitHubConnect.as_view(), name='rest_github_connect'),
        re_path(r'microsoft/login/?$', MicrosoftLogin.as_view(), name='rest_microsoft_login'),
        re_path(r'microsoft/connect/?$', MicrosoftConnect.as_view(), name='rest_microsoft_connect'),
    ]
