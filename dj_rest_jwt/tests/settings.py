from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from dj_rest_jwt.defaults import *  # noqa: F401,F403
from dj_rest_jwt.defaults import DJ_REST_JWT_APPS, DJ_REST_JWT_MIDDLEWARE

SECRET_KEY = "tests-only"
DEBUG = False
ALLOWED_HOSTS = ["testserver"]
ROOT_URLCONF = "dj_rest_jwt.tests.urls"

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
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]   # speed; checked separately
SILENCED_SYSTEM_CHECKS = ["dj_rest_jwt.W008"]

HEADLESS_JWT_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
).decode()
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": "https://app.example.com/account/verify-email/{key}",
    "account_reset_password": "https://app.example.com/account/password/reset",
    "account_reset_password_from_key": "https://app.example.com/account/password/reset/key/{key}",
    "account_signup": "https://app.example.com/account/signup",
}
SOCIALACCOUNT_PROVIDERS = {
    "google": {"APPS": [{"client_id": "test-google-client", "secret": ""}]},
}
