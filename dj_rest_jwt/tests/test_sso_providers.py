import json

import responses
from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.providers.google.views import IDENTITY_URL
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import TestCase, override_settings

from .mixins import TestsMixin

try:
    from django.urls import reverse
except ImportError:
    from django.core.urlresolvers import reverse  # noqa

User = get_user_model()

GITHUB_USER_API_URL = GitHubOAuth2Adapter.profile_url


@override_settings(ROOT_URLCONF='tests.urls')
class ReadyMadeSSOProviderTests(TestsMixin, TestCase):
    """
    dj_rest_jwt ships concrete Google/GitHub/Microsoft login+connect views
    out of the box (dj_rest_jwt/registration/social_views.py) - no need for a
    project to write its own adapter_class subclass. These tests confirm the
    endpoints are actually wired up and functional, using the same
    responses-mocked-provider-API approach as the Facebook/Twitter tests.
    """

    def setUp(self):
        self.init()
        site = Site.objects.get_current()

        for provider, client_id, secret in [
            ('google', 'google-client-id', 'google-secret'),
            ('github', 'github-client-id', 'github-secret'),
            ('microsoft', 'microsoft-client-id', 'microsoft-secret'),
        ]:
            app = SocialApp.objects.create(
                provider=provider, name=provider.title(),
                client_id=client_id, secret=secret,
            )
            app.sites.add(site)

        self.google_login_url = reverse('rest_google_login')
        self.github_login_url = reverse('rest_github_login')

    @responses.activate
    def test_google_login_creates_user(self):
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
