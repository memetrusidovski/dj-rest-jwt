"""
Django settings for demo project.

For more information on this file, see
https://docs.djangoproject.com/en/1.7/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.7/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os

from django.core.management.utils import get_random_secret_key

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# This is a starter template meant to be copied into a real project, so it reads
# its security-critical settings from the environment and only falls back to
# development-friendly values. Set DJANGO_DEBUG=0 and DJANGO_SECRET_KEY before
# deploying anywhere real.

# A generated key changes on every restart, which logs everyone out - fine for a
# scratch project, not something to rely on. Set DJANGO_SECRET_KEY in any
# environment you care about.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') or get_random_secret_key()

DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'

ALLOWED_HOSTS = [
    h for h in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h
]

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'rest_framework',
    'rest_framework.authtoken',
    # Required for logout and for password changes to actually revoke
    # already-issued refresh tokens.
    'rest_framework_simplejwt.token_blacklist',
    'dj_rest_jwt',
    'allauth',
    'allauth.account',
    'dj_rest_jwt.registration',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.facebook',
    'drf_yasg',
    'corsheaders'
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

# For backwards compatibility for Django 1.8
MIDDLEWARE_CLASSES = MIDDLEWARE

ROOT_URLCONF = 'starter.urls'

WSGI_APPLICATION = 'starter.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.7/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.7/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.7/howto/static-files/

STATIC_URL = '/static/'

# TEMPLATE_DIRS = [os.path.join(BASE_DIR, 'templates')]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates'), ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

REST_AUTH = {
    'SESSION_LOGIN': True,
    'USE_JWT': True,
    'JWT_AUTH_COOKIE': 'auth',
    'JWT_AUTH_REFRESH_COOKIE': 'refresh',
    # Keep the token out of reach of JavaScript, so an XSS bug in the frontend
    # can't walk off with it.
    'JWT_AUTH_HTTPONLY': True,
    # Off only so the template works over http://localhost. Must be True
    # anywhere with a real domain.
    'JWT_AUTH_SECURE': not DEBUG,
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
SITE_ID = 1
ACCOUNT_SIGNUP_FIELDS = ['email', 'username*', 'password1*', 'password2*']
ACCOUNT_LOGIN_METHODS = {'username'}
ACCOUNT_EMAIL_VERIFICATION = 'optional'


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'dj_rest_jwt.jwt_auth.JWTCookieAuthentication'
    ),
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.coreapi.AutoSchema'
}

SWAGGER_SETTINGS = {
    'LOGIN_URL': 'login',
    'LOGOUT_URL': 'logout',
}


# An allowlist, not "*": CORS_ALLOW_CREDENTIALS with a wildcard origin would let
# any site on the internet make authenticated requests with the user's cookie.
CORS_ALLOWED_ORIGINS = [
    o for o in os.environ.get(
        'DJANGO_CORS_ALLOWED_ORIGINS',
        'http://localhost:3000,http://127.0.0.1:3000',
    ).split(',') if o
]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = list(CORS_ALLOWED_ORIGINS)

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
