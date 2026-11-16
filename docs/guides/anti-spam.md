# Signup anti-spam

Both run inside allauth's signup form (`ACCOUNT_SIGNUP_FORM_CLASS = "dj_rest_jwt.signup.SignupForm"`,
set by the preset), so they apply to `POST auth/signup` without any extra views.

## Honeypot (on by default)

`POST auth/signup` accepts an extra field, `website` by default, that must stay empty. Render it
in your signup form but hide it from people (off-screen, `tabIndex={-1}`, `aria-hidden`); naive
bots fill in every field and get rejected. Rename it with `DJ_REST_JWT["HONEYPOT_FIELD_NAME"]`.

## Captcha (optional)

```python title="settings.py"
DJ_REST_JWT = {
    "CAPTCHA_BACKEND": "turnstile",          # or "recaptcha_v3", "hcaptcha"
    "CAPTCHA_SECRET_KEY": os.environ["CAPTCHA_SECRET_KEY"],
    # "CAPTCHA_RECAPTCHA_V3_MIN_SCORE": 0.5,
}
```

The client must then send `captcha_token` (from the widget) with the signup. Verification fails
closed: if the provider can't be reached, signup is refused.

## Rate limits

allauth rate-limits signup, login, failed logins (per IP and per account), password reset and
code entry out of the box (`ACCOUNT_RATE_LIMITS`). The preset keeps those defaults; the
`dj_rest_jwt.W007` check warns if you turn them off. They use Django's cache, so a shared cache
is required with more than one server process.
