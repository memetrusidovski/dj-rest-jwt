"""
One-time recovery codes.

Codes are shown exactly once, at the moment they're generated, and only their
hashes are kept. That means a stolen access token can't be traded for a list of
permanent MFA bypasses, and a leaked database doesn't hand the attacker working
codes either.

The previous scheme stored a seed and re-derived the codes on demand; seeds
found in existing rows are still accepted at verification time so upgrades don't
lock anybody out, but they can no longer be listed and are replaced the next
time the user regenerates.
"""
import hashlib
import hmac
import secrets

from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes

from dj_rest_jwt.app_settings import api_settings

from .models import Authenticator

CODE_BYTES = 5  # -> 10 hex chars, formatted as xxxxx-xxxxx


def _hash_code(code):
    return hashlib.sha256(force_bytes(code)).hexdigest()


def _generate_code():
    raw = secrets.token_hex(CODE_BYTES)
    return f'{raw[:5]}-{raw[5:]}'


def _normalize(code):
    return str(code).strip().lower()


class RecoveryCodes:
    @staticmethod
    def _legacy_codes(seed, count):
        """Re-derive codes stored under the old seed-based scheme."""
        codes = []
        for i in range(count):
            raw = hmac.new(
                bytes.fromhex(seed),
                msg=str(i).encode(),
                digestmod=hashlib.sha256,
            ).hexdigest()[:8]
            codes.append(f'{raw[:4]}-{raw[4:]}')
        return codes

    @staticmethod
    def activate(user):
        """Generate a fresh set, invalidating any previous one. Returns the plaintext."""
        count = api_settings.MFA_RECOVERY_CODE_COUNT
        codes = [_generate_code() for _ in range(count)]
        Authenticator.objects.update_or_create(
            user=user,
            type=Authenticator.Type.RECOVERY_CODES,
            defaults={'data': {'hashes': [_hash_code(c) for c in codes], 'used': []}},
        )
        return codes

    @staticmethod
    def get_unused_count(user):
        try:
            auth = Authenticator.objects.get(
                user=user, type=Authenticator.Type.RECOVERY_CODES,
            )
        except Authenticator.DoesNotExist:
            return 0

        data = auth.data
        if 'hashes' in data:
            return len(data['hashes']) - len(data.get('used', []))

        # Legacy seed-based row.
        used_mask = data.get('used_mask', 0)
        count = api_settings.MFA_RECOVERY_CODE_COUNT
        return sum(1 for i in range(count) if not used_mask & (1 << i))

    @staticmethod
    def validate_code(user, code):
        normalized = _normalize(code)

        with transaction.atomic():
            try:
                auth = Authenticator.objects.select_for_update().get(
                    user=user, type=Authenticator.Type.RECOVERY_CODES,
                )
            except Authenticator.DoesNotExist:
                return False

            if 'hashes' in auth.data:
                matched = RecoveryCodes._consume_hashed(auth, normalized)
            else:
                matched = RecoveryCodes._consume_legacy(auth, normalized)

            if not matched:
                return False

            auth.last_used_at = timezone.now()
            auth.save(update_fields=['data', 'last_used_at'])
            return True

    @staticmethod
    def _consume_hashed(auth, normalized):
        candidate = _hash_code(normalized)
        used = set(auth.data.get('used', []))

        for index, stored in enumerate(auth.data['hashes']):
            if index in used:
                continue
            if hmac.compare_digest(stored, candidate):
                auth.data['used'] = sorted(used | {index})
                return True
        return False

    @staticmethod
    def _consume_legacy(auth, normalized):
        seed = auth.data.get('seed')
        if not seed:
            return False
        used_mask = auth.data.get('used_mask', 0)
        count = api_settings.MFA_RECOVERY_CODE_COUNT

        for i, candidate in enumerate(RecoveryCodes._legacy_codes(seed, count)):
            if hmac.compare_digest(candidate, normalized) and not used_mask & (1 << i):
                auth.data['used_mask'] = used_mask | (1 << i)
                return True
        return False

    @staticmethod
    def deactivate(user):
        Authenticator.objects.filter(
            user=user, type=Authenticator.Type.RECOVERY_CODES,
        ).delete()
