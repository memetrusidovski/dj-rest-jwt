# Multi-Factor Authentication (MFA)

dj-rest-jwt includes optional TOTP-based MFA with one-time recovery codes. When enabled, users complete login with a second factor from an authenticator app.

## Overview

- **TOTP Authentication**: RFC 6238 time-based one-time passwords
- **Recovery Codes**: backup access if authenticator device is unavailable
- **Headless-first**: clients can render QR codes from `totp_url`
- **Optional server-side QR**: API can return `qr_code_data_uri` when `qrcode` is installed

## Setup

### 1) Install MFA extras

```bash
pip install 'dj-rest-jwt[with-mfa]'
```

`with-mfa` installs TOTP support (`pyotp`).

### 2) Enable app

```python title="settings.py"
INSTALLED_APPS = [
    # ...
    'rest_framework',
    'rest_framework.authtoken',
    'dj_rest_jwt',
    'dj_rest_jwt.mfa',
]
```

### 3) Run migrations

```bash
python manage.py migrate
```

### 4) Use MFA login view and include MFA URLs

```python title="urls.py"
from django.urls import include, path
from dj_rest_jwt.mfa.views import MFALoginView

urlpatterns = [
    path('dj-rest-jwt/login/', MFALoginView.as_view(), name='rest_login'),
    path('dj-rest-jwt/', include('dj_rest_jwt.urls')),
    path('dj-rest-jwt/', include('dj_rest_jwt.mfa.urls')),
]
```

### Optional: server-side QR rendering

```bash
pip install qrcode
```

!!! note
    Without `qrcode`, activation still works. Clients can generate a QR code from `totp_url`.

## Login flow

When MFA is enabled for a user:

1. Client sends username/password to login endpoint.
2. API returns `ephemeral_token` + `mfa_required: true` (instead of full login).
3. Client submits `ephemeral_token` + TOTP (or recovery code) to MFA verify endpoint.
4. API returns normal auth response (token/JWT/session login).

## Endpoints

### Verify MFA

`POST /dj-rest-jwt/mfa/verify/`

Request fields:

- `ephemeral_token`
- `code` (TOTP or recovery code)

### Activate TOTP (step 1)

`GET /dj-rest-jwt/mfa/totp/activate/`

Response fields:

- `secret`
- `totp_url`
- `activation_token`
- `qr_code_data_uri` (empty string when `qrcode` is not installed)

### Activate TOTP (step 2)

`POST /dj-rest-jwt/mfa/totp/activate/`

Request fields:

- `activation_token`
- `code`

Response fields:

- `recovery_codes`

### Deactivate TOTP

`POST /dj-rest-jwt/mfa/totp/deactivate/`

Request fields:

- `code`

Response:

- `detail`

### Status

`GET /dj-rest-jwt/mfa/status/`

Response fields:

- `mfa_enabled`
- `created_at`
- `last_used_at`

### Recovery codes

- `GET /dj-rest-jwt/mfa/recovery-codes/` - how many are left: `{"remaining": 8}`
- `POST /dj-rest-jwt/mfa/recovery-codes/regenerate/` - rotate all codes

Codes are shown **once**, in the response that generates them (TOTP activation,
or regeneration). Only their SHA-256 hashes are stored, so there is no endpoint
that can list them again - show them to the user at generation time and tell
them to save them.

Regenerating requires step-up re-authentication, because a new set of codes is a
new set of permanent MFA bypasses:

```json
POST /dj-rest-jwt/mfa/recovery-codes/regenerate/
{"password": "the-user-s-current-password"}
```

A current TOTP or recovery `code` works in place of the password, which matters
for accounts that sign in through a social provider and have no usable password.

## Security behavior

- the verify endpoint is rate limited by `RATE_LIMIT_MFA_VERIFY` (default
  `5/min`), bucketed by the ephemeral token as well as by IP so that rotating
  source addresses doesn't buy extra guesses at a 6-digit code
- `ephemeral_token` expires after `MFA_EPHEMERAL_TOKEN_TIMEOUT` (default 300s)
  and is single-use - it is redeemed the moment a correct code is presented
  (a wrong code doesn't burn it, so typos don't force a re-login)
- TOTP codes cannot be replayed: accepting a code burns its time step and every
  earlier one, under a row lock, so neither a captured code nor two racing
  requests can be used twice
- TOTP secrets are encrypted at rest with a key derived from `SECRET_KEY`
  (requires `cryptography`; see `MFA_ENCRYPT_SECRETS`)
- recovery codes are stored as hashes; usage is atomic and one-time
- MFA is enforced on **every** login path - password, social, and passkey - not
  just the password one
- activation requires a signed, user-bound `activation_token`
- sensitive MFA events are logged via the `dj_rest_jwt.mfa` logger

### Upgrading an existing install

Secrets and recovery codes written by earlier versions are read transparently:
legacy signed TOTP secrets still work and are re-written encrypted the next time
a code is verified, and seed-derived recovery codes keep validating until the
user regenerates. Nobody gets locked out.

## Settings

Configure via `REST_AUTH`:

```python title="settings.py"
REST_AUTH = {
    'MFA_EPHEMERAL_TOKEN_TIMEOUT': 300,
    'MFA_TOTP_DIGITS': 6,
    'MFA_TOTP_PERIOD': 30,
    'MFA_TOTP_ISSUER': '',
    'MFA_RECOVERY_CODE_COUNT': 10,
    'MFA_TOTP_VALID_WINDOW': 1,
    'MFA_ENCRYPT_SECRETS': True,
    'RATE_LIMIT_MFA_VERIFY': '5/min',
    'RATE_LIMIT_CREDENTIAL_ACTION': '20/hour',
    'REQUIRE_REAUTH_FOR_CREDENTIAL_CHANGES': True,
}
```
