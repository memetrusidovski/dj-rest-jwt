# Demo

A React SPA and a Django backend wired together with dj-rest-jwt. It shows every
flow end to end: signup with an emailed code, password and passkey sign-in,
sign-in by emailed code, TOTP two-factor, recovery codes, password reset,
step-up re-authentication, signed-in devices, and (with a Google client ID)
Sign in with Google.

| Part | What it shows |
|---|---|
| `backend/` | A Django project on the secure preset. `demo/settings.py` is the part to read. |
| `backend/templates/account/email/` | Editing allauth's emails: an HTML layout plus HTML versions of the verification, reset and sign-in code emails. |
| `spa/` | A Vite + React app built on [`dj-rest-jwt-client`](../js). `src/auth.ts` creates the client; the pages call it. |

## Run it

```bash
# backend (Python 3.12+)
cd demo/backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver          # http://localhost:8000

# SPA, in another terminal (Node 20.19+)
cd js && npm install && cd ../demo/spa
npm install
npm run dev                         # http://localhost:5173
```

Or `docker compose up` in this directory.

Open http://localhost:5173. Emails (verification and reset codes) print in the
backend's terminal. The admin is at http://localhost:5173/admin/ after
`python manage.py createsuperuser`.

Optional: `GOOGLE_CLIENT_ID=... python manage.py runserver` shows "Sign in with
Google" (add `http://localhost:5173` as an authorized JavaScript origin).

## Things to try

- **Codes or links.** Change `email_flows(...)` in `backend/demo/settings.py` to
  `verification="link", password_reset="link"`. Emails then link to the SPA's
  `/verify-email/:key` and `/reset-password/:key` routes.
- **Edit an email.** Change `backend/templates/account/email/base_message.html`
  and sign up again. `python manage.py copy_email_templates templates/` copies
  every allauth email for editing.
- **Stay signed in.** Access tokens last 5 minutes. Leave the tab, come back
  later, click "GET /api/me": the client refreshes on its own.
- **Several tabs.** Sign out in one tab; the others follow.
- **Revoke a device.** Sign in from a second browser, then end that session under
  Account → Signed-in devices. Its next request fails immediately.

## How the SPA reaches the API

Vite proxies `/api` and `/admin` to Django (`spa/vite.config.ts`), so the SPA
and the API share an origin and the httpOnly cookies just work. Do the same in
production with one domain behind a reverse proxy, or put the API on a
subdomain with CORS (`credentials: "include"`).

The demo runs on plain `http://localhost`, so `settings.py` relaxes the
`Secure` cookie flags and the WebAuthn origin check when `DEBUG` is on. Never
copy those lines to production.
