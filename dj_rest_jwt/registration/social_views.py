"""
Ready-made social login/connect views for the three most commonly requested
OAuth2 providers, so a project doesn't have to write its own adapter_class
subclass just to use Google/GitHub/Microsoft sign-in.

Each accepts either `access_token`/`id_token` (client obtained the token
itself, e.g. via Google Identity Services or MSAL) or `code` (server-side
authorization code exchange) - see SocialLoginSerializer.

Any other allauth provider (Apple, Discord, GitLab, ...) works the same way -
just subclass SocialLoginView/SocialConnectView with that provider's
adapter_class, following this file as a template.
"""
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.microsoft.views import (
    MicrosoftGraphOAuth2Adapter,
)
from allauth.socialaccount.providers.oauth2.client import OAuth2Client

from dj_rest_jwt.registration.views import SocialConnectView, SocialLoginView


class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client


class GoogleConnect(SocialConnectView):
    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client


class GitHubLogin(SocialLoginView):
    adapter_class = GitHubOAuth2Adapter
    client_class = OAuth2Client


class GitHubConnect(SocialConnectView):
    adapter_class = GitHubOAuth2Adapter
    client_class = OAuth2Client


class MicrosoftLogin(SocialLoginView):
    adapter_class = MicrosoftGraphOAuth2Adapter
    client_class = OAuth2Client


class MicrosoftConnect(SocialConnectView):
    adapter_class = MicrosoftGraphOAuth2Adapter
    client_class = OAuth2Client
