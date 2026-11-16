"""
Secure defaults for an API-first project. In settings.py::

    from dj_rest_jwt.defaults import *  # noqa

    INSTALLED_APPS = [..., *DJ_REST_JWT_APPS]
    MIDDLEWARE = [..., *DJ_REST_JWT_MIDDLEWARE]   # after Session/Csrf/Auth middleware

    HEADLESS_FRONTEND_URLS = {...}   # where your SPA handles email links
    HEADLESS_JWT_PRIVATE_KEY = env("JWT_PRIVATE_KEY")   # manage.py generate_jwt_key

then override anything below. ``manage.py check`` (and ``--deploy``) reports
settings that weaken the result.

To switch emails between codes and links, use ``email_flows()`` (below).
"""


def email_flows(verification="code", password_reset="code", login_code=False):
    """
    Pick how each email flow works, as settings to merge into settings.py::

        globals().update(email_flows(verification="link", password_reset="code"))

    ``verification`` / ``password_reset``:
        ``"code"``  the email holds a short code the user types into the app.
                    Works across devices (read mail on the phone, type on the
                    laptop) and survives email scanners that pre-open links.
        ``"link"``  the email holds a link to your frontend
                    (``HEADLESS_FRONTEND_URLS``), which posts the key back.
    ``login_code``:
        Also offer passwordless sign-in with an emailed code
        (``auth/code/request`` + ``auth/code/confirm``). allauth has no
        "magic link" sign-in; the code is its equivalent, and safer.

    Passkey-only signup needs code verification (the user has no password to
    come back with), so it is switched off with ``verification="link"``.
    """
    for name, value in (("verification", verification), ("password_reset", password_reset)):
        if value not in ("code", "link"):
            raise ValueError(f'{name} must be "code" or "link", got {value!r}')
    return {
        "ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED": verification == "code",
        "ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED": password_reset == "code",
        "ACCOUNT_LOGIN_BY_CODE_ENABLED": bool(login_code),
        "MFA_PASSKEY_SIGNUP_ENABLED": verification == "code",
    }


DJ_REST_JWT_APPS = [
    "django.contrib.sessions",
    "rest_framework",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.mfa",
    "allauth.usersessions",
    "allauth.headless",
    "dj_rest_jwt",
]

DJ_REST_JWT_MIDDLEWARE = [
    "allauth.account.middleware.AccountMiddleware",
    "dj_rest_jwt.middleware.TokenTransportMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# --- Passwords -------------------------------------------------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Tokens ----------------------------------------------------------------
# Clients authenticate with JWTs only; allauth's cookie-session "browser"
# client and its HTML pages are off.
HEADLESS_ONLY = True
HEADLESS_CLIENTS = ("app",)
HEADLESS_TOKEN_STRATEGY = "dj_rest_jwt.strategy.JWTTokenStrategy"
HEADLESS_JWT_ALGORITHM = "RS256"
HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN = 60 * 5
# Sliding "stay signed in": every refresh issues a new refresh token with a
# fresh lifetime, so a user who returns within this window never logs in again.
HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN = 60 * 60 * 24 * 30
HEADLESS_JWT_ROTATE_REFRESH_TOKEN = True
# Logging out or revoking a device kills its access tokens immediately,
# at the cost of a (cached) session lookup per request.
HEADLESS_JWT_STATEFUL_VALIDATION_ENABLED = True

# The server-side session is the refresh token's backing store, not a client
# credential. It must outlive the refresh token (it is re-extended on each
# refresh), and should be cache-backed because every request touches it.
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_AGE = HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True

# --- Accounts --------------------------------------------------------------
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_SIGNUP_FORM_CLASS = "dj_rest_jwt.signup.SignupForm"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
# Codes, not links, by default; change with email_flows().
globals().update(email_flows())
ACCOUNT_PREVENT_ENUMERATION = True
ACCOUNT_CHANGE_EMAIL = True
ACCOUNT_EMAIL_NOTIFICATIONS = True         # "your password was changed", ...
ACCOUNT_REAUTHENTICATION_REQUIRED = True   # step-up before sensitive changes
# Google-style: the device that changed the password stays signed in; every
# other session is invalidated (Django ties sessions to the password hash).
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = False
ACCOUNT_LOGIN_ON_PASSWORD_RESET = False
# Rate limits: allauth's built-in ACCOUNT_RATE_LIMITS defaults (login,
# failed logins per IP and per account, signup, password reset, ...) are
# already sound and are left alone. A system check refuses `False`.

# --- MFA and passkeys ------------------------------------------------------
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes", "webauthn"]
MFA_PASSKEY_LOGIN_ENABLED = True
MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = False

# --- Social login ----------------------------------------------------------
# Never sign someone into an existing account just because a provider
# reports the same email address.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = False
SOCIALACCOUNT_LOGIN_ON_GET = False

# --- DRF -------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["dj_rest_jwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}

# --- Admin -----------------------------------------------------------------
LOGIN_URL = "account_login"

# --- Transport headers -----------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
