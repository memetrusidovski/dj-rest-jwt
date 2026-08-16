import base64
import binascii
import uuid

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions, serializers

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import options_to_json
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from dj_rest_jwt.app_settings import api_settings
from dj_rest_jwt.reauth import ReauthSerializerMixin

from .models import WebAuthnCredential

UserModel = get_user_model()


def b64url_encode(raw):
    """Encode credential id bytes the way WebAuthn clients send them: unpadded base64url."""
    return base64.urlsafe_b64encode(bytes(raw)).rstrip(b'=').decode('ascii')


def b64url_decode(value):
    """Decode a stored (unpadded base64url) credential id back to bytes."""
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


def b64url_normalize(value):
    """
    Normalize a client-supplied base64url credential id to our stored form.

    Clients are inconsistent about padding, so decode then re-encode rather than
    comparing the raw strings. Returns None for anything that isn't valid
    base64url - the caller turns that into a 400 rather than letting a
    binascii.Error escape as a 500.
    """
    if not isinstance(value, str) or not value:
        return None
    padded = value + '=' * (-len(value) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded)
    except (binascii.Error, ValueError):
        return None
    if not raw:
        return None
    return b64url_encode(raw)


def _get_rp_settings():
    rp_id = api_settings.PASSKEY_RP_ID
    rp_name = api_settings.PASSKEY_RP_NAME
    rp_origins = api_settings.PASSKEY_RP_ORIGINS
    if not rp_id or not rp_name or not rp_origins:
        raise exceptions.ValidationError(
            _('Passkey RP settings (PASSKEY_RP_ID, PASSKEY_RP_NAME, PASSKEY_RP_ORIGINS) must be configured.')
        )
    return rp_id, rp_name, rp_origins


def _user_verification():
    if api_settings.PASSKEY_REQUIRE_USER_VERIFICATION:
        return UserVerificationRequirement.REQUIRED
    return UserVerificationRequirement.PREFERRED


def _extract_transports(credential):
    """
    Pull the authenticator's transport hints out of a client credential.

    Per the WebAuthn spec these live on `response.transports`, not at the top
    level - reading the wrong one silently records an empty list for every
    passkey, which then makes the browser's autofill hints worse.
    """
    if not isinstance(credential, dict):
        return []
    response = credential.get('response')
    if isinstance(response, dict):
        transports = response.get('transports')
        if isinstance(transports, list):
            return [t for t in transports if isinstance(t, str)]
    return []


class PasskeyRegisterBeginSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, default='', allow_blank=True)

    def validate(self, attrs):
        user = self.context['request'].user
        rp_id, rp_name, rp_origins = _get_rp_settings()

        exclude_credentials = [
            PublicKeyCredentialDescriptor(id=b64url_decode(cred.credential_id))
            for cred in WebAuthnCredential.objects.filter(user=user)
        ]

        options = generate_registration_options(
            rp_id=rp_id,
            rp_name=rp_name,
            user_name=user.get_username(),
            user_id=str(user.pk).encode(),
            user_display_name=user.get_full_name() or user.get_username(),
            exclude_credentials=exclude_credentials,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=_user_verification(),
            ),
            timeout=api_settings.PASSKEY_CHALLENGE_TIMEOUT * 1000,
        )

        cache_key = f'webauthn_reg_{user.pk}'
        cache.set(cache_key, base64.b64encode(options.challenge).decode(), api_settings.PASSKEY_CHALLENGE_TIMEOUT)

        attrs['options_json'] = options_to_json(options)
        attrs['name'] = attrs.get('name', '')
        return attrs


