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

# The HTML pages live in demo/templates, one level above the Django project
# (demo/backend), so that the SPA client and this server-rendered tour of the
# API sit side by side under demo/.
DEMO_DIR = os.path.dirname(BASE_DIR)

# This project exists to demo the package locally. It is not a deployment
# template - see ../../starter for that - but it still shouldn't ship a
# checked-in secret key or answer to every Host header.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') or get_random_secret_key()

DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']

# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'rest_framework',
    'rest_framework.authtoken',
    # Gives password change/reset somewhere to record a revocation.
    'rest_framework_simplejwt.token_blacklist',
    'dj_rest_jwt',
    'allauth',
    'allauth.account',
    'allauth.mfa',
    'dj_rest_jwt.registration',
    'dj_rest_jwt.mfa',
    'dj_rest_jwt.passkeys',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.facebook',
    'drf_yasg',
    'corsheaders'
)

MIDDLEWARE = (
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
)

# For backwards compatibility for Django 1.8
MIDDLEWARE_CLASSES = MIDDLEWARE

ROOT_URLCONF = 'demo.urls'

WSGI_APPLICATION = 'demo.wsgi.application'

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
        'DIRS': [os.path.join(DEMO_DIR, 'templates'), ],
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
    'SESSION_LOGIN': False,
    'USE_JWT': False,
    # This demo showcases the classic Token-auth flow (matches
    # DEFAULT_AUTHENTICATION_CLASSES below) rather than the package's default
    # JWT-only mode, so TOKEN_MODEL has to be set explicitly now that it
    # defaults to None.
    'TOKEN_MODEL': 'rest_framework.authtoken.models.Token',

    'PASSKEY_RP_ID': 'localhost',
    'PASSKEY_RP_NAME': 'dj-rest-jwt demo',
    'PASSKEY_RP_ORIGINS': ['http://localhost:3000', 'http://localhost:8000'],
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
SITE_ID = 1
ACCOUNT_SIGNUP_FIELDS = ['email', 'username*', 'password1*', 'password2*']
ACCOUNT_LOGIN_METHODS = {'username'}
ACCOUNT_EMAIL_VERIFICATION = 'optional'


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.coreapi.AutoSchema'
}

SWAGGER_SETTINGS = {
    'LOGIN_URL': 'login',
    'LOGOUT_URL': 'logout',
}


# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
