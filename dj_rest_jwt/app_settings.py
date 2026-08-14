from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework.settings import APISettings as _APISettings


USER_SETTINGS = getattr(settings, "REST_AUTH", None)

DEFAULTS = {
    'LOGIN_SERIALIZER': 'dj_rest_jwt.serializers.LoginSerializer',
    'TOKEN_SERIALIZER': 'dj_rest_jwt.serializers.TokenSerializer',
    'JWT_SERIALIZER': 'dj_rest_jwt.serializers.JWTSerializer',
    'JWT_SERIALIZER_WITH_EXPIRATION': 'dj_rest_jwt.serializers.JWTSerializerWithExpiration',
    'JWT_TOKEN_CLAIMS_SERIALIZER': 'rest_framework_simplejwt.serializers.TokenObtainPairSerializer',
    'USER_DETAILS_SERIALIZER': 'dj_rest_jwt.serializers.UserDetailsSerializer',
    'PASSWORD_RESET_SERIALIZER': 'dj_rest_jwt.serializers.PasswordResetSerializer',
    'PASSWORD_RESET_CONFIRM_SERIALIZER': 'dj_rest_jwt.serializers.PasswordResetConfirmSerializer',
    'PASSWORD_CHANGE_SERIALIZER': 'dj_rest_jwt.serializers.PasswordChangeSerializer',

    'REGISTER_SERIALIZER': 'dj_rest_jwt.registration.serializers.RegisterSerializer',

    'REGISTER_PERMISSION_CLASSES': ('rest_framework.permissions.AllowAny',),

    'TOKEN_MODEL': None,
    'TOKEN_CREATOR': 'dj_rest_jwt.utils.default_create_token',

    'PASSWORD_RESET_USE_SITES_DOMAIN': False,
    'OLD_PASSWORD_FIELD_ENABLED': False,
    'LOGOUT_ON_PASSWORD_CHANGE': False,
    'SESSION_LOGIN': False,
    'USE_JWT': True,

    'JWT_AUTH_COOKIE': None,
    'JWT_AUTH_REFRESH_COOKIE': None,
    'JWT_AUTH_REFRESH_COOKIE_PATH': '/',
    'JWT_AUTH_SECURE': False,
    'JWT_AUTH_HTTPONLY': True,
    'JWT_AUTH_SAMESITE': 'Lax',
    'JWT_AUTH_COOKIE_DOMAIN': None,
    'JWT_AUTH_RETURN_EXPIRATION': False,
    'JWT_AUTH_COOKIE_USE_CSRF': False,
    'JWT_AUTH_COOKIE_ENFORCE_CSRF_ON_UNAUTHENTICATED': False,

    # Rate limiting - active out of the box, no REST_FRAMEWORK throttle config needed.
    # Set any of these to None to disable throttling for that endpoint.
    'RATE_LIMIT_LOGIN': '10/min',
    'RATE_LIMIT_REGISTER': '20/hour',
    'RATE_LIMIT_PASSWORD_RESET': '5/hour',
    'RATE_LIMIT_SENSITIVE_ACTION': '30/hour',

    # MFA settings — only active when dj_rest_jwt.mfa is in INSTALLED_APPS
    'MFA_VERIFY_SERIALIZER': 'dj_rest_jwt.mfa.serializers.MFAVerifySerializer',
    'MFA_TOTP_ACTIVATE_INIT_SERIALIZER': 'dj_rest_jwt.mfa.serializers.TOTPActivateInitSerializer',
    'MFA_TOTP_ACTIVATE_CONFIRM_SERIALIZER': 'dj_rest_jwt.mfa.serializers.TOTPActivateConfirmSerializer',
    'MFA_TOTP_DEACTIVATE_SERIALIZER': 'dj_rest_jwt.mfa.serializers.TOTPDeactivateSerializer',
    'MFA_STATUS_SERIALIZER': 'dj_rest_jwt.mfa.serializers.MFAStatusSerializer',
    'MFA_RECOVERY_CODES_SERIALIZER': 'dj_rest_jwt.mfa.serializers.RecoveryCodesSerializer',
    'MFA_EPHEMERAL_TOKEN_TIMEOUT': 300,
    'MFA_TOTP_DIGITS': 6,
    'MFA_TOTP_PERIOD': 30,
    'MFA_TOTP_ISSUER': '',
    'MFA_RECOVERY_CODE_COUNT': 10,

    # Passkey settings (serializers resolved lazily to avoid importing webauthn when not installed)
    'PASSKEY_RP_ID': None,
    'PASSKEY_RP_NAME': None,
    'PASSKEY_RP_ORIGINS': None,
    'PASSKEY_CHALLENGE_TIMEOUT': 300,
}

