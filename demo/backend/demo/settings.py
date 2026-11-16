"""
Demo settings: dj-rest-jwt's secure preset plus what a local dev setup needs.

Not a deployment template. Values marked DEV ONLY must change in production.
"""
import os
from pathlib import Path

from django.core.management.utils import get_random_secret_key

from dj_rest_jwt.defaults import *  # noqa: F401,F403  the secure preset
from dj_rest_jwt.defaults import DJ_REST_JWT_APPS, DJ_REST_JWT_MIDDLEWARE, email_flows

BASE_DIR = Path(__file__).resolve().parent.parent

# DEV ONLY: generated once and kept on disk. It also protects sessions (and
# so every JWT); a new key would sign everybody out.
_secret_file = BASE_DIR / ".secret_key"
if not os.environ.get("DJANGO_SECRET_KEY") and not _secret_file.exists():
    _secret_file.write_text(get_random_secret_key())
    _secret_file.chmod(0o600)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or _secret_file.read_text()
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "backend"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    *DJ_REST_JWT_APPS,
    "allauth.socialaccount.providers.google",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    *DJ_REST_JWT_MIDDLEWARE,
]

ROOT_URLCONF = "demo.urls"
WSGI_APPLICATION = "demo.wsgi.application"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
USE_TZ = True

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    # Our copies of allauth's email templates live here and win over
    # allauth's. Make your own with: python manage.py copy_email_templates templates/
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

# --- Signing key -------------------------------------------------------------
# DEV ONLY: a key generated on first run and kept next to the database so
# tokens survive restarts. In production read it from a secret store.
_key_file = BASE_DIR / ".jwt_key.pem"
if os.environ.get("JWT_PRIVATE_KEY"):
    HEADLESS_JWT_PRIVATE_KEY = os.environ["JWT_PRIVATE_KEY"]
else:
    if not _key_file.exists():
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        _key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _key_file.write_bytes(_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
        ))
        _key_file.chmod(0o600)
    HEADLESS_JWT_PRIVATE_KEY = _key_file.read_text()

# --- Email -------------------------------------------------------------------
# Codes or links? One call picks every email flow. Try
#   email_flows(verification="link", password_reset="link")
# and the SPA's /verify-email/:key and /reset-password/:key routes take over.
globals().update(email_flows(verification="code", password_reset="code", login_code=True))

# Where the SPA handles the links in emails (http://localhost:5173 is Vite).
FRONTEND = os.environ.get("FRONTEND_URL", "http://localhost:5173")
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": f"{FRONTEND}/verify-email/{{key}}",
    "account_reset_password": f"{FRONTEND}/forgot-password",
    "account_reset_password_from_key": f"{FRONTEND}/reset-password/{{key}}",
    "account_signup": f"{FRONTEND}/signup",
    "socialaccount_login_error": f"{FRONTEND}/login",
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"   # DEV ONLY: emails print to the console
if os.environ.get("EMAIL_FILE_PATH"):   # used by the JS client's end-to-end tests to read codes
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    EMAIL_FILE_PATH = os.environ["EMAIL_FILE_PATH"]
DEFAULT_FROM_EMAIL = "Demo App <no-reply@example.com>"
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Demo App] "

# --- Social login ------------------------------------------------------------
# Set GOOGLE_CLIENT_ID to show "Sign in with Google" (Google Identity Services
# ID token -> POST auth/provider/token).
if os.environ.get("GOOGLE_CLIENT_ID"):
    SOCIALACCOUNT_PROVIDERS = {"google": {"APPS": [{
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
    }]}}

# --- Local HTTP --------------------------------------------------------------
if DEBUG:
    # DEV ONLY: plain http://localhost. Never in production.
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    DJ_REST_JWT = {"COOKIE_SECURE": False}
    MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = True
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    CSRF_TRUSTED_ORIGINS = [FRONTEND]