class PasskeyRegisterCompleteSerializer(ReauthSerializerMixin, serializers.Serializer):
    """
    Finish enrolling a passkey.

    Re-authenticated because the credential this creates outlives the access
    token that created it and survives a password reset - a stolen token alone
    must not be enough to plant one.
    """
    credential = serializers.JSONField()
    name = serializers.CharField(required=False, default='', allow_blank=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = self.context['request'].user
        rp_id, rp_name, rp_origins = _get_rp_settings()

        cache_key = f'webauthn_reg_{user.pk}'
        challenge_b64 = cache.get(cache_key)
        if not challenge_b64:
            raise exceptions.ValidationError(_('Registration challenge has expired. Please start over.'))

        challenge = base64.b64decode(challenge_b64)
        cache.delete(cache_key)

        try:
            verification = verify_registration_response(
                credential=attrs['credential'],
                expected_challenge=challenge,
                expected_rp_id=rp_id,
                expected_origin=rp_origins,
                require_user_verification=api_settings.PASSKEY_REQUIRE_USER_VERIFICATION,
            )
        except Exception:
            raise exceptions.ValidationError(_('Registration verification failed.'))

        credential_id = b64url_encode(verification.credential_id)
        if WebAuthnCredential.objects.filter(credential_id=credential_id).exists():
            raise exceptions.ValidationError(_('This credential is already registered.'))

        name = attrs.get('name', '') or _('Passkey')
        credential = WebAuthnCredential.objects.create(
            user=user,
            name=name,
            credential_id=credential_id,
            public_key=verification.credential_public_key,
            sign_count=verification.sign_count,
            transports=_extract_transports(attrs['credential']),
            discoverable=True,
        )

        attrs['credential_obj'] = credential
        return attrs


class PasskeyLoginBeginSerializer(serializers.Serializer):
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, attrs):
        rp_id, rp_name, rp_origins = _get_rp_settings()

        allow_credentials = None
        username = attrs.get('username', '').strip()
        email = attrs.get('email', '').strip()

        if username or email:
            lookup = {}
            if username:
                lookup[UserModel.USERNAME_FIELD] = username
            elif email:
                lookup[UserModel.EMAIL_FIELD] = email
            try:
                user = UserModel.objects.get(**lookup)
            except (UserModel.DoesNotExist, UserModel.MultipleObjectsReturned):
                pass  # Intentional: fall through to discoverable credentials flow
            else:
                allow_credentials = [
                    PublicKeyCredentialDescriptor(id=b64url_decode(cred.credential_id))
                    for cred in WebAuthnCredential.objects.filter(user=user)
                ]

        options = generate_authentication_options(
            rp_id=rp_id,
            allow_credentials=allow_credentials,
            user_verification=_user_verification(),
            timeout=api_settings.PASSKEY_CHALLENGE_TIMEOUT * 1000,
        )

        session_id = uuid.uuid4().hex
        cache_key = f'webauthn_auth_{session_id}'
        cache.set(cache_key, base64.b64encode(options.challenge).decode(), api_settings.PASSKEY_CHALLENGE_TIMEOUT)

        attrs['options_json'] = options_to_json(options)
        attrs['session_id'] = session_id
        return attrs


class PasskeyLoginCompleteSerializer(serializers.Serializer):
    credential = serializers.JSONField()
    session_id = serializers.RegexField(r'^[0-9a-f]{32}$')

    def validate(self, attrs):
        rp_id, rp_name, rp_origins = _get_rp_settings()

        cache_key = f'webauthn_auth_{attrs["session_id"]}'
        challenge_b64 = cache.get(cache_key)
        if not challenge_b64:
            raise exceptions.ValidationError(_('Authentication challenge has expired. Please start over.'))

        challenge = base64.b64decode(challenge_b64)
        cache.delete(cache_key)

        cred_data = attrs['credential']
        if not isinstance(cred_data, dict):
            raise exceptions.ValidationError(_('Invalid credential format.'))

        credential_id = b64url_normalize(cred_data.get('rawId') or cred_data.get('id'))
        if credential_id is None:
            raise exceptions.ValidationError(_('Invalid credential format.'))

        try:
            stored_credential = WebAuthnCredential.objects.get(credential_id=credential_id)
        except WebAuthnCredential.DoesNotExist:
            raise exceptions.ValidationError(_('Credential not found.'))

        try:
            verification = verify_authentication_response(
                credential=cred_data,
                expected_challenge=challenge,
                expected_rp_id=rp_id,
                expected_origin=rp_origins,
                credential_public_key=bytes(stored_credential.public_key),
                credential_current_sign_count=stored_credential.sign_count,
                require_user_verification=api_settings.PASSKEY_REQUIRE_USER_VERIFICATION,
            )
        except Exception:
            raise exceptions.ValidationError(_('Authentication verification failed.'))

        user = stored_credential.user
        if not user.is_active:
            raise exceptions.ValidationError(_('User account is disabled.'))

        stored_credential.sign_count = verification.new_sign_count
        stored_credential.last_used_at = timezone.now()
        stored_credential.save(update_fields=['sign_count', 'last_used_at'])

        from django.conf import settings as django_settings
        backends = django_settings.AUTHENTICATION_BACKENDS
        user.backend = backends[0] if backends else 'django.contrib.auth.backends.ModelBackend'
        attrs['user'] = user
        return attrs


class PasskeyListSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebAuthnCredential
        fields = ('id', 'name', 'credential_id', 'created_at', 'last_used_at', 'transports', 'discoverable')
        read_only_fields = ('id', 'credential_id', 'created_at', 'last_used_at', 'transports', 'discoverable')


class PasskeyUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebAuthnCredential
        fields = ('name',)


class PasskeyDeleteSerializer(ReauthSerializerMixin, serializers.Serializer):
    """Removing a login credential is as sensitive as adding one."""
