# Security

## Reporting a vulnerability

Please don't open a public issue. Report privately through GitHub's
[security advisory form](https://github.com/memetrusidovski/dj-rest-jwt/security/advisories/new)
with a description, steps to reproduce and the impact. Only test against your own
installations.

Vulnerabilities in authentication logic itself (login, MFA, social providers) usually belong to
[django-allauth](https://github.com/pennersr/django-allauth/security); if you're unsure, report
here and we'll forward it.

## What is protected, and how

| Threat | Protection |
|---|---|
| XSS stealing tokens | Browser tokens live in httpOnly cookies only; never in a response body |
| CSRF with cookie auth | Django's CSRF check on every cookie-authenticated unsafe request, including refresh |
| Stolen refresh token | Rotation on every use; reuse ends the session for everyone holding it |
| Lost device, logout, password change | Server-side session per login, checked on every request: revocation is immediate |
| Credential stuffing, brute force | allauth's rate limits per IP and per account; Argon2 hashing |
| Account enumeration | `ACCOUNT_PREVENT_ENUMERATION`: signup and reset answer the same for known and unknown addresses |
| Social-login account takeover | No sign-in by matching email address |
| Session token leakage | allauth's `session_token` stripped from responses once sign-in completes |
| Header/cookie confusion | Header-transport requests never read or set cookies |
| Admin brute force | Admin sign-in through allauth: rate limits and MFA |
| Weak configuration | System checks; deploy checks for `Secure` cookies and shared caches |
| Signup spam | Honeypot; optional Turnstile/reCAPTCHA/hCaptcha, failing closed |

## Production checklist

- [ ] `python manage.py check --deploy` is clean
- [ ] `HEADLESS_JWT_PRIVATE_KEY` comes from a secret store, not the repository
- [ ] HTTPS everywhere, `SECURE_HSTS_SECONDS` set, `DEBUG = False`
- [ ] `CACHES["default"]` is Redis or Memcached, shared by all processes
- [ ] Email delivery configured, and the frontend handles the pages in `HEADLESS_FRONTEND_URLS`
- [ ] Rotating the JWT key signs everyone out; plan for it
- [ ] A receiver on `dj_rest_jwt.signals.refresh_token_reused` alerts the user or your team
