# Staying signed in

## The model

| Token | Lifetime (preset) | Setting |
|---|---|---|
| Access | 5 minutes | `HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN` |
| Refresh | 30 days, sliding | `HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN` |

Every refresh returns a **new** refresh token with a fresh 30-day lifetime
(`HEADLESS_JWT_ROTATE_REFRESH_TOKEN = True`) and re-saves the server-side session. So a user who
opens the app at least once every 30 days stays signed in indefinitely, while a device that
goes quiet for 30 days is signed out. `SESSION_COOKIE_AGE` must be at least the refresh
lifetime; a system check enforces it.

Each login is backed by a server-side session (the token's `sid` claim). With stateful
validation (`HEADLESS_JWT_STATEFUL_VALIDATION_ENABLED = True`, the preset) every access token is
checked against it, so these take effect on the very next request, not after 5 minutes:

- signing out (`DELETE auth/session`)
- revoking a device (`DELETE auth/sessions`)
- changing the password: all other devices are signed out; the device that made the change gets
  a fresh token pair and stays signed in
- refresh-token reuse (below)

The cost is one session lookup per request, which is why the preset uses the `cached_db` session
engine. Point `CACHES["default"]` at Redis or Memcached in production.

## Refresh-token reuse detection

A refresh token can be used once. If a token that was already rotated comes back, either the
legitimate client or an attacker has a copy it shouldn't. dj-rest-jwt ends the whole session,
which cuts off both, logs a warning to the `dj_rest_jwt.security` logger, and sends the
`dj_rest_jwt.signals.refresh_token_reused` signal (`user_id`, `request`) so you can alert the
user.

```python
from django.dispatch import receiver
from dj_rest_jwt.signals import refresh_token_reused

@receiver(refresh_token_reused)
def alert(sender, user_id, request, **kwargs):
    ...
```

## Parallel refreshes

Two tabs, or two requests, may refresh with the same token at the same moment. The second one
arrives with a token that was rotated milliseconds ago. Within `REFRESH_REUSE_GRACE_SECONDS`
(default 10) that is not treated as theft: the endpoint answers `409 token_rotated`, leaves the
cookies alone, and the client retries with the new tokens. The JS client also serializes
refreshes across tabs, so this rarely happens at all.

## Listing and revoking devices

`GET auth/sessions` lists the user's signed-in devices (IP, user agent, last seen);
`DELETE auth/sessions {"sessions": [ids]}` signs them out. This is allauth's `usersessions` app,
included in the preset.
