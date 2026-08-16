"""
Step-up re-authentication for credential changes.

Enrolling a passkey or rotating recovery codes creates a credential that
outlives the access token used to create it, and survives a password reset. So
a stolen token alone must not be enough: the caller has to re-prove they are the
account holder, with their password or a current second-factor code.

Mixed into a serializer, this adds optional `password` and `code` fields and
requires one of them to check out. Users who have neither a usable password nor
MFA (social-only accounts) have nothing to prove with, and are let through -
their account security rests on the provider.
"""
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .app_settings import api_settings


def mfa_available(user):
    from django.apps import apps
    if not apps.is_installed('dj_rest_jwt.mfa'):
        return False
    from .mfa.utils import is_mfa_enabled
    return is_mfa_enabled(user)


class ReauthSerializerMixin(serializers.Serializer):
    """
    Requires `password` or `code` before a credential change is allowed.

    Set `REST_AUTH['REQUIRE_REAUTH_FOR_CREDENTIAL_CHANGES'] = False` to turn
    this off, e.g. if your project enforces freshness at another layer.
    """

    def get_fields(self):
        fields = super().get_fields()
        if api_settings.REQUIRE_REAUTH_FOR_CREDENTIAL_CHANGES:
            fields['password'] = serializers.CharField(
                write_only=True, required=False, allow_blank=True,
                style={'input_type': 'password'},
                help_text=_('Your current password. Required unless a second-factor code is given.'),
            )
            fields['code'] = serializers.CharField(
                write_only=True, required=False, allow_blank=True,
                help_text=_('A current TOTP or recovery code. Alternative to the password.'),
            )
        return fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not api_settings.REQUIRE_REAUTH_FOR_CREDENTIAL_CHANGES:
            return attrs

        password = attrs.pop('password', '') or ''
        code = attrs.pop('code', '') or ''
        user = self.context['request'].user

        has_password = user.has_usable_password()
        has_mfa = mfa_available(user)

        if not has_password and not has_mfa:
            # Nothing to re-prove with.
            return attrs

        if password and has_password and user.check_password(password):
            return attrs

        if code and has_mfa and self._check_code(user, code):
            return attrs

        if has_mfa:
            message = _(
                'This action needs re-authentication. Send your current password '
                'or a current second-factor code.'
            )
        else:
            message = _('This action needs re-authentication. Send your current password.')
        raise serializers.ValidationError({'password': message})

    @staticmethod
    def _check_code(user, code):
        from .mfa.recovery_codes import RecoveryCodes
        from .mfa.totp import TOTP
        return TOTP.validate_code(user, code) or RecoveryCodes.validate_code(user, code)
