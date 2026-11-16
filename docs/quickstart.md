# Quick start

## Install

```bash
pip install dj-rest-jwt
```

This pulls in django-allauth (with MFA, social accounts and headless), Django REST framework,
and argon2.

## Settings

```python title="settings.py"
import os

from dj_rest_jwt.defaults import *  # noqa  the secure preset

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    *DJ_REST_JWT_APPS,
    "allauth.socialaccount.providers.google",   # any providers you want
    # your apps
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

HEADLESS_JWT_PRIVATE_KEY = os.environ["JWT_PRIVATE_KEY"]

# Codes in emails (the default) or links? See the emails guide.
globals().update(email_flows(verification="code", password_reset="code"))

# Where your frontend handles the links in emails.
HEADLESS_FRONTEND_URLS = {
    "account_reset_password": "https://app.example.com/forgot-password",
    "account_signup": "https://app.example.com/signup",
    # only needed for link mode:
    # "account_confirm_email": "https://app.example.com/verify-email/{key}",
    # "account_reset_password_from_key": "https://app.example.com/reset-password/{key}",
}

# Sessions are read on every authenticated request: back them with a shared cache.
CACHES = {"default": {
    "BACKEND": "django.core.cache.backends.redis.RedisCache",
    "LOCATION": os.environ["REDIS_URL"],
}}
```

The preset sets the rest: token lifetimes, Argon2, password rules, mandatory email verification,
enumeration protection, MFA and passkeys, DRF defaults. Override any of it after the import.
[Settings reference](reference/settings.md).

## URLs

```python title="urls.py"
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", include("dj_rest_jwt.admin_login")),   # before admin.site.urls
    path("admin/", admin.site.urls),
    path("api/auth/", include("dj_rest_jwt.urls")),       # /api/auth/v1/...
    path("api/", include("myapp.urls")),                  # your API, JWT-protected by default
]
```

## Key, database, checks

```bash
python manage.py generate_jwt_key   # put the output in JWT_PRIVATE_KEY; never commit it
python manage.py migrate
python manage.py check --deploy
```

`check --deploy` runs the [system checks](reference/checks.md); fix anything they report before
going live.

## Frontend

```bash
npm install dj-rest-jwt-client
```

```ts
import { createAuthClient } from "dj-rest-jwt-client";

export const auth = createAuthClient();          // browser: cookie transport
await auth.getSession();
const res = await auth.login({ email, password });
const me = await auth.fetch("/api/me");          // refreshes and retries on 401
```

See the [JavaScript client](guides/js-client.md) guide, and the
[demo](https://github.com/memetrusidovski/dj-rest-jwt/tree/main/demo) for a complete React app.
