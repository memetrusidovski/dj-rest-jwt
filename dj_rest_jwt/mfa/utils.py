import secrets

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from django.core.signing import BadSignature, TimestampSigner

from dj_rest_jwt.app_settings import api_settings

from .models import Authenticator

UserModel = get_user_model()

_EPHEMERAL_SALT = 'dj-rest-jwt-mfa'
_ACTIVATION_SALT = 'dj-rest-jwt-mfa-activation'
_NONCE_CACHE_PREFIX = 'dj_rest_jwt_mfa_nonce'


class EphemeralTokenConsumed(Exception):
    """The token was valid but has already been redeemed."""


def _nonce_cache_key(nonce):
    return f'{_NONCE_CACHE_PREFIX}:{nonce}'


def create_ephemeral_token(user):
    """
    Issue proof that the first factor succeeded.

    Carries a one-shot nonce alongside the user id: redeeming the token burns
    the nonce, so a token that leaks - out of a log, a proxy, a client-side
    error report - can't be replayed into an unlimited supply of sessions.
    """
    nonce = secrets.token_urlsafe(16)
    cache.set(
        _nonce_cache_key(nonce),
        user.pk,
        api_settings.MFA_EPHEMERAL_TOKEN_TIMEOUT,
    )
    signer = TimestampSigner(salt=_EPHEMERAL_SALT)
    return signer.sign(f'{user.pk}:{nonce}')


def verify_ephemeral_token(token, max_age=None):
    """
    Validate an ephemeral token and return its user, without redeeming it.

    Raises BadSignature/SignatureExpired for a bad token and
    EphemeralTokenConsumed for one that has already been redeemed.
    """
    if max_age is None:
        max_age = api_settings.MFA_EPHEMERAL_TOKEN_TIMEOUT
    signer = TimestampSigner(salt=_EPHEMERAL_SALT)
    value = signer.unsign(token, max_age=max_age)

    user_pk, _, nonce = value.partition(':')

    if nonce and cache.get(_nonce_cache_key(nonce)) is None:
        raise EphemeralTokenConsumed()

    return UserModel.objects.get(pk=user_pk)


def consume_ephemeral_token(token):
    """
    Redeem an ephemeral token so it can't be used again.

    Called only once the second factor has actually checked out: burning the
    token on a wrong code would mean every typo costs a full re-login, and
    would hand anyone who learns the token a way to knock the user back to the
    login screen. Brute force is the rate limiter's job, not this one's.
    """
    try:
        value = TimestampSigner(salt=_EPHEMERAL_SALT).unsign(token)
    except BadSignature:
        return
    _, _, nonce = value.partition(':')
    if nonce:
        cache.delete(_nonce_cache_key(nonce))


def create_totp_activation_token(user, secret):
    payload = {'uid': user.pk, 'secret': secret}
    return signing.dumps(payload, salt=_ACTIVATION_SALT)


def verify_totp_activation_token(token, max_age=None):
    if max_age is None:
        max_age = api_settings.MFA_EPHEMERAL_TOKEN_TIMEOUT
    payload = signing.loads(
        token,
        salt=_ACTIVATION_SALT,
        max_age=max_age,
    )
    return payload


def is_mfa_enabled(user):
    if user is None or not getattr(user, 'pk', None):
        return False
    return Authenticator.objects.filter(
        user=user, type=Authenticator.Type.TOTP,
    ).exists()
