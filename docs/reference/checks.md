# System checks

Run with `python manage.py check` (and `check --deploy` for the deploy-only ones). Silence one
deliberately with `SILENCED_SYSTEM_CHECKS`.

## Errors

| ID | Problem |
|---|---|
| `dj_rest_jwt.E001` | `HEADLESS_TOKEN_STRATEGY` is not `dj_rest_jwt.strategy.JWTTokenStrategy` |
| `dj_rest_jwt.E002` | No `HEADLESS_JWT_PRIVATE_KEY` with an RS* algorithm |
| `dj_rest_jwt.E003` | `"app"` missing from `HEADLESS_CLIENTS` |
| `dj_rest_jwt.E004` | `signed_cookies` session engine (sessions are the revocation store; can't work) |
| `dj_rest_jwt.E005` | `TokenTransportMiddleware` not in `MIDDLEWARE` |
| `dj_rest_jwt.E006` | Cookie transport enabled without `CsrfViewMiddleware` |
| `dj_rest_jwt.E007` | allauth's `AccountMiddleware` not in `MIDDLEWARE` |
| `dj_rest_jwt.E008` | `HEADLESS_FRONTEND_URLS` lacks a page your email choices link to |
| `dj_rest_jwt.E009` | `ADMIN_LOGIN` on but `dj_rest_jwt.admin_login` URLs not mounted |

## Warnings

| ID | Problem |
|---|---|
| `dj_rest_jwt.W001` | allauth's cookie-session `browser` client is enabled |
| `dj_rest_jwt.W002` | `HEADLESS_ONLY` is off (allauth's HTML pages are served) |
| `dj_rest_jwt.W003` | Stateless JWT validation: logout and revocation wait for access-token expiry |
| `dj_rest_jwt.W004` | Refresh tokens don't rotate: no "stay signed in", no reuse detection |
| `dj_rest_jwt.W005` | `SESSION_COOKIE_AGE` shorter than the refresh-token lifetime |
| `dj_rest_jwt.W006` | Plain `db` session engine with stateful validation (a DB query per request) |
| `dj_rest_jwt.W007` | `ACCOUNT_RATE_LIMITS = False` |
| `dj_rest_jwt.W008` | First password hasher is not Argon2 or scrypt |
| `dj_rest_jwt.W009` | `SOCIALACCOUNT_EMAIL_AUTHENTICATION` on (account takeover risk) |
| `dj_rest_jwt.W010` | `--deploy`: token cookies not `Secure` |
| `dj_rest_jwt.W011` | `--deploy`: local-memory or dummy cache (rate limits and sessions aren't shared between processes) |
