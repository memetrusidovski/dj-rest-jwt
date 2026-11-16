# dj-rest-jwt

Secure, API-first JWT authentication for Django, built on
[django-allauth](https://docs.allauth.org/) headless.

allauth does the authentication: login, signup, email verification, password reset, TOTP and
recovery codes, passkeys, Google/GitHub/Apple/Microsoft and 100+ other providers, device sessions,
JWT minting and refresh-token rotation. dj-rest-jwt adds the layer an API-first project still needs,
with every protection switched on:

- **Two token transports, per client.** Browser SPAs get httpOnly cookies that script can never read,
  with CSRF protection. Native apps send `X-Auth-Transport: header` and use `Authorization: Bearer`.
  The two never mix.
- **Clean URLs.** `/api/auth/v1/auth/login` instead of `/_allauth/app/v1/auth/login`.
- **Stays signed in.** Each refresh issues a new refresh token, so a user who comes back within the
  refresh lifetime (30 days by default) never has to log in again.
- **Refresh-token theft detection.** Replaying a rotated refresh token ends the whole session.
- **Instant revocation.** Logging out, revoking a device or changing the password kills the affected
  access tokens immediately. The device that changed the password stays signed in.
- **A secure admin.** Django admin sign-in goes through allauth, with rate limits and MFA.
- **Signup anti-spam.** Honeypot by default; Turnstile, reCAPTCHA v3 or hCaptcha optional.
- **Codes or links in emails**, picked with one call, and every email editable
  (`manage.py copy_email_templates`).
- **A JavaScript client** (`dj-rest-jwt-client`, in `js/`) that refreshes on 401, shares one
  refresh across tabs, and wraps every flow including passkeys. React bindings included.
- **A secure preset and system checks** that flag settings that weaken it.
- **A DRF authentication class** for the rest of your API.

Requires Python 3.12+, Django 6.0+.

## Quick start

```bash
pip install dj-rest-jwt
```

```python
# settings.py
from dj_rest_jwt.defaults import *  # noqa

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    *DJ_REST_JWT_APPS,
    "allauth.socialaccount.providers.google",   # any providers you want
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

# Emails carry codes (default) or links: pick per flow.
globals().update(email_flows(verification="code", password_reset="code", login_code=False))

# Where your frontend handles the links in emails.
HEADLESS_FRONTEND_URLS = {
    "account_reset_password": "https://app.example.com/forgot-password",
    "account_signup": "https://app.example.com/signup",
    # link mode only:
    # "account_confirm_email": "https://app.example.com/verify-email/{key}",
    # "account_reset_password_from_key": "https://app.example.com/reset-password/{key}",
}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache",
                      "LOCATION": os.environ["REDIS_URL"]}}
```

```python
# urls.py
urlpatterns = [
    path("admin/", include("dj_rest_jwt.admin_login")),   # before admin.site.urls
    path("admin/", admin.site.urls),
    path("api/auth/", include("dj_rest_jwt.urls")),
    path("api/", include("myapp.urls")),                  # your DRF API, JWT-protected by default
]
```

Then:

```bash
python manage.py generate_jwt_key   # put the output in JWT_PRIVATE_KEY; never commit it
python manage.py migrate
python manage.py check --deploy
```

Frontend:

```ts
import { createAuthClient } from "dj-rest-jwt-client";

const auth = createAuthClient();                 // browser SPA: cookie transport
await auth.login({ email, password });
const res = await auth.fetch("/api/me");         // refreshes and retries on 401
```

See [`demo/`](demo/) for a complete React app, and the
[documentation](https://memetrusidovski.github.io/dj-rest-jwt/) for every guide.

## Endpoints

Everything under `/api/auth/v1/` is
[allauth's headless API](https://docs.allauth.org/en/latest/headless/openapi-specification/) for the
`app` client, so its OpenAPI spec describes the request and response shapes. Common ones:

| Endpoint | Purpose |
|---|---|
| `POST auth/signup`, `POST auth/email/verify` | Sign up, confirm with the emailed code |
| `POST auth/login` | Password login (answers `401` + a pending `mfa_authenticate` flow when MFA is on) |
| `POST auth/2fa/authenticate` | Finish login with a TOTP or recovery code |
| `GET/POST auth/webauthn/login` | Passkey login |
| `POST auth/provider/token` | Social login with a provider ID/access token (Google One Tap, native SDKs) |
| `GET/DELETE auth/session` | Current user / log out |
| `POST tokens/refresh` | New token pair (cookie or body, depending on transport) |
| `GET/DELETE auth/sessions` | List and revoke signed-in devices |
| `POST auth/reauthenticate` | Step-up before sensitive changes |
| `POST account/password/change` | Change password (other devices are signed out) |
| `account/authenticators/...` | Manage TOTP, recovery codes, passkeys |
| `account/email`, `account/providers` | Manage email addresses and linked social accounts |

## Settings

allauth settings (`HEADLESS_*`, `ACCOUNT_*`, `MFA_*`, `SOCIALACCOUNT_*`) are documented by allauth;
`dj_rest_jwt/defaults.py` shows the preset values and why. This package's own settings live in
`DJ_REST_JWT` (see `dj_rest_jwt/conf.py`): `TRANSPORTS`, `DEFAULT_TRANSPORT`, cookie names and
attributes, `REFRESH_REUSE_GRACE_SECONDS`, `ADMIN_LOGIN`, `HONEYPOT_FIELD_NAME`, `CAPTCHA_BACKEND`,
`CAPTCHA_SECRET_KEY`.

## Emails

`email_flows()` in settings picks codes or links for verification and password reset, and turns
on sign-in by emailed code. To edit the emails, copy allauth's templates into your project:

```bash
python manage.py copy_email_templates templates/
```

Add a `<name>_message.html` next to any `<name>_message.txt` to send HTML too.
`demo/backend/templates/account/email/` has a worked example.

## Development

```bash
pip install -e . -r dj_rest_jwt/tests/requirements.txt
python runtests.py
flake8 dj_rest_jwt/
cd js && npm install && npm test
```

Docs are built with [Zensical](https://zensical.org) (`zensical serve`) and published to GitHub
Pages on every push to `main`.

## License

MIT
