import json
from unittest.mock import patch

import responses
from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.google.views import IDENTITY_URL
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import TestCase, override_settings

from dj_rest_jwt.social_verification import (
    GITHUB_API_URL, GOOGLE_TOKENINFO_URL,
)

from .mixins import TestsMixin
from .utils import override_api_settings

try:
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse  # noqa

User = get_user_model()

GITHUB_USER_API_URL = GitHubOAuth2Adapter.profile_url


@override_settings(ROOT_URLCONF='tests.urls')
class ReadyMadeSSOProviderTests(TestsMixin, TestCase):
    """
    dj_rest_jwt ships concrete Google/GitHub/Microsoft/Apple login+connect
    views out of the box (dj_rest_jwt/registration/social_views.py) - no need
    for a project to write its own adapter_class subclass. These tests confirm
    the endpoints are actually wired up and functional, using the same
    responses-mocked-provider-API approach as the Facebook/Twitter tests.
    """

    def setUp(self):
        self.init()
        site = Site.objects.get_current()

        for provider, client_id, secret in [
            ('google', 'google-client-id', 'google-secret'),
            ('github', 'github-client-id', 'github-secret'),
            ('microsoft', 'microsoft-client-id', 'microsoft-secret'),
            ('apple', 'apple-client-id', 'apple-key-id'),
        ]:
            app = SocialApp.objects.create(
                provider=provider, name=provider.title(),
                client_id=client_id, secret=secret,
            )
            app.sites.add(site)

        self.google_login_url = reverse('rest_google_login')
        self.github_login_url = reverse('rest_github_login')
        self.microsoft_login_url = reverse('rest_microsoft_login')
        self.apple_login_url = reverse('rest_apple_login')

    @staticmethod
    def mock_google_tokeninfo(aud='google-client-id', status=200):
        responses.add(
            responses.GET,
            GOOGLE_TOKENINFO_URL,
            body=json.dumps({'aud': aud, 'azp': aud}),
            status=status,
            content_type='application/json',
        )

    @staticmethod
    def mock_github_introspection(status=200):
        responses.add(
            responses.POST,
            GITHUB_API_URL + '/applications/github-client-id/token',
            body=json.dumps({'app': {'client_id': 'github-client-id'}}),
            status=status,
            content_type='application/json',
        )

    @responses.activate
    def test_google_login_creates_user(self):
        self.mock_google_tokeninfo()
        responses.add(
            responses.GET,
            IDENTITY_URL,
            body=json.dumps({
                'id': '1234567890',
                'email': 'googleuser@example.com',
                'verified_email': True,
                'name': 'Google User',
            }),
            status=200,
            content_type='application/json',
        )

        users_count = User.objects.all().count()
        response = self.post(
            self.google_login_url, data={'access_token': 'fake-google-token'}, status_code=200,
        )
        self.assertIn('key', response.json)
        self.assertEqual(User.objects.all().count(), users_count + 1)

    @responses.activate
    def test_github_login_creates_user(self):
        self.mock_github_introspection()
        responses.add(
            responses.GET,
            GITHUB_USER_API_URL,
            body=json.dumps({
                'id': 987654321,
                'login': 'githubuser',
                'name': 'GitHub User',
                'email': 'githubuser@example.com',
            }),
            status=200,
            content_type='application/json',
        )
        responses.add(
            responses.GET,
            'https://api.github.com/user/emails',
            body=json.dumps([{'email': 'githubuser@example.com', 'primary': True, 'verified': True}]),
            status=200,
            content_type='application/json',
        )

        users_count = User.objects.all().count()
        response = self.post(
            self.github_login_url, data={'access_token': 'fake-github-token'}, status_code=200,
        )
        self.assertIn('key', response.json)
        self.assertEqual(User.objects.all().count(), users_count + 1)

    @responses.activate
    def test_microsoft_rejects_bare_access_token(self):
        """
        Microsoft Graph tokens carry no audience we can check against our own
        client id, so a raw access_token must not be accepted - the `code` flow
        is the supported path.
        """
        response = self.post(
            self.microsoft_login_url,
            data={'access_token': 'fake-microsoft-token'},
            status_code=400,
        )
        self.assertIn('does not support signing in with a bare', str(response.json))

    @responses.activate
    def test_google_rejects_token_issued_to_another_app(self):
        """The token-substitution case: a valid Google token, wrong audience."""
        self.mock_google_tokeninfo(aud='some-other-app.apps.googleusercontent.com')
        responses.add(
            responses.GET,
            IDENTITY_URL,
            body=json.dumps({'id': '1', 'email': 'victim@example.com'}),
            status=200,
            content_type='application/json',
        )

        users_count = User.objects.all().count()
        response = self.post(
            self.google_login_url, data={'access_token': 'token-for-another-app'}, status_code=400,
        )
        self.assertIn('not issued to this application', str(response.json))
        self.assertEqual(User.objects.all().count(), users_count)

    @responses.activate
    def test_github_rejects_token_issued_to_another_app(self):
        # GitHub answers 404 when the token wasn't minted by the app doing the asking.
        self.mock_github_introspection(status=404)
        responses.add(
            responses.GET,
            GITHUB_USER_API_URL,
            body=json.dumps({'id': 1, 'login': 'victim'}),
            status=200,
            content_type='application/json',
        )

        users_count = User.objects.all().count()
        response = self.post(
            self.github_login_url, data={'access_token': 'token-for-another-app'}, status_code=400,
        )
        self.assertIn('not issued to this application', str(response.json))
        self.assertEqual(User.objects.all().count(), users_count)

    @responses.activate
    def test_verification_can_be_disabled_for_legacy_deployments(self):
        with override_api_settings(SOCIAL_LOGIN_VERIFY_ACCESS_TOKEN=False):
            responses.add(
                responses.GET,
                IDENTITY_URL,
                body=json.dumps({
                    'id': '555', 'email': 'legacy@example.com', 'verified_email': True,
                }),
                status=200,
                content_type='application/json',
            )
            response = self.post(
                self.google_login_url, data={'access_token': 'unverified'}, status_code=200,
            )
        self.assertIn('key', response.json)

    def test_apple_login_creates_user(self):
        """
        Apple only ever authenticates through a signed id_token whose audience
        allauth verifies against the configured client id, so there's no bare
        access_token path to guard here.
        """
        identity = {
            'sub': 'apple-user-001',
            'email': 'appleuser@example.com',
            'email_verified': 'true',
        }
        users_count = User.objects.all().count()

        with patch(
            'allauth.socialaccount.providers.apple.views.AppleOAuth2Adapter.get_verified_identity_data',
            return_value=identity,
        ):
            response = self.post(
                self.apple_login_url,
                data={'access_token': 'fake-apple-access-token', 'id_token': 'fake-apple-id-token'},
                status_code=200,
            )

        self.assertIn('key', response.json)
        self.assertEqual(User.objects.all().count(), users_count + 1)

    def test_apple_login_rejects_unverifiable_id_token(self):
        from allauth.socialaccount.providers.oauth2.client import OAuth2Error

        with patch(
            'allauth.socialaccount.providers.apple.views.AppleOAuth2Adapter.get_verified_identity_data',
            side_effect=OAuth2Error('bad signature'),
        ):
            self.post(
                self.apple_login_url,
                data={'access_token': 'fake', 'id_token': 'forged'},
                status_code=400,
            )

    def test_apple_login_requires_an_id_token(self):
        """Without one there is nothing signed to check, so it must not proceed."""
        self.post(
            self.apple_login_url,
            data={'access_token': 'fake-apple-access-token'},
            status_code=400,
        )
