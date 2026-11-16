# Cookies or headers

Every request picks one of two token transports. Most projects have both kinds of client, so
both are on by default.

| | `cookie` (default) | `header` |
|---|---|---|
| For | Browser SPAs | Native apps, CLIs, server-to-server |
| Client sends | nothing special | `X-Auth-Transport: header` |
| Tokens arrive | in httpOnly cookies, never in the body | in the JSON body (`meta.access_token`, `meta.refresh_token`) |
| Requests carry | the access cookie (automatic) + `X-CSRFToken` on POST/PUT/PATCH/DELETE | `Authorization: Bearer <access>` |
| Refresh | `POST tokens/refresh` with an empty body; the cookie is read | `POST tokens/refresh` with `{"refresh_token": ...}` |
| XSS can steal tokens | no | tokens are wherever the app stores them |

## Why cookies for browsers

A token in `localStorage` is readable by any script on the page, so one XSS bug, or one
compromised npm dependency, leaks it, and a stolen refresh token works from anywhere for 30 days.
An httpOnly cookie can't be read by script at all. The trade-off is CSRF, which Django already
solves: cookie-authenticated unsafe requests must send the `csrftoken` cookie's value in
`X-CSRFToken`, and dj-rest-jwt enforces that on allauth's endpoints and in the DRF
authentication class.

The refresh cookie is scoped to the refresh endpoint's path, so it is only sent there.

## Why headers for apps

Native apps have no cookie jar worth relying on, but they do have secure storage (Keychain,
Android Keystore). They ask for header transport per request and keep the tokens there.

## The two never mix

A header-mode request never reads cookies and never gets cookies set. So a script that sends
`X-Auth-Transport: header` from a browser can't use it to get the tokens out of the cookies: it
gets nothing the cookies were protecting. And a request with an `Authorization` header that
fails validation is not rescued by a cookie.

## Restricting transports

```python title="settings.py"
DJ_REST_JWT = {
    "TRANSPORTS": ("cookie",),        # browser-only project
    # "TRANSPORTS": ("header",),      # API for apps only; no CSRF needed
    "DEFAULT_TRANSPORT": "cookie",
}
```

## Cookie settings

| Setting (`DJ_REST_JWT`) | Default |
|---|---|
| `ACCESS_COOKIE_NAME` / `REFRESH_COOKIE_NAME` | `access_token` / `refresh_token` |
| `COOKIE_SECURE` | `True` (a deploy check warns if off) |
| `COOKIE_SAMESITE` | `"Lax"` |
| `COOKIE_DOMAIN` | `None` (host-only). Set `.example.com` to share with `api.example.com`. |
| `REFRESH_COOKIE_PATH` | the refresh endpoint's path |

## SPA and API on different origins

Easiest is one origin: serve the SPA and proxy `/api` to Django (the demo does this with Vite).
If the API lives on a subdomain, set `COOKIE_DOMAIN`, `CSRF_COOKIE_DOMAIN` and
`CSRF_TRUSTED_ORIGINS`, enable CORS with credentials (e.g. django-cors-headers with
`CORS_ALLOW_CREDENTIALS = True`), and create the JS client with the API's absolute `baseUrl`.
Keep both on the same registrable domain so `SameSite=Lax` still sends the cookies.
