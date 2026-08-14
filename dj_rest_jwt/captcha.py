import requests
from django.core.exceptions import ImproperlyConfigured
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .app_settings import api_settings

# (siteverify URL, the POST field the provider expects the widget token in)
_BACKENDS = {
    'turnstile': 'https://challenges.cloudflare.com/turnstile/v0/siteverify',
    'recaptcha_v3': 'https://www.google.com/recaptcha/api/siteverify',
    'hcaptcha': 'https://hcaptcha.com/siteverify',
}


def verify_captcha(token, remote_ip=None):
    """
    Verify a widget response token against the configured captcha backend's
    siteverify endpoint. Returns True/False; raises ImproperlyConfigured if
    captcha is enabled but misconfigured.
    """
    backend = api_settings.CAPTCHA_BACKEND
    if backend not in _BACKENDS:
        raise ImproperlyConfigured(
            "CAPTCHA_BACKEND must be one of %s, got %r" % (list(_BACKENDS), backend)
        )
    secret = api_settings.CAPTCHA_SECRET_KEY
    if not secret:
        raise ImproperlyConfigured(
            'ENABLE_CAPTCHA is True but CAPTCHA_SECRET_KEY is not set.'
        )
    if not token:
        return False

    data = {'secret': secret, 'response': token}
    if remote_ip:
        data['remoteip'] = remote_ip

    try:
        result = requests.post(_BACKENDS[backend], data=data, timeout=5).json()
    except (requests.RequestException, ValueError):
        # Fail closed: a network hiccup with the captcha provider shouldn't be
        # treated as a free pass for bots.
        return False

    if backend == 'recaptcha_v3':
        threshold = api_settings.CAPTCHA_RECAPTCHA_V3_MIN_SCORE
        return bool(result.get('success')) and result.get('score', 0) >= threshold
    return bool(result.get('success'))


class CaptchaSerializerMixin(serializers.Serializer):
    """
    Adds a `captcha_token` field, validated against the configured captcha
    backend, when ENABLE_CAPTCHA is on. No-op (field not even present) when off,
    so this is safe to mix into serializers regardless of configuration.
    """
    def get_fields(self):
        fields = super().get_fields()
        if api_settings.ENABLE_CAPTCHA:
            fields['captcha_token'] = serializers.CharField(
                write_only=True, required=True, allow_blank=False,
            )
        return fields

    def validate_captcha_token(self, value):
        request = self.context.get('request')
        remote_ip = request.META.get('REMOTE_ADDR') if request else None
        if not verify_captcha(value, remote_ip=remote_ip):
            raise ValidationError(_('Captcha verification failed.'))
        return value


class HoneypotSerializerMixin(serializers.Serializer):
    """
    Adds a hidden `HONEYPOT_FIELD_NAME` field that must be left blank. Real
    users never see or fill it (hide it with CSS/aria-hidden on the client);
    bots that blindly fill every form field trip it. Enabled independently of
    ENABLE_CAPTCHA via ENABLE_HONEYPOT.
    """
    def get_fields(self):
        fields = super().get_fields()
        if api_settings.ENABLE_HONEYPOT:
            fields[api_settings.HONEYPOT_FIELD_NAME] = serializers.CharField(
                write_only=True, required=False, allow_blank=True, default='',
            )
        return fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if api_settings.ENABLE_HONEYPOT:
            field_name = api_settings.HONEYPOT_FIELD_NAME
            if attrs.pop(field_name, ''):
                raise ValidationError(_('Spam detected.'))
        return attrs
