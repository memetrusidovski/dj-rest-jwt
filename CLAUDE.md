# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

dj-rest-jwt is an API/JWT-first security layer over **django-allauth headless**. allauth does the
authentication itself (login, signup, email verification, MFA, passkeys, social login, sessions, JWT
minting and rotation). This package only adds what an API-first project still needs on top of it.
Prefer an allauth feature or setting over new code here; only add code where allauth has no hook.

Requires Python 3.12+, Django 6.0+, django-allauth 65.22–65.x (pinned because `strategy.py` uses
allauth's non-public `headless.tokens.strategies.jwt.internal`).

## Common Commands

```bash
python runtests.py                                        # all tests
python runtests.py dj_rest_jwt.tests.test_tokens          # one module
python runtests.py dj_rest_jwt.tests.test_tokens.SessionTests.test_pending_login_token_is_dead_once_login_completes
coverage run ./runtests.py && coverage report
flake8 dj_rest_jwt/
tox                                                       # py3.12–3.14 × Django 6.0/6.1
pip install -e . -r dj_rest_jwt/tests/requirements.txt    # dev setup
```

## Architecture (`dj_rest_jwt/`)

- **`transport.py`** — Per-request token transport. `cookie` (default; browser SPAs): tokens only in
  httpOnly cookies, CSRF on unsafe methods. `header` (client sends `X-Auth-Transport: header`; native
  apps): tokens in JSON body, `Authorization: Bearer`. The two never mix: header-mode requests never
  read or set cookies. Cookie helpers and the CSRF check live here.
- **`strategy.py`** — `JWTTokenStrategy`, subclass of allauth's (set as `HEADLESS_TOKEN_STRATEGY`).
  Adds the access cookie as a credential for allauth's own views, and refresh-token reuse detection
  (reuse after `REFRESH_REUSE_GRACE_SECONDS` ends the session and sends `signals.refresh_token_reused`).
- **`middleware.py`** — `TokenTransportMiddleware`. Post-processes every response in the `headless`
  URL namespace: tokens in `meta` → cookies (cookie mode), always strips `session_token` once JWTs are
  issued, clears cookies on `DELETE auth/session`.
- **`urls.py`** — allauth's app-client URL tree (`build_urlpatterns(Client.APP)`) without the
  `_allauth/app/` prefix, plus our overrides placed first in the same `headless` namespace.
- **`views.py`** — `TokenRefreshView` (refresh from cookie or body) and `ChangePasswordView` (re-mints
  tokens for the changing device, since Django rotates the session key on password change).
- **`authentication.py`** — DRF `JWTAuthentication`: Bearer header or access cookie (+CSRF).
- **`admin_login.py`** — Admin sign-in via allauth (rate limits + MFA). `apps.py` wraps
  `admin.site.login` on startup when `DJ_REST_JWT["ADMIN_LOGIN"]` (default on).
- **`signup.py`** — `ACCOUNT_SIGNUP_FORM_CLASS` adding honeypot + optional captcha
  (turnstile/recaptcha_v3/hcaptcha, fails closed) to allauth's signup, headless included.
- **`defaults.py`** — The secure settings preset (`from dj_rest_jwt.defaults import *`), plus
  `DJ_REST_JWT_APPS` / `DJ_REST_JWT_MIDDLEWARE` lists.
- **`checks.py`** — System checks `dj_rest_jwt.E0xx/W0xx` enforcing the preset; deploy checks under
  `check --deploy`.
- **`conf.py`** — Our own settings, read from the `DJ_REST_JWT` dict.
- **`management/commands/generate_jwt_key.py`** — Prints an RSA key for `HEADLESS_JWT_PRIVATE_KEY`.
- **`management/commands/copy_email_templates.py`** — Copies allauth's email templates into a project for editing.
- **`defaults.email_flows()`** — Picks code vs link for verification/reset and login-by-code; `checks.E008`
  requires only the frontend URLs those choices need.

## Other parts of the repo

- **`js/`** — `dj-rest-jwt-client` (TypeScript, no runtime deps; `react` subpath export). Refresh on 401 with
  single-flight + Web Locks across tabs, BroadcastChannel sign-in/out sync, CSRF / Bearer, pending-flow
  `X-Session-Token`, passkeys. `npm test` (unit); `test/e2e.test.ts` runs against the demo backend (see
  docs/contributing.md).
- **`demo/`** — `backend/` (Django on the preset, example HTML email templates) + `spa/` (Vite + React on the
  JS client, proxying `/api` to Django).
- **`docs/`** — Zensical site (`zensical.toml`), deployed to GitHub Pages by `.github/workflows/docs.yml`.
- **`starter/`** — Not yet ported to the new architecture.

### Key facts about allauth's JWT model

- Each JWT login is backed by a server-side Django session (the token's `sid` is the encrypted
  session key). Sessions are the revocation store, never a client credential (admin excepted).
  `signed_cookies` session engine cannot work; `cached_db` is the preset.
- Refresh re-saves the session, so `SESSION_COOKIE_AGE >= HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN` gives
  a sliding "stay signed in" window.
- allauth puts `session_token` (the raw session key) in response `meta`; it must never reach clients
  after login, hence the middleware strip.
- Sensitive actions (adding a passkey/TOTP, password change) need a recent explicit
  `auth/reauthenticate`; a fresh login does not count.

## Testing (`dj_rest_jwt/tests/`)

- `settings.py` builds on `dj_rest_jwt.defaults` (generates a throwaway RSA key, MD5 hasher for speed).
- `helpers.py` — `Api` client (cookie or `header=True` transport, CSRF enforced), `VerifyingDevice`
  (soft WebAuthn authenticator with the UV flag), TOTP/Google helpers.
- Tests are end-to-end over HTTP. Security-relevant code paths are expected to have a test that fails
  when the protection is removed.

## Code Style

flake8, max line length 120 (`setup.cfg`).
