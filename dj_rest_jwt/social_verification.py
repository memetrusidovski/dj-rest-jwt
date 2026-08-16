"""
Audience validation for provider access tokens.

A raw OAuth2 `access_token` posted by a client carries no proof of *which*
application it was issued to. Without a check, anyone holding a token minted for
any other OAuth client - their own app, a compromised third party - can present
it here and be logged in as its owner. The `code` and `id_token` flows don't
have this problem: an authorization code is redeemed with our own client
secret, and an id_token is signed and carries an `aud` claim that allauth
verifies against the configured client id.

So: bare access tokens are only accepted when a verifier for that provider can
confirm the token belongs to this application. Providers without a verifier are
rejected by default; register your own via
`REST_AUTH['SOCIAL_LOGIN_ACCESS_TOKEN_VERIFIERS']` if you have a way to check.

A verifier takes `(app, access_token)` and returns True when the token is bound
to `app`, False when it demonstrably is not. It should raise
`AccessTokenVerificationUnavailable` when it cannot reach the provider, so a
network blip surfaces as an error instead of silently authenticating someone.
"""
import logging

import requests
from django.utils.module_loading import import_string

from .app_settings import api_settings

logger = logging.getLogger('dj_rest_jwt.social')

GOOGLE_TOKENINFO_URL = 'https://oauth2.googleapis.com/tokeninfo'
GITHUB_API_URL = 'https://api.github.com'
FACEBOOK_GRAPH_URL = 'https://graph.facebook.com'

VERIFY_TIMEOUT = 10


class AccessTokenVerificationUnavailable(Exception):
    """The provider could not be reached to check the token's audience."""


def _client_ids(app):
    """
    allauth allows a comma-separated list of client ids (Apple uses this for
    the web + native app pair), so an audience may legitimately be any of them.
    """
    return {cid.strip() for cid in (app.client_id or '').split(',') if cid.strip()}


def verify_google_access_token(app, access_token):
    """
    Google's tokeninfo endpoint echoes back the client id the token was issued
    to, as `aud` (`azp` for tokens obtained by a browser-side client).
    """
    try:
        response = requests.get(
            GOOGLE_TOKENINFO_URL,
            params={'access_token': access_token},
            timeout=VERIFY_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise AccessTokenVerificationUnavailable(str(exc)) from exc

    if response.status_code != 200:
        # 400 is Google's answer for an invalid/expired token.
        return False
    try:
        data = response.json()
    except ValueError as exc:
        raise AccessTokenVerificationUnavailable('malformed tokeninfo response') from exc

    audiences = {data.get('aud'), data.get('azp')} - {None, ''}
    return bool(_client_ids(app) & audiences)


def verify_github_access_token(app, access_token):
    """
    GitHub exposes a token introspection endpoint that is authenticated with the
    OAuth app's own credentials, so a 200 means "this token was issued to you".
    """
    client_ids = _client_ids(app)
    if not client_ids:
        return False
    client_id = sorted(client_ids)[0]

    try:
        response = requests.post(
            f'{GITHUB_API_URL}/applications/{client_id}/token',
            json={'access_token': access_token},
            auth=(client_id, app.secret),
            headers={'Accept': 'application/vnd.github+json'},
            timeout=VERIFY_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise AccessTokenVerificationUnavailable(str(exc)) from exc

    if response.status_code == 200:
        return True
    if response.status_code in (404, 422):
        # 404: token isn't ours / doesn't exist. 422: malformed token.
        return False
    raise AccessTokenVerificationUnavailable(
        f'unexpected status {response.status_code} from GitHub token introspection'
    )


def verify_facebook_access_token(app, access_token):
    """
    Facebook's debug_token endpoint, called with an app access token, reports
    which app the inspected token was issued to.
    """
    client_ids = _client_ids(app)
    if not client_ids:
        return False
    client_id = sorted(client_ids)[0]

    try:
        response = requests.get(
            f'{FACEBOOK_GRAPH_URL}/debug_token',
            params={
                'input_token': access_token,
                'access_token': f'{client_id}|{app.secret}',
            },
            timeout=VERIFY_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise AccessTokenVerificationUnavailable(str(exc)) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise AccessTokenVerificationUnavailable('malformed debug_token response') from exc

    data = payload.get('data') or {}
    if not response.ok and not data:
        # An invalid input token still comes back 200 with an error inside
        # `data`; a non-200 with no data means we couldn't ask the question.
        raise AccessTokenVerificationUnavailable(
            f'unexpected status {response.status_code} from Facebook debug_token'
        )

    if not data.get('is_valid', False):
        return False
    return str(data.get('app_id')) in client_ids


def get_verifier(provider_id):
    """Resolve the configured verifier for a provider, or None."""
    verifiers = api_settings.SOCIAL_LOGIN_ACCESS_TOKEN_VERIFIERS or {}
    verifier = verifiers.get(provider_id)
    if verifier is None:
        return None
    if isinstance(verifier, str):
        verifier = import_string(verifier)
    return verifier
