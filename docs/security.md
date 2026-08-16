# Security

## Vulnerability Disclosure Policy

Please observe standard best practices of responsible disclosure when reporting security vulnerabilities.

See OWASP's [Vulnerability Disclosure Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Vulnerability_Disclosure_Cheat_Sheet.html) for guidance.

### Reporting a Vulnerability

1. **Do not** open a public GitHub issue for security vulnerabilities
2. **Report privately** through GitHub's [security advisory form](https://github.com/memetrusidovski/dj-rest-jwt/security/advisories/new)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- Acknowledgment within 48 hours
- Regular updates on progress
- Credit in the security advisory (unless you prefer anonymity)

### Guidelines

- **Keep it legal** - Only test against your own installations
- **Respect privacy** - Don't access or modify other users' data
- **Be patient** - Security fixes take time to develop and test properly

---

## Security Best Practices

### JWT Configuration

```python title="settings.py (Production)"
REST_AUTH = {
    'USE_JWT': True,
    'JWT_AUTH_COOKIE': 'access',
    'JWT_AUTH_REFRESH_COOKIE': 'refresh',
    'JWT_AUTH_HTTPONLY': True,       # Prevent XSS
    'JWT_AUTH_SECURE': True,          # HTTPS only
    'JWT_AUTH_SAMESITE': 'Lax',       # CSRF protection
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5),   # Short-lived
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}
```

### Rate Limiting

Every auth endpoint is rate limited from the first request - there is nothing to
turn on. Tune the limits in `REST_AUTH`, not in DRF's `DEFAULT_THROTTLE_RATES`:

```python title="settings.py"
REST_AUTH = {
    'RATE_LIMIT_LOGIN': '10/min',
    'RATE_LIMIT_REGISTER': '20/hour',
    'RATE_LIMIT_PASSWORD_RESET': '5/hour',
    'RATE_LIMIT_SENSITIVE_ACTION': '30/hour',
    'RATE_LIMIT_MFA_VERIFY': '5/min',
    'RATE_LIMIT_CREDENTIAL_ACTION': '20/hour',
    'RATE_LIMIT_PASSKEY_CHALLENGE': '20/min',
}
```

Throttle state lives in Django's cache, so use a shared backend (Redis,
Memcached) if you run more than one process - the default per-process
`LocMemCache` multiplies every limit by your worker count.

### Token revocation

Changing or resetting a password blacklists the user's outstanding refresh
tokens, so the "I think I've been compromised" flow actually evicts whoever else
is holding one. This needs somewhere to record the revocation:

```python title="settings.py"
INSTALLED_APPS = [
    # ...
    'rest_framework_simplejwt.token_blacklist',
]

REST_AUTH = {
    'REVOKE_TOKENS_ON_PASSWORD_CHANGE': True,  # default
}
```

This also deletes the user's DRF `authtoken` key if you use one, since those
never expire on their own. Clients get a fresh credential by logging in again.

Access tokens already in flight can't be individually revoked and stay valid
until they expire, which is the argument for a short `ACCESS_TOKEN_LIFETIME`.

`manage.py check` warns if revocation is on without the blacklist app installed.

### Step-up re-authentication

Enrolling a passkey, removing one, or regenerating recovery codes creates or
destroys a credential that outlives the access token used to do it. These
endpoints require the caller to re-prove who they are with `password` or a
current second-factor `code`. Note that a `code` used this way is consumed - a
TOTP code burns its time step, and a recovery code is spent - so prefer the
password where the account has one:

```python title="settings.py"
REST_AUTH = {
    'REQUIRE_REAUTH_FOR_CREDENTIAL_CHANGES': True,  # default
}
```

### Social login token substitution

A raw provider `access_token` doesn't prove which OAuth application it was
issued to. dj-rest-jwt verifies that with the provider before trusting it - see
[Access token verification](guides/social-auth.md#access-token-verification).

### Password Validation

Use Django's password validators:

```python title="settings.py"
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
```

### HTTPS

Always use HTTPS in production:

```python title="settings.py"
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

---

## Known Security Considerations

### Email Enumeration

By design, the password reset endpoint always returns a success response, even
for non-existent emails. The login endpoint runs the password hasher even when
no account matches, so response timing doesn't reveal which addresses are
registered either.

Registration is the exception: it has to tell the caller that an email or
username is already taken, so it necessarily confirms existence. If that matters
for your threat model, override `RegisterSerializer` to accept the signup and
send a "this address is already registered" email instead.

### Token Storage

- **DO**: Store tokens in HTTP-only cookies
- **DON'T**: Store tokens in localStorage or sessionStorage (XSS vulnerable)

### CORS

Be restrictive with CORS origins in production:

```python title="settings.py"
CORS_ALLOWED_ORIGINS = [
    'https://yourapp.com',  # Specific domains only
]
CORS_ALLOW_CREDENTIALS = True
```

---

## Security Updates

Security updates are released as patch versions. Always keep dj-rest-jwt updated:

```bash
pip install --upgrade dj-rest-jwt
```

Subscribe to [GitHub releases](https://github.com/iMerica/dj-rest-jwt/releases) for security announcements.
