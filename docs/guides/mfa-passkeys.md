# MFA and passkeys

The preset turns on allauth's MFA with all three factor types:

```python
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes", "webauthn"]
MFA_PASSKEY_LOGIN_ENABLED = True       # "Sign in with a passkey"
MFA_PASSKEY_SIGNUP_ENABLED = True      # signup without a password (needs code verification)
```

## Sign-in with a second factor

When a user with TOTP or a passkey signs in with a password (or a social account), the login
answers `401` with a pending `mfa_authenticate` flow. The client finishes it with
`POST auth/2fa/authenticate {"code": ...}` (TOTP or recovery code) or with a passkey via
`auth/webauthn/authenticate`. Only then are tokens issued; the short-lived pending state is
carried by `X-Session-Token` and is useless once login completes.

## Setting up TOTP

1. `GET account/authenticators/totp` answers `404` with `meta.secret` and `meta.totp_url`
   (render the URL as a QR code).
2. `POST account/authenticators/totp {"code": ...}` with the first code activates it. Recovery
   codes are generated at the same time: show them with
   `GET account/authenticators/recovery-codes`.

## Passkeys

- Sign in: `GET auth/webauthn/login` → browser prompt → `POST auth/webauthn/login`.
- Add to an account: `GET account/authenticators/webauthn?passwordless` →
  browser prompt → `POST account/authenticators/webauthn`.
- Passkey-only signup: `POST auth/webauthn/signup {"email"}` → verify the emailed code →
  `GET`/`PUT auth/webauthn/signup`.

The JS client's `loginWithPasskey()`, `addPasskey()` and `startPasskeySignup()` /
`finishPasskeySignup()` do the whole round trip including the browser prompt.

WebAuthn is bound to your domain: allauth derives the relying party from the request, so serve
the SPA and the API from the same site. Over plain `http://localhost` in development set
`MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = True` (never in production).

## Step-up

Adding or removing a factor, viewing recovery codes and changing the password require a recent
**explicit** re-authentication (`ACCOUNT_REAUTHENTICATION_REQUIRED = True`). A fresh login does not
count. These endpoints answer `401` with a pending `reauthenticate` flow; the client calls
`POST auth/reauthenticate {"password"}` (or `auth/2fa/reauthenticate`) and retries.

## Notifications

With `ACCOUNT_EMAIL_NOTIFICATIONS = True` (preset) the user is emailed when a factor is added or
removed. See [emails](emails.md) to edit them.
