"""
Encryption at rest for TOTP secrets.

A TOTP secret is a password equivalent: anyone holding it can mint valid codes
forever. Signing it (which is all `django.core.signing.Signer` does) proves the
value wasn't tampered with but leaves it perfectly readable to anyone who can
read the row - a database backup, a read replica, a SQL injection. So the
secret is encrypted with a key derived from `SECRET_KEY`.

Values are stored with a short prefix identifying the scheme, so a project can
be upgraded in place: legacy signed values are still readable and get rewritten
as encrypted on the next write.
"""
import base64
import hashlib

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.signing import Signer
from django.utils.encoding import force_bytes

from dj_rest_jwt.app_settings import api_settings

# Retained so secrets written before encryption was introduced stay readable.
_LEGACY_SIGNER = Signer(salt='dj-rest-jwt-mfa-totp-secret')

ENCRYPTED_PREFIX = 'enc:'
_KEY_INFO = b'dj-rest-jwt-mfa-totp-secret-key'


class EncryptionUnavailable(ImproperlyConfigured):
    """`cryptography` isn't installed but secret encryption is switched on."""


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:  # pragma: no cover - depends on the install extra
        raise EncryptionUnavailable(
            'MFA_ENCRYPT_SECRETS is on but the `cryptography` package is not '
            'installed. Install it (`pip install dj-rest-jwt[with-mfa]`), or set '
            "REST_AUTH['MFA_ENCRYPT_SECRETS'] = False to store TOTP secrets in "
            'the clear (not recommended).'
        ) from exc

    # HKDF-ish: one round of SHA-256 over SECRET_KEY plus a fixed info string,
    # so this key is domain-separated from every other SECRET_KEY-derived value
    # Django hands out.
    digest = hashlib.sha256(force_bytes(settings.SECRET_KEY) + _KEY_INFO).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(secret):
    """Serialize a TOTP secret for storage."""
    if not api_settings.MFA_ENCRYPT_SECRETS:
        return _LEGACY_SIGNER.sign(secret)
    return ENCRYPTED_PREFIX + _fernet().encrypt(force_bytes(secret)).decode()


def decrypt_secret(stored):
    """
    Read back a stored TOTP secret, transparently handling both schemes.

    Returns None when the value can't be read - a rotated SECRET_KEY, a
    tampered row - so callers fail the code check rather than blowing up.
    """
    if not stored:
        return None

    if stored.startswith(ENCRYPTED_PREFIX):
        from cryptography.fernet import InvalidToken
        try:
            return _fernet().decrypt(force_bytes(stored[len(ENCRYPTED_PREFIX):])).decode()
        except (InvalidToken, EncryptionUnavailable):
            return None

    from django.core.signing import BadSignature
    try:
        return _LEGACY_SIGNER.unsign(stored)
    except BadSignature:
        return None


def needs_rewrite(stored):
    """True when a stored value is in the legacy format and should be upgraded."""
    return bool(stored) and api_settings.MFA_ENCRYPT_SECRETS and not stored.startswith(ENCRYPTED_PREFIX)
