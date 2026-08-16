import time

import pyotp
from django.db import transaction
from django.utils import timezone

from dj_rest_jwt.app_settings import api_settings

from .crypto import decrypt_secret, encrypt_secret, needs_rewrite
from .models import Authenticator


def generate_totp_secret():
    return pyotp.random_base32()


def build_totp_uri(user, secret):
    issuer = api_settings.MFA_TOTP_ISSUER or None
    digits = api_settings.MFA_TOTP_DIGITS
    period = api_settings.MFA_TOTP_PERIOD
    totp = pyotp.TOTP(secret, digits=digits, interval=period)
    name = getattr(user, 'email', None) or str(user)
    return totp.provisioning_uri(name=name, issuer_name=issuer)


def _totp(secret):
    return pyotp.TOTP(
        secret,
        digits=api_settings.MFA_TOTP_DIGITS,
        interval=api_settings.MFA_TOTP_PERIOD,
    )


def validate_totp_code(secret, code):
    """Stateless check - used during enrolment, before there's a row to guard."""
    window = api_settings.MFA_TOTP_VALID_WINDOW
    return _totp(secret).verify(str(code), valid_window=window)


def matching_timestep(secret, code, at=None):
    """
    The time step a code is valid for, or None.

    Returned so the caller can record it and refuse to accept that step - or any
    earlier one - a second time.
    """
    period = api_settings.MFA_TOTP_PERIOD
    window = api_settings.MFA_TOTP_VALID_WINDOW
    now = at if at is not None else time.time()
    current_step = int(now // period)
    totp = _totp(secret)

    for offset in range(-window, window + 1):
        step = current_step + offset
        if totp.verify(str(code), for_time=step * period, valid_window=0):
            return step
    return None


class TOTP:
    @staticmethod
    def activate(user, secret):
        authenticator, _ = Authenticator.objects.update_or_create(
            user=user,
            type=Authenticator.Type.TOTP,
            defaults={'data': {'secret': encrypt_secret(secret)}},
        )
        return authenticator

    @staticmethod
    def deactivate(user):
        Authenticator.objects.filter(
            user=user, type=Authenticator.Type.TOTP,
        ).delete()

    @staticmethod
    def get_secret(user):
        try:
            auth = Authenticator.objects.get(
                user=user, type=Authenticator.Type.TOTP,
            )
        except Authenticator.DoesNotExist:
            return None
        return decrypt_secret(auth.data.get('secret'))

    @staticmethod
    def validate_code(user, code):
        """
        Verify a code and burn its time step.

        The whole accepted window up to and including the matched step is
        consumed, so a code can never be presented twice - not by an attacker
        replaying one they observed, and not by two requests racing each other.
        The row is locked for the duration, which is what makes the second case
        hold under concurrency.
        """
        normalized = str(code).strip()

        with transaction.atomic():
            try:
                auth = Authenticator.objects.select_for_update().get(
                    user=user, type=Authenticator.Type.TOTP,
                )
            except Authenticator.DoesNotExist:
                return False

            stored = auth.data.get('secret')
            secret = decrypt_secret(stored)
            if not secret:
                return False

            step = matching_timestep(secret, normalized)
            if step is None:
                return False

            if step <= auth.data.get('last_step', -1):
                # Already used, or older than a code we've already accepted.
                return False

            auth.data['last_step'] = step
            auth.data.pop('last_code', None)  # superseded by last_step
            if needs_rewrite(stored):
                auth.data['secret'] = encrypt_secret(secret)
            auth.last_used_at = timezone.now()
            auth.save(update_fields=['data', 'last_used_at'])
            return True
