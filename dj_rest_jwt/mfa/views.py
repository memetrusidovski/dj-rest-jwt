import io
import logging

from django.db.models import Max
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from dj_rest_jwt.app_settings import api_settings
from dj_rest_jwt.throttling import (
    CredentialActionRateThrottle, MFAVerifyRateThrottle,
    SensitiveAccountActionRateThrottle,
)
from dj_rest_jwt.views import LoginView

from .audit import log_mfa_event
from .models import Authenticator
from .recovery_codes import RecoveryCodes
from .totp import TOTP, build_totp_uri, generate_totp_secret
from .utils import create_totp_activation_token, is_mfa_enabled


class MFALoginView(LoginView):
    """
    Kept for backwards compatibility.

    The MFA challenge now lives in `LoginView` itself, so that every login
    entry point - social, passkey, anything else subclassing it - is covered
    rather than just the one URL a project remembered to point here.
    """


@method_decorator(
    sensitive_post_parameters('code', 'ephemeral_token'),
    name='dispatch',
)
class MFAVerifyView(LoginView):
    """
    Exchange ephemeral_token + TOTP/recovery code for a real auth token.

    Subclasses LoginView so token issuance, cookie handling and the response
    shape are shared with the first-factor endpoint rather than reimplemented.
    """
    permission_classes = (AllowAny,)
    serializer_class = api_settings.MFA_VERIFY_SERIALIZER
    throttle_classes = (MFAVerifyRateThrottle,)

    def get_serializer_class(self):
        return api_settings.MFA_VERIFY_SERIALIZER

    def mfa_required(self):
        # This *is* the second factor; challenging again would loop forever.
        return False

    def login(self):
        self.user = self.serializer.validated_data['user']

        # django.contrib.auth.login() insists on knowing which backend
        # authenticated the user, and we got here without going through one.
        if not hasattr(self.user, 'backend'):
            from django.conf import settings as django_settings
            backends = django_settings.AUTHENTICATION_BACKENDS
            self.user.backend = (
                backends[0] if backends else 'django.contrib.auth.backends.ModelBackend'
            )

        self.issue_tokens()


