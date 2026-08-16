# API Endpoints

Complete reference for all dj-rest-jwt endpoints.

## Authentication Endpoints

### Login

Authenticate a user and obtain a token or JWT.

```
POST /dj-rest-jwt/login/
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | Yes* | Username |
| `email` | string | Yes* | Email address |
| `password` | string | Yes | Password |

*Either `username` or `email` is required, depending on your allauth configuration.

=== "Token Auth Response"

    ```json
    {
        "key": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
    }
    ```

=== "JWT Response"

    ```json
    {
        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "user": {
            "pk": 1,
            "username": "testuser",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User"
        }
    }
    ```

=== "JWT with Expiration"

    When `JWT_AUTH_RETURN_EXPIRATION = True`:

    ```json
    {
        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "access_expiration": "2026-02-15T12:30:00Z",
        "refresh_expiration": "2026-02-22T12:00:00Z",
        "user": {
            "pk": 1,
            "username": "testuser",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User"
        }
    }
    ```

**Error Responses:**

```json
// 400 Bad Request - Invalid credentials
{
    "non_field_errors": ["Unable to log in with provided credentials."]
}

// 400 Bad Request - Missing fields
{
    "password": ["This field is required."]
}
```

---

### Logout

Revoke the authentication token and/or clear JWT cookies.

```
POST /dj-rest-jwt/logout/
```

**Request Headers:**

| Header | Value |
|--------|-------|
| `Authorization` | `Token {key}` or `Bearer {jwt}` |

**Response:**

```json
{
    "detail": "Successfully logged out."
}
```

!!! note "GET Method"
    To allow logout via GET request, set `ACCOUNT_LOGOUT_ON_GET = True` in your Django settings. This is **not recommended** for security reasons.

!!! tip "JWT Blacklisting"
    If using JWT with `rest_framework_simplejwt.token_blacklist` in `INSTALLED_APPS`, the refresh token will be blacklisted on logout.

---

### User Details

Retrieve or update the authenticated user's information.

```
GET /dj-rest-jwt/user/
PUT /dj-rest-jwt/user/
PATCH /dj-rest-jwt/user/
```

**Request Headers:**

| Header | Value |
|--------|-------|
| `Authorization` | `Token {key}` or `Bearer {jwt}` |

**GET Response:**

```json
{
    "pk": 1,
    "username": "testuser",
    "email": "test@example.com",
    "first_name": "Test",
    "last_name": "User"
}
```

**PUT/PATCH Request Body:**

| Field | Type | Description |
|-------|------|-------------|
| `username` | string | Username (if allowed) |
| `first_name` | string | First name |
| `last_name` | string | Last name |

!!! note "Read-only Fields"
    By default, `pk` and `email` are read-only. To customize which fields are editable, override the `USER_DETAILS_SERIALIZER`.

---

## Password Management

### Password Reset

Request a password reset email.

```
POST /dj-rest-jwt/password/reset/
```

**Request Body:**

```json
{
    "email": "user@example.com"
}
```

**Response:**

```json
{
    "detail": "Password reset e-mail has been sent."
}
```

!!! warning "Security Note"
    The response is always successful even if the email doesn't exist, to prevent email enumeration attacks.

---

### Password Reset Confirm

Complete the password reset using the token from the email.

```
POST /dj-rest-jwt/password/reset/confirm/
```

**Request Body:**

```json
{
    "uid": "MQ",
    "token": "c5p4t0-a1b2c3d4e5f6g7h8i9j0",
    "new_password1": "newSecurePassword123",
    "new_password2": "newSecurePassword123"
}
```

**Response:**

```json
{
    "detail": "Password has been reset with the new password."
}
```

**Error Response:**

```json
// 400 Bad Request - Invalid token
{
    "token": ["Invalid value"]
}

