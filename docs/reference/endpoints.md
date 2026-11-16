# Endpoints

Everything under `/api/auth/v1/` (if mounted at `api/auth/`) is
[allauth's headless API](https://docs.allauth.org/en/latest/headless/openapi-specification/)
for the `app` client, minus the `_allauth/app/` prefix. allauth's OpenAPI spec documents every
request and response shape; the differences here are the token transport and the endpoints
marked **dj-rest-jwt**.

Responses use allauth's envelope: `{"status", "data", "meta", "errors"}`. Auth endpoints answer
`200` when signed in and `401` with `data.flows` otherwise; a flow with `"is_pending": true` is
the next step the user has to complete.

## Authentication

| Method | Path | |
|---|---|---|
| GET | `config` | Enabled features, social providers and their client IDs |
| GET / DELETE | `auth/session` | Current user / sign out (clears cookies) |
| POST | `auth/login` | Password sign-in |
| POST | `auth/signup` | Sign up (plus honeypot/captcha fields) |
| POST | `auth/email/verify`, `auth/email/verify/resend` | Confirm the emailed code (or link key) |
| POST | `auth/code/request`, `auth/code/confirm` | Sign-in by emailed code (`login_code=True`) |
| POST | `auth/2fa/authenticate` | Finish sign-in with TOTP or recovery code |
| GET / POST | `auth/webauthn/authenticate` | Finish sign-in with a passkey as second factor |
| GET / POST | `auth/webauthn/login` | Passkey sign-in |
| POST / GET / PUT | `auth/webauthn/signup` | Passkey-only signup |
| POST | `auth/provider/token` | Social sign-in with a provider ID/access token |
| POST | `auth/password/request` | Request a reset email |
| GET / POST | `auth/password/reset` | Check a reset key (`X-Password-Reset-Key` header) / set the new password |
| POST | `auth/reauthenticate`, `auth/2fa/reauthenticate`, `auth/webauthn/reauthenticate` | Step-up |
| GET / DELETE | `auth/sessions` | List / revoke signed-in devices |
| POST | `tokens/refresh` | **dj-rest-jwt.** New token pair. Cookie transport: empty body, reads the refresh cookie, CSRF required. Header transport: `{"refresh_token"}`. `401` = session over, `409 token_rotated` = a parallel refresh won, retry. |

## Account

| Method | Path | |
|---|---|---|
| POST | `account/password/change` | **dj-rest-jwt override.** Other devices are signed out; this one gets new tokens. |
| GET / POST / PATCH / DELETE / PUT | `account/email` | List, add, make primary, remove, resend verification |
| GET / DELETE | `account/providers` | Linked social accounts |
| GET | `account/authenticators` | All MFA factors |
| GET / POST / DELETE | `account/authenticators/totp` | Set up / activate / remove TOTP |
| GET / POST | `account/authenticators/recovery-codes` | View / regenerate |
| GET / POST / PUT / DELETE | `account/authenticators/webauthn` | Add / rename / remove passkeys |

## Headers

| Header | Direction | |
|---|---|---|
| `X-Auth-Transport: header` | request | Use header transport for this request |
| `Authorization: Bearer <access>` | request | Header transport credential |
| `X-CSRFToken` | request | Cookie transport, unsafe methods |
| `X-Session-Token` | request | allauth's pending-flow token, echoed from `meta.session_token` during multi-step sign-in |

Once sign-in completes, `meta.session_token` is removed from every response: it is the raw
session key and would outlive the access token. In cookie transport, `meta.access_token` and
`meta.refresh_token` are also moved out of the body into cookies.
