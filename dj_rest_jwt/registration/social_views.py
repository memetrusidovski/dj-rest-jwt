"""
Ready-made social login/connect views for the four most commonly requested
OAuth2 providers, so a project doesn't have to write its own adapter_class
subclass just to use Google/GitHub/Microsoft/Apple sign-in.

Each accepts either an authorization `code` (server-side exchange, always
safe) or a client-obtained `access_token`/`id_token` - see
SocialLoginSerializer. A bare `access_token` is only accepted for providers
that expose a way to prove the token was issued to *this* application:

  Google     `code`, `id_token`, or `access_token` (checked via tokeninfo)
  GitHub     `code`, or `access_token` (checked via token introspection)
  Microsoft  `code` only - Graph tokens carry no verifiable audience
  Apple      `code`, or `access_token` + `id_token` (Apple always signs and
             audience-checks the id_token, so no extra check is needed)

Any other allauth provider (Discord, GitLab, ...) works the same way - just
subclass SocialLoginView/SocialConnectView with that provider's adapter_class,
following this file as a template.
"""
from allauth.socialaccount.providers.apple.client import AppleOAuth2Client
from allauth.socialaccount.providers.apple.views import AppleOAuth2Adapter
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


class AppleLogin(SocialLoginView):
    """
    Sign in with Apple.

    Apple's client secret is a short-lived ES256 JWT rather than a static
    string, which is why this needs AppleOAuth2Client instead of the plain
    OAuth2Client. Configure the SocialApp with:

        client_id        your Services ID (or a comma-separated list, for the
                         web + native app pair)
        secret           the private key's Key ID
        key              your Apple Team ID
        settings         {'certificate_key': '<contents of AuthKey_XXX.p8>'}

    Native iOS clients that already hold Apple's response should post
    `access_token` together with `id_token`; web clients doing the redirect
    dance should post `code`.
    """
    adapter_class = AppleOAuth2Adapter
    client_class = AppleOAuth2Client


class AppleConnect(SocialConnectView):
    adapter_class = AppleOAuth2Adapter
    client_class = AppleOAuth2Client