# List of settings that may be in string import notation.
IMPORT_STRINGS = (
    'TOKEN_CREATOR',
    'TOKEN_MODEL',
    'TOKEN_SERIALIZER',
    'JWT_SERIALIZER',
    'JWT_SERIALIZER_WITH_EXPIRATION',
    'JWT_TOKEN_CLAIMS_SERIALIZER',
    'USER_DETAILS_SERIALIZER',
    'LOGIN_SERIALIZER',
    'PASSWORD_RESET_SERIALIZER',
    'PASSWORD_RESET_CONFIRM_SERIALIZER',
    'PASSWORD_CHANGE_SERIALIZER',
    'REGISTER_SERIALIZER',
    'REGISTER_PERMISSION_CLASSES',
    'MFA_VERIFY_SERIALIZER',
    'MFA_TOTP_ACTIVATE_INIT_SERIALIZER',
    'MFA_TOTP_ACTIVATE_CONFIRM_SERIALIZER',
    'MFA_TOTP_DEACTIVATE_SERIALIZER',
    'MFA_STATUS_SERIALIZER',
    'MFA_RECOVERY_CODES_SERIALIZER',
)

# List of settings that have been removed
REMOVED_SETTINGS = []


_PASSKEY_SERIALIZER_DEFAULTS = {
    'PASSKEY_REGISTER_BEGIN_SERIALIZER': 'dj_rest_jwt.passkeys.serializers.PasskeyRegisterBeginSerializer',
    'PASSKEY_REGISTER_COMPLETE_SERIALIZER': 'dj_rest_jwt.passkeys.serializers.PasskeyRegisterCompleteSerializer',
    'PASSKEY_LOGIN_BEGIN_SERIALIZER': 'dj_rest_jwt.passkeys.serializers.PasskeyLoginBeginSerializer',
    'PASSKEY_LOGIN_COMPLETE_SERIALIZER': 'dj_rest_jwt.passkeys.serializers.PasskeyLoginCompleteSerializer',
    'PASSKEY_LIST_SERIALIZER': 'dj_rest_jwt.passkeys.serializers.PasskeyListSerializer',
    'PASSKEY_UPDATE_SERIALIZER': 'dj_rest_jwt.passkeys.serializers.PasskeyUpdateSerializer',
}


class APISettings(_APISettings):  # pragma: no cover
    def __check_user_settings(self, user_settings):
        from .utils import format_lazy
        SETTINGS_DOC = 'https://dj-rest-jwt.readthedocs.io/en/latest/configuration.html'

        for setting in REMOVED_SETTINGS:
            if setting in user_settings:
                raise RuntimeError(
                    format_lazy(
                        _(
                            "The '{}' setting has been removed. Please refer to '{}' for available settings."
                        ),
                        setting,
                        SETTINGS_DOC,
                    )
                )

        return user_settings

    def __getattr__(self, attr):
        if attr in _PASSKEY_SERIALIZER_DEFAULTS:
            from django.utils.module_loading import import_string
            val = self.user_settings.get(attr, _PASSKEY_SERIALIZER_DEFAULTS[attr])
            val = import_string(val)
            self.__dict__[attr] = val
            return val
        return super().__getattr__(attr)


api_settings = APISettings(USER_SETTINGS, DEFAULTS, IMPORT_STRINGS)
