# Emails: codes, links, templates

## Codes or links

One call in `settings.py` picks how each email flow works:

```python title="settings.py"
from dj_rest_jwt.defaults import *  # noqa

globals().update(email_flows(
    verification="code",     # or "link"
    password_reset="code",   # or "link"
    login_code=False,        # True: also offer passwordless sign-in by emailed code
))
```

| | Code (preset) | Link |
|---|---|---|
| Email contains | a short code, e.g. `VTBX-WMQP` | a link to your frontend |
| User | types it into the open app | clicks; your page posts the key back |
| Works across devices | yes (mail on the phone, app on the laptop) | only on the device that opens the mail |
| Email scanners that pre-open links | harmless | can consume single-use links |
| Frontend routes needed | none | `/verify-email/{key}`, `/reset-password/{key}` |

!!! note "Magic links"
    allauth has no "magic link" sign-in. `login_code=True` is its equivalent: the user enters
    an email address and gets a sign-in code. It's safer than a link for the reasons above.

With `verification="link"`, passkey-only signup is switched off (it needs code verification).

`HEADLESS_FRONTEND_URLS` tells allauth where your frontend handles each link. The
`dj_rest_jwt.E008` check lists the ones your choices need:

```python
HEADLESS_FRONTEND_URLS = {
    "account_reset_password": "https://app.example.com/forgot-password",   # always
    "account_signup": "https://app.example.com/signup",                    # always
    "account_confirm_email": "https://app.example.com/verify-email/{key}",              # link mode
    "account_reset_password_from_key": "https://app.example.com/reset-password/{key}",  # link mode
}
```

Code lifetimes and attempt limits are allauth settings: `ACCOUNT_EMAIL_VERIFICATION_BY_CODE_TIMEOUT`,
`ACCOUNT_PASSWORD_RESET_BY_CODE_TIMEOUT`, `ACCOUNT_LOGIN_BY_CODE_TIMEOUT` and their
`..._MAX_ATTEMPTS`.

## Editing the emails

Every email allauth sends is a Django template you can override. Copy them into your project:

```bash
python manage.py copy_email_templates templates/
python manage.py copy_email_templates templates/ --only email_confirmation password_reset_code
```

and make sure that directory is in `TEMPLATES["DIRS"]`. Existing files are never overwritten
(unless `--force`).

Each email is a set of files under `account/email/` (or `mfa/email/`):

| File | |
|---|---|
| `<name>_subject.txt` | Subject line. `ACCOUNT_EMAIL_SUBJECT_PREFIX` is prepended (default `[site name] `). |
| `<name>_message.txt` | Plain-text body |
| `<name>_message.html` | Optional HTML body; when present, sent alongside the text |

The ones you'll most likely edit:

| Email | `<name>` | Variables |
|---|---|---|
| Verify email at signup | `email_confirmation_signup` | `code` or `activate_url`, `user` |
| Verify another address | `email_confirmation` | `code` or `activate_url`, `user` |
| Password reset (code) | `password_reset_code` | `code` |
| Password reset (link) | `password_reset_key` | `password_reset_url` |
| Sign-in code | `login_code` | `code` |
| Reset requested for unknown address | `unknown_account` | `signup_url` |
| Password changed / set / reset | `password_changed`, `password_set`, `password_reset` | |
| Email address changed / removed | `email_changed`, `email_deleted` | `from_email`, `to_email` / `deleted_email` |
| 2FA turned on/off, passkey added/removed, new recovery codes | `totp_activated`, `totp_deactivated`, `webauthn_added`, `webauthn_removed`, `recovery_codes_generated` (under `mfa/email/`) | |

All of them also get `current_site`, `request` and `email`. The text templates extend
`account/email/base_message.txt`, so editing that one file changes the greeting and sign-off of
every email.

The [demo](https://github.com/memetrusidovski/dj-rest-jwt/tree/main/demo/backend/templates/account/email)
has a complete example: an HTML layout (`base_message.html`) with HTML versions of the
verification, reset and sign-in code emails.

## Sending

Configure Django's email backend as usual (`EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL`). To change how
mail is sent (a queue, an API like Postmark or SES, extra headers), override `send_mail` on an
allauth account adapter (`ACCOUNT_ADAPTER`).
