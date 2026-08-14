# dj-rest-jwt

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](setup.py)
[![Django](https://img.shields.io/badge/django-4.2%E2%80%936.0-green)](setup.py)

A JWT-first fork of [dj-rest-auth](https://github.com/iMerica/dj-rest-auth) for Django REST
Framework, built so a project gets a *production-ready* auth API - not just login/logout - with
close to zero configuration: JWT by default, working rate limits, anti-spam, SSO, MFA and
passkeys all built in rather than left as homework.

Everything below reflects what's actually implemented and tested in this repo today, not a
roadmap dressed up as a feature list. See [Roadmap](#roadmap) for what's genuinely still missing.

## Why this fork exists

dj-rest-auth is a solid, widely-used package, but it's deliberately provider-agnostic: JWT is one
option among several, nothing is rate-limited unless you wire up DRF's throttle settings yourself,
and there's no anti-spam story at all. That's the right default for a general-purpose library, but
it means every project re-solves the same "make this production-ready" checklist from scratch.

This fork picks opinions:

- **JWT is the only auth method, on by default.** No `REST_FRAMEWORK`/`REST_AUTH` boilerplate
  needed to get stateless, cookie-based JWT auth - see [Quick start](#quick-start) below.
- **Rate limiting works out of the box.** Login, registration, password reset and email
  verification are throttled from the first request, with no `DEFAULT_THROTTLE_RATES` to configure.
- **Anti-spam is built in**, not bolted on: a honeypot field is on by default, and
  Turnstile/reCAPTCHA v3/hCaptcha are one setting away.
- **SSO ships with ready-made Google/GitHub/Microsoft views**, plus the same escape hatch
  dj-rest-auth offers for any other allauth provider.
- **MFA (TOTP) and Passkeys/WebAuthn** are included as opt-in sub-packages.

## Quick start

```bash
pip install dj-rest-jwt
```

```python
# settings.py
INSTALLED_APPS = [
    ...,
    "rest_framework",
    "dj_rest_jwt",
]
```

```python
# urls.py
urlpatterns = [
    path("auth/", include("dj_rest_jwt.urls")),
]
```

That's the whole configuration. No `REST_AUTH` dict, no `rest_framework.authtoken`, no
`DEFAULT_AUTHENTICATION_CLASSES` - `POST /auth/login/` already returns both a JWT access token and
refresh token in the response body, and login/registration are already rate-limited. Set
`JWT_AUTH_COOKIE`/`JWT_AUTH_REFRESH_COOKIE` if you'd rather transport them as httponly cookies
instead (see [Configuration](#configuration-reference)).

| Endpoint | Method | Description |
|---|---|---|
| `/auth/login/` | POST | Log in, returns a JWT access + refresh token |
| `/auth/logout/` | POST | Log out (clears JWT cookies, if configured) |
| `/auth/user/` | GET, PUT, PATCH | Current user's details |
| `/auth/password/change/` | POST | Change password (authenticated) |
| `/auth/password/reset/` | POST | Request a password reset email |
| `/auth/password/reset/confirm/` | POST | Confirm a password reset |
| `/auth/token/verify/` | POST | Verify a JWT |
| `/auth/token/refresh/` | POST | Refresh an access token |

Want DRF token auth or session auth instead? Set `TOKEN_MODEL`/`SESSION_LOGIN`/`USE_JWT` in
`REST_AUTH` to override the defaults - see [Configuration](#configuration-reference).

## Registration & email verification

Registration and email verification are backed by [django-allauth](https://docs.allauth.org/)
and work today, not just in theory - `RegisterView` already calls allauth's signup flow, and
`VerifyEmailView`/`ResendEmailVerificationView` are wired up.

```bash
pip install 'dj-rest-jwt[with-social]'   # pulls in django-allauth
```

```python
# settings.py
INSTALLED_APPS = [
    ...,
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "dj_rest_jwt.registration",
]
SITE_ID = 1
ACCOUNT_EMAIL_VERIFICATION = "mandatory"  # or "optional" / "none"
```

```python
# urls.py
urlpatterns = [
    path("auth/", include("dj_rest_jwt.urls")),
    path("auth/registration/", include("dj_rest_jwt.registration.urls")),
]
```

| Endpoint | Method | Description |
|---|---|---|
| `/auth/registration/` | POST | Register a new user |
| `/auth/registration/verify-email/` | POST | Confirm an email verification key |
| `/auth/registration/resend-email/` | POST | Resend the verification email |

## Anti-spam

A hidden **honeypot field** (`website` by default) is checked on registration out of the box -
no configuration, no external dependency. Bots that blindly fill in every form field trip it;
real users never see it.

For a hosted CAPTCHA challenge, enable it and pick a backend:

```python
REST_AUTH = {
    "ENABLE_CAPTCHA": True,
    "CAPTCHA_BACKEND": "turnstile",  # or "recaptcha_v3" / "hcaptcha"
    "CAPTCHA_SITE_KEY": env("CAPTCHA_SITE_KEY"),
    "CAPTCHA_SECRET_KEY": env("CAPTCHA_SECRET_KEY"),
}
```

**Turnstile is the default** rather than reCAPTCHA: it's free, doesn't depend on Google, and is
usually invisible to the user (no "click all the traffic lights" puzzle). reCAPTCHA v3 and
hCaptcha are available as drop-in alternates via `CAPTCHA_BACKEND` if you'd rather use those.
Once enabled, `RegisterSerializer` requires a validated `captcha_token` field - render the
provider's widget client-side and pass its response token through.

## Rate limiting

Every auth endpoint ships with a sane default rate limit, enforced from dj_rest_jwt's own
settings rather than DRF's `DEFAULT_THROTTLE_RATES` (which most projects never configure, leaving
`throttle_scope` attributes silently inert). Override any of them, or set one to `None` to disable it:

```python
REST_AUTH = {
    "RATE_LIMIT_LOGIN": "10/min",              # login + email verification
    "RATE_LIMIT_REGISTER": "20/hour",          # registration
    "RATE_LIMIT_PASSWORD_RESET": "5/hour",     # password reset + resend-verification email
    "RATE_LIMIT_SENSITIVE_ACTION": "30/hour",  # logout, password change
}
```

## SSO / social login

Google, GitHub and Microsoft ship as ready-made views - no `adapter_class` subclass required:

```python
# settings.py
INSTALLED_APPS = [
    ...,
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.github",
    "allauth.socialaccount.providers.microsoft",
    "dj_rest_jwt.registration",
]
```

Once the corresponding `SocialApp` is configured (via `SOCIALACCOUNT_PROVIDERS` or the Django
admin), these endpoints work immediately:

| Endpoint | Description |
|---|---|
| `/auth/registration/google/login/`, `.../google/connect/` | Google OAuth2 |
| `/auth/registration/github/login/`, `.../github/connect/` | GitHub OAuth2 |
| `/auth/registration/microsoft/login/`, `.../microsoft/connect/` | Microsoft/Entra OAuth2 |

Each accepts either `access_token`/`id_token` (client already obtained a token, e.g. via Google
Identity Services or MSAL) or `code` (server-side authorization code exchange).

Any other allauth provider (Apple, Discord, GitLab, ...) works the same way - see
[`dj_rest_jwt/registration/social_views.py`](dj_rest_jwt/registration/social_views.py), which
doubles as the template: subclass `SocialLoginView`/`SocialConnectView` with that provider's
`adapter_class`.

## MFA (TOTP)

```bash
pip install 'dj-rest-jwt[with-mfa]'
```

```python
INSTALLED_APPS = [..., "dj_rest_jwt.mfa"]
```

```python
urlpatterns = [
    path("auth/", include("dj_rest_jwt.urls")),
    path("auth/", include("dj_rest_jwt.mfa.urls")),
]
```

TOTP activation/deactivation, a login-time verification challenge, and recovery codes - see
[`docs/guides/mfa.md`](docs/guides/mfa.md).

## Passkeys (WebAuthn)

```bash
pip install 'dj-rest-jwt[with-passkeys]'
```

```python
INSTALLED_APPS = [..., "dj_rest_jwt.passkeys"]
REST_AUTH = {
    "PASSKEY_RP_ID": "example.com",
    "PASSKEY_RP_NAME": "Your App",
    "PASSKEY_RP_ORIGINS": ["https://example.com"],
}
```

Passwordless registration/login via Touch ID, Windows Hello, or a hardware security key, plus
credential management (list, rename, delete) - see [`docs/guides/passkeys.md`](docs/guides/passkeys.md).

## Configuration reference

Everything above is configured through a single `REST_AUTH` dict; every key has a working
default. The full list lives in [`dj_rest_jwt/app_settings.py`](dj_rest_jwt/app_settings.py) - the
ones most worth knowing about:

```python
REST_AUTH = {
    # Auth method - JWT-only by default
    "USE_JWT": True,
    "TOKEN_MODEL": None,        # set to 'rest_framework.authtoken.models.Token' for DRF tokens
    "SESSION_LOGIN": False,     # set True to also log in via Django sessions

    # JWT cookies
    "JWT_AUTH_COOKIE": None,            # e.g. "jwt-access"
    "JWT_AUTH_REFRESH_COOKIE": None,    # e.g. "jwt-refresh"
    "JWT_AUTH_HTTPONLY": True,
    "JWT_AUTH_SECURE": False,           # set True in production (HTTPS only)
    "JWT_AUTH_SAMESITE": "Lax",

    # Rate limiting (see above)
    "RATE_LIMIT_LOGIN": "10/min",
    "RATE_LIMIT_REGISTER": "20/hour",
    "RATE_LIMIT_PASSWORD_RESET": "5/hour",
    "RATE_LIMIT_SENSITIVE_ACTION": "30/hour",

    # Anti-spam (see above)
    "ENABLE_HONEYPOT": True,
    "ENABLE_CAPTCHA": False,
    "CAPTCHA_BACKEND": "turnstile",

    # MFA / Passkeys (only take effect if those sub-packages are installed)
    "MFA_TOTP_ISSUER": "",
    "PASSKEY_RP_ID": None,
}
```

## Starter project

`starter/` is a working reference Django project - templates for signup, login, logout, password
reset/change, and email verification, all wired to the API above (including the honeypot field in
action). `starter/react-spa/` is scaffolding only (untouched create-react-app boilerplate, no auth
code yet) - a good first-contribution target if you'd like a JS/SPA reference client.

```bash
cd starter
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Roadmap

Things that are genuinely not implemented yet - not shipped, not partially done, just planned:

- [ ] Session management (list/revoke active sessions from the API)
- [ ] Audit logging of auth events
- [ ] Account deactivation (soft delete)
- [ ] WebAuthn/passkey and MFA UI in the React SPA starter

## Contributing

```bash
pip install -r dj_rest_jwt/tests/requirements.txt
python runtests.py
```

## License

MIT License - see [LICENSE](LICENSE).

## Acknowledgements

Built on top of the excellent [dj-rest-auth](https://github.com/iMerica/dj-rest-auth) (whose
maintainers did the hard work of getting registration, social auth, MFA, and passkeys right) and
[django-allauth](https://github.com/pennersr/django-allauth). This fork narrows the scope to
JWT-only and adds the production-hardening layer (rate limiting, anti-spam, ready-made SSO
providers) on top.
