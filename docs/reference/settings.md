# Settings

## The preset

`from dj_rest_jwt.defaults import *` sets these. Override any of them after the import.
[`defaults.py`](https://github.com/memetrusidovski/dj-rest-jwt/blob/main/dj_rest_jwt/defaults.py)
explains each choice.

| Area | Setting | Preset |
|---|---|---|
| Tokens | `HEADLESS_TOKEN_STRATEGY` | `dj_rest_jwt.strategy.JWTTokenStrategy` |
| | `HEADLESS_JWT_ALGORITHM` | `RS256` |
| | `HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN` | `300` (5 min) |
| | `HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN` | `2592000` (30 days, sliding) |
| | `HEADLESS_JWT_ROTATE_REFRESH_TOKEN` | `True` |
| | `HEADLESS_JWT_STATEFUL_VALIDATION_ENABLED` | `True` (instant revocation) |
| Clients | `HEADLESS_ONLY`, `HEADLESS_CLIENTS` | `True`, `("app",)` |
| Sessions | `SESSION_ENGINE` | `cached_db` |
| | `SESSION_COOKIE_AGE` | = refresh lifetime |
| Passwords | `PASSWORD_HASHERS` | Argon2 first |
| | `AUTH_PASSWORD_VALIDATORS` | Django's four, minimum length 10 |
| Accounts | `ACCOUNT_LOGIN_METHODS` | `{"email"}` |
| | `ACCOUNT_SIGNUP_FIELDS` | `["email*", "password1*"]` |
| | `ACCOUNT_EMAIL_VERIFICATION` | `"mandatory"` |
| | email flows | codes for verification and reset; see [`email_flows()`](../guides/emails.md) |
| | `ACCOUNT_PREVENT_ENUMERATION` | `True` |
| | `ACCOUNT_REAUTHENTICATION_REQUIRED` | `True` |
| | `ACCOUNT_EMAIL_NOTIFICATIONS` | `True` |
| | `ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE` | `False` (this device stays signed in; others are signed out) |
| | `ACCOUNT_LOGIN_ON_PASSWORD_RESET` | `False` |
| | `ACCOUNT_RATE_LIMITS` | allauth's defaults |
| MFA | `MFA_SUPPORTED_TYPES` | TOTP, recovery codes, WebAuthn |
| | `MFA_PASSKEY_LOGIN_ENABLED` / `MFA_PASSKEY_SIGNUP_ENABLED` | `True` / `True` |
| Social | `SOCIALACCOUNT_EMAIL_AUTHENTICATION` (+`_AUTO_CONNECT`) | `False` |
| | `SOCIALACCOUNT_LOGIN_ON_GET` | `False` |
| DRF | `REST_FRAMEWORK` | `JWTAuthentication` + `IsAuthenticated` |
| Headers | `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_REFERRER_POLICY`, `X_FRAME_OPTIONS` | on, `same-origin`, `DENY` |

You still set: `HEADLESS_JWT_PRIVATE_KEY`, `HEADLESS_FRONTEND_URLS`, `CACHES`, email delivery,
and the usual production settings (`SECRET_KEY`, `ALLOWED_HOSTS`, HTTPS/HSTS).

## `DJ_REST_JWT`

This package's own settings, all optional:

```python title="settings.py"
DJ_REST_JWT = {
    "TRANSPORTS": ("cookie", "header"),
    "DEFAULT_TRANSPORT": "cookie",
    "ACCESS_COOKIE_NAME": "access_token",
    "REFRESH_COOKIE_NAME": "refresh_token",
    "COOKIE_SECURE": True,
    "COOKIE_SAMESITE": "Lax",
    "COOKIE_DOMAIN": None,
    "REFRESH_COOKIE_PATH": None,          # defaults to the refresh endpoint's path
    "REFRESH_REUSE_GRACE_SECONDS": 10,
    "ADMIN_LOGIN": True,
    "HONEYPOT_FIELD_NAME": "website",
    "CAPTCHA_BACKEND": None,              # "turnstile" | "recaptcha_v3" | "hcaptcha"
    "CAPTCHA_SECRET_KEY": None,
    "CAPTCHA_RECAPTCHA_V3_MIN_SCORE": 0.5,
}
```

## Management commands

| Command | |
|---|---|
| `generate_jwt_key [--bits 2048\|3072\|4096]` | Print a new RSA private key for `HEADLESS_JWT_PRIVATE_KEY` |
| `copy_email_templates DEST [--only NAME ...] [--force]` | Copy allauth's email templates into `DEST` for editing |
