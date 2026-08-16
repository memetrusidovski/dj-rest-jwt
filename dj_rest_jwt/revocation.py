"""
Session/token revocation.

Changing or resetting a password is the standard "I think I've been
compromised" move, so it has to actually evict the attacker. Rotating the
password hash alone doesn't: already-issued JWTs stay valid until they expire,
and DRF auth tokens never expire at all.
"""
import logging

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger('dj_rest_jwt')


def blacklist_enabled():
    return 'rest_framework_simplejwt.token_blacklist' in settings.INSTALLED_APPS


def revoke_user_tokens(user):
    """
    Invalidate every outstanding credential for `user`.

    Blacklists all of the user's simplejwt refresh tokens (requires the
    `token_blacklist` app - without it simplejwt has nowhere to record the
    revocation) and deletes their DRF auth token. Access tokens already in
    flight are not individually revocable and remain valid until they expire,
    which is the usual argument for keeping ACCESS_TOKEN_LIFETIME short.

    Returns the number of refresh tokens blacklisted.
    """
    revoked = 0

    if blacklist_enabled():
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken, OutstandingToken,
        )

        for token in OutstandingToken.objects.filter(user=user):
            _, created = BlacklistedToken.objects.get_or_create(token=token)
            if created:
                revoked += 1
    else:
        logger.warning(
            'Password changed for user %s but refresh tokens could not be revoked: '
            'add "rest_framework_simplejwt.token_blacklist" to INSTALLED_APPS to '
            'enable revocation.',
            getattr(user, 'pk', None),
        )

    # Classic DRF token auth: the key never expires, so it has to go.
    try:
        user.auth_token.delete()
    except (AttributeError, ObjectDoesNotExist):
        pass

    return revoked