@method_decorator(
    sensitive_post_parameters('code', 'activation_token', 'password'),
    name='dispatch',
)
class TOTPActivateView(GenericAPIView):
    """
    GET: Generate a new TOTP secret + provisioning URI + QR code.
    POST: Confirm TOTP activation with activation_token and a valid code.
    """
    permission_classes = (IsAuthenticated,)
    throttle_classes = (CredentialActionRateThrottle,)

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return api_settings.MFA_TOTP_ACTIVATE_INIT_SERIALIZER
        return api_settings.MFA_TOTP_ACTIVATE_CONFIRM_SERIALIZER

    def get(self, request, *args, **kwargs):
        secret = generate_totp_secret()
        totp_url = build_totp_uri(request.user, secret)
        qr_data_uri = self._generate_qr_data_uri(totp_url)
        activation_token = create_totp_activation_token(request.user, secret)
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(instance={
            'secret': secret,
            'totp_url': totp_url,
            'qr_code_data_uri': qr_data_uri,
            'activation_token': activation_token,
        })
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        if is_mfa_enabled(request.user):
            log_mfa_event(
                'activation_failed',
                user=request.user,
                request=request,
                level=logging.WARNING,
                reason='already_enabled',
            )
            return Response(
                {
                    'detail': _(
                        'MFA is already enabled. Deactivate it before activating again.',
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        secret = serializer.validated_data['secret']
        TOTP.activate(request.user, secret)
        codes = RecoveryCodes.activate(request.user)
        log_mfa_event(
            'activated',
            user=request.user,
            request=request,
            recovery_codes_count=len(codes),
        )

        return Response(
            {
                'recovery_codes': codes,
                'detail': _(
                    'Store these recovery codes now. They are shown once and '
                    'cannot be retrieved again.',
                ),
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _generate_qr_data_uri(data):
        try:
            import qrcode
            import qrcode.image.svg
        except ImportError:
            return ''
        img = qrcode.make(data, image_factory=qrcode.image.svg.SvgImage)
        buf = io.BytesIO()
        img.save(buf)
        import base64
        svg_b64 = base64.b64encode(buf.getvalue()).decode()
        return f'data:image/svg+xml;base64,{svg_b64}'


@method_decorator(
    sensitive_post_parameters('code'),
    name='dispatch',
)
class TOTPDeactivateView(GenericAPIView):
    """Deactivate TOTP MFA. Requires a valid TOTP code to confirm."""
    permission_classes = (IsAuthenticated,)
    throttle_classes = (CredentialActionRateThrottle,)

    def get_serializer_class(self):
        return api_settings.MFA_TOTP_DEACTIVATE_SERIALIZER

    def post(self, request, *args, **kwargs):
        if not is_mfa_enabled(request.user):
            log_mfa_event(
                'deactivation_failed',
                user=request.user,
                request=request,
                level=logging.WARNING,
                reason='not_enabled',
            )
            return Response(
                {'detail': _('MFA is not enabled.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        TOTP.deactivate(request.user)
        RecoveryCodes.deactivate(request.user)
        log_mfa_event(
            'deactivated',
            user=request.user,
            request=request,
        )

        return Response(
            {'detail': _('TOTP has been deactivated.')},
            status=status.HTTP_200_OK,
        )


class MFAStatusView(GenericAPIView):
    """Check whether the current user has MFA enabled."""
    permission_classes = (IsAuthenticated,)
    throttle_classes = (SensitiveAccountActionRateThrottle,)

    def get_serializer_class(self):
        return api_settings.MFA_STATUS_SERIALIZER

    def get(self, request, *args, **kwargs):
        try:
            auth = Authenticator.objects.get(
                user=request.user, type=Authenticator.Type.TOTP,
            )
            last_used_at = Authenticator.objects.filter(
                user=request.user,
                type__in=[
                    Authenticator.Type.TOTP,
                    Authenticator.Type.RECOVERY_CODES,
                ],
            ).aggregate(last_used_at=Max('last_used_at'))['last_used_at']
            data = {
                'mfa_enabled': True,
                'created_at': auth.created_at,
                'last_used_at': last_used_at,
                'recovery_codes_remaining': RecoveryCodes.get_unused_count(request.user),
            }
        except Authenticator.DoesNotExist:
            data = {
                'mfa_enabled': False,
                'created_at': None,
                'last_used_at': None,
                'recovery_codes_remaining': 0,
            }
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(instance=data)
        return Response(serializer.data)


class RecoveryCodesView(GenericAPIView):
    """
    How many recovery codes are left.

    The codes themselves are only ever shown once, when they're generated:
    they're stored as hashes, so there is nothing here to hand back. Use the
    regenerate endpoint to get a new set.
    """
    permission_classes = (IsAuthenticated,)
    throttle_classes = (SensitiveAccountActionRateThrottle,)

    def get_serializer_class(self):
        return api_settings.MFA_RECOVERY_CODES_STATUS_SERIALIZER

    def get(self, request, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        serializer = serializer_class(instance={
            'remaining': RecoveryCodes.get_unused_count(request.user),
        })
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)


@method_decorator(
    sensitive_post_parameters('password', 'code'),
    name='dispatch',
)
class RecoveryCodesRegenerateView(GenericAPIView):
    """Regenerate recovery codes. Invalidates all previous codes."""
    permission_classes = (IsAuthenticated,)
    throttle_classes = (CredentialActionRateThrottle,)

    def get_serializer_class(self):
        return api_settings.MFA_RECOVERY_CODES_REGENERATE_SERIALIZER

    def post(self, request, *args, **kwargs):
        if not is_mfa_enabled(request.user):
            return Response(
                {'detail': _('MFA is not enabled.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        codes = RecoveryCodes.activate(request.user)
        log_mfa_event(
            'recovery_codes_regenerated',
            user=request.user,
            request=request,
            recovery_codes_count=len(codes),
        )
        return Response({
            'codes': codes,
            'detail': _(
                'Store these recovery codes now. They are shown once and cannot '
                'be retrieved again.',
            ),
        })