// 400 Bad Request - Passwords don't match
{
    "new_password2": ["The two password fields didn't match."]
}
```

---

### Password Change

Change password for authenticated user.

```
POST /dj-rest-jwt/password/change/
```

**Request Headers:**

| Header | Value |
|--------|-------|
| `Authorization` | `Token {key}` or `Bearer {jwt}` |

**Request Body:**

```json
{
    "old_password": "currentPassword",
    "new_password1": "newSecurePassword123",
    "new_password2": "newSecurePassword123"
}
```

!!! note "Old Password Field"
    The `old_password` field is only required when `OLD_PASSWORD_FIELD_ENABLED = True`.

**Response:**

```json
{
    "detail": "New password has been saved."
}
```

---

## JWT Endpoints

These endpoints are only available when `USE_JWT = True`.

### Token Verify

Verify that a JWT token is valid.

```
POST /dj-rest-jwt/token/verify/
```

**Request Body:**

```json
{
    "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Response:**

- `200 OK` - Token is valid (empty response body)
- `401 Unauthorized` - Token is invalid or expired

```json
{
    "detail": "Token is invalid or expired",
    "code": "token_not_valid"
}
```

---

### Token Refresh

Obtain a new access token using a refresh token.

```
POST /dj-rest-jwt/token/refresh/
```

**Request Body:**

```json
{
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

!!! tip "Cookie-based Refresh"
    When using `JWT_AUTH_HTTPONLY = True`, the refresh token is automatically read from cookies. No request body needed.

**Response:**

```json
{
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

---

## Registration Endpoints

These endpoints require `dj_rest_jwt.registration` in `INSTALLED_APPS`.

### Register

Create a new user account.

```
POST /dj-rest-jwt/registration/
```

**Request Body:**

```json
{
    "username": "newuser",
    "email": "newuser@example.com",
    "password1": "securePassword123",
    "password2": "securePassword123"
}
```

**Response:**

=== "Token Auth"

    ```json
    {
        "key": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
    }
    ```

=== "JWT"

    ```json
    {
        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
        "user": {
            "pk": 2,
            "username": "newuser",
            "email": "newuser@example.com",
            "first_name": "",
            "last_name": ""
        }
    }
    ```

**Error Response:**

```json
// 400 Bad Request
{
    "username": ["A user with that username already exists."],
    "email": ["A user is already registered with this e-mail address."],
    "password1": ["This password is too common."]
}
```

---

### Verify Email

Verify user's email address using the key from verification email.

```
POST /dj-rest-jwt/registration/verify-email/
```

**Request Body:**

```json
{
    "key": "MjQ6YzVwNHQwLWExYjJjM2Q0ZTVmNmc3aDhpOWow"
}
```

**Response:**

```json
{
    "detail": "ok"
}
```

!!! note "Email Verification URL"
    You need to configure the email verification URL in your frontend. Add this to your `urls.py`:

    ```python
    from dj_rest_jwt.registration.views import VerifyEmailView

    urlpatterns = [
        # ...
        path(
            'api/auth/account-confirm-email/',
            VerifyEmailView.as_view(),
            name='account_email_verification_sent'
        ),
    ]
    ```

---

### Resend Email Verification

Resend the email verification link.

```
POST /dj-rest-jwt/registration/resend-email/
```

**Request Body:**

```json
{
    "email": "user@example.com"
}
```

**Response:**

```json
{
    "detail": "ok"
}
```

---

## Social Authentication Endpoints

See [Social Authentication Guide](../guides/social-auth.md) for setup instructions.

### Social Login

Authenticate using an OAuth provider.

```
POST /dj-rest-jwt/{provider}/
```

**Request Body:**

| Field | Type | Description |
|-------|------|-------------|
| `access_token` | string | OAuth access token |
| `code` | string | OAuth authorization code |
| `id_token` | string | OpenID Connect ID token (some providers) |

!!! note "Provider-specific Fields"
    Different providers may require different fields. See the [Social Auth Guide](../guides/social-auth.md) for provider-specific examples.

!!! warning "Bare access tokens are audience-checked"
    An `access_token` on its own carries no proof of which OAuth application it
    was issued to, so anyone holding a token minted for *any* client could
    otherwise sign in as its owner. dj-rest-jwt verifies the token's audience
    with the provider before trusting it, and rejects providers where that isn't
    possible. See [Social Authentication](../guides/social-auth.md#access-token-verification).

Ready-made views ship for Google, GitHub, Microsoft and Apple:

```
POST /dj-rest-jwt/registration/google/login/
POST /dj-rest-jwt/registration/github/login/
POST /dj-rest-jwt/registration/microsoft/login/
POST /dj-rest-jwt/registration/apple/login/
```

with a matching `.../connect/` endpoint for each, to link a provider account to
an already-authenticated user.

---

## MFA Endpoints

See [MFA Guide](../guides/mfa.md) for setup, login flow, and endpoint contracts.

### MFA Verify

```
POST /dj-rest-jwt/mfa/verify/
```

### TOTP Activate

```
GET /dj-rest-jwt/mfa/totp/activate/
POST /dj-rest-jwt/mfa/totp/activate/
```

### TOTP Deactivate

```
POST /dj-rest-jwt/mfa/totp/deactivate/
```

### MFA Status

```
GET /dj-rest-jwt/mfa/status/
```

### Recovery Codes

```
GET  /dj-rest-jwt/mfa/recovery-codes/
POST /dj-rest-jwt/mfa/recovery-codes/regenerate/
```

`GET` returns only `{"remaining": <int>}`. Codes are stored as hashes and shown
exactly once, when they are generated - there is nothing to hand back.

`regenerate` returns a fresh set in `codes` and invalidates the previous ones. It
requires step-up re-authentication: send `password` (or a current second-factor
`code`) alongside the request.

---

## Passkey Endpoints

These endpoints require `dj_rest_jwt.passkeys` in `INSTALLED_APPS`. See [Passkeys Guide](../guides/passkeys.md) for setup and flow details.

### Passkey Register Begin

```
POST /dj-rest-jwt/passkeys/register/begin/
```

Authentication required. Returns WebAuthn `PublicKeyCredentialCreationOptions`.

### Passkey Register Complete

```
POST /dj-rest-jwt/passkeys/register/complete/
```

Authentication required, plus step-up re-authentication: send `password` (or a
current second-factor `code`) alongside `credential`. Verifies and stores the
credential (201 Created).

### Passkey Login Begin

```
POST /dj-rest-jwt/passkeys/login/begin/
```

No authentication required. Returns WebAuthn `PublicKeyCredentialRequestOptions` + `session_id`.

### Passkey Login Complete

```
POST /dj-rest-jwt/passkeys/login/complete/
```

No authentication required. Verifies the assertion and returns a standard auth response.

### List Passkeys

```
GET /dj-rest-jwt/passkeys/
```

Authentication required. Returns all passkeys for the authenticated user.

### Passkey Detail

```
GET    /dj-rest-jwt/passkeys/{id}/
PATCH  /dj-rest-jwt/passkeys/{id}/
DELETE /dj-rest-jwt/passkeys/{id}/
```

Authentication required. Retrieve, rename, or delete an individual passkey.

`DELETE` also requires step-up re-authentication - send `password` (or a current
second-factor `code`) in the request body.

---

## Response Status Codes

| Code | Description |
|------|-------------|
| `200 OK` | Request successful |
| `201 Created` | Resource created (registration) |
| `204 No Content` | Request successful, no response body |
| `400 Bad Request` | Invalid request data |
| `401 Unauthorized` | Authentication required or failed |
| `403 Forbidden` | Permission denied |
| `404 Not Found` | Resource not found |
| `429 Too Many Requests` | Rate limit exceeded |

---

## Throttling

Every auth endpoint is rate limited out of the box, from dj-rest-jwt's own
settings rather than DRF's `DEFAULT_THROTTLE_RATES`. There is nothing to wire up
and no `ScopedRateThrottle` to register.

```python title="settings.py"
REST_AUTH = {
    'RATE_LIMIT_LOGIN': '10/min',
    'RATE_LIMIT_REGISTER': '20/hour',
    'RATE_LIMIT_PASSWORD_RESET': '5/hour',
    'RATE_LIMIT_SENSITIVE_ACTION': '30/hour',   # logout, password change, reads
    'RATE_LIMIT_MFA_VERIFY': '5/min',           # second-factor code submission
    'RATE_LIMIT_CREDENTIAL_ACTION': '20/hour',  # enrolling/removing MFA or a passkey
    'RATE_LIMIT_PASSKEY_CHALLENGE': '20/min',   # unauthenticated WebAuthn challenges
}
```

Set any of them to `None` to disable throttling for that group of endpoints.

`RATE_LIMIT_MFA_VERIFY` buckets by the ephemeral token as well as by IP, so
rotating source addresses doesn't buy an attacker extra guesses at one account's
6-digit code.

To apply a different limit to a specific view, set `throttle_classes` on it -
note that a bare `throttle_scope` attribute does nothing unless your project has
also registered DRF's `ScopedRateThrottle`:

```python title="views.py"
from dj_rest_jwt.throttling import ConfigurableRateThrottle
from dj_rest_jwt.views import LoginView


class StrictLoginThrottle(ConfigurableRateThrottle):
    scope = 'myapp_strict_login'
    rate_setting_name = 'RATE_LIMIT_LOGIN'


class StrictLoginView(LoginView):
    throttle_classes = (StrictLoginThrottle,)
```
