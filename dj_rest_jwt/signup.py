"""
Signup anti-spam, plugged into allauth via ``ACCOUNT_SIGNUP_FORM_CLASS``.

allauth builds its signup form (headless included) on top of this class, so
the fields below appear on ``POST /auth/signup`` without touching its views.

- Honeypot: a field named ``HONEYPOT_FIELD_NAME`` that must stay empty. Free,
  no third party, on whenever this form is configured. Hide it in the client.
- Captcha: set ``CAPTCHA_BACKEND`` and ``CAPTCHA_SECRET_KEY`` and the client
  must send ``captcha_token`` from the widget. Fails closed if the provider
  can't be reached.
"""
import requests
from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

from . import conf

CAPTCHA_VERIFY_URLS = {
    "turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    "recaptcha_v3": "https://www.google.com/recaptcha/api/siteverify",
    "hcaptcha": "https://hcaptcha.com/siteverify",
}


def verify_captcha(token, remote_ip=None):
    backend = conf.get("CAPTCHA_BACKEND")
    if backend not in CAPTCHA_VERIFY_URLS:
        raise ImproperlyConfigured(f"CAPTCHA_BACKEND must be one of {list(CAPTCHA_VERIFY_URLS)}, got {backend!r}")
    secret = conf.get("CAPTCHA_SECRET_KEY")
    if not secret:
        raise ImproperlyConfigured("CAPTCHA_BACKEND is set but CAPTCHA_SECRET_KEY is not.")
    if not token:
        return False
    data = {"secret": secret, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        result = requests.post(CAPTCHA_VERIFY_URLS[backend], data=data, timeout=5).json()
    except (requests.RequestException, ValueError):
        return False
    if backend == "recaptcha_v3":
        return bool(result.get("success")) and result.get("score", 0) >= conf.get("CAPTCHA_RECAPTCHA_V3_MIN_SCORE")
    return bool(result.get("success"))


class SignupForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[conf.get("HONEYPOT_FIELD_NAME")] = forms.CharField(required=False)
        if conf.get("CAPTCHA_BACKEND"):
            self.fields["captcha_token"] = forms.CharField(required=True)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get(conf.get("HONEYPOT_FIELD_NAME")):
            raise forms.ValidationError(_("Signup could not be completed."), code="spam")
        if conf.get("CAPTCHA_BACKEND") and "captcha_token" in cleaned:
            from allauth.core import context

            request = getattr(context, "request", None)
            remote_ip = request.META.get("REMOTE_ADDR") if request is not None else None
            if not verify_captcha(cleaned["captcha_token"], remote_ip=remote_ip):
                self.add_error("captcha_token", _("Captcha verification failed."))
        return cleaned

    def signup(self, request, user):
        """Required by allauth's ACCOUNT_SIGNUP_FORM_CLASS contract."""
