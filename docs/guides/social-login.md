# Social login

Any of allauth's 100+ providers works. Add the provider app and its credentials:

```python title="settings.py"
INSTALLED_APPS += ["allauth.socialaccount.providers.google"]

SOCIALACCOUNT_PROVIDERS = {
    "google": {"APPS": [{
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "secret": os.environ["GOOGLE_CLIENT_SECRET"],
    }]},
}
```

## Token flow (recommended for SPAs and apps)

The frontend uses the provider's own SDK (Google Identity Services, Sign in with Apple, the
native Google/Facebook SDKs) to get an ID token or access token, then hands it to the API:

```http
POST /api/auth/v1/auth/provider/token
{"provider": "google", "process": "login",
 "token": {"client_id": "...", "id_token": "..."}}
```

allauth verifies the token (signature, audience, expiry) and signs the user in or up. If the
user has MFA, the response is the usual pending `mfa_authenticate` step.

```ts
google.accounts.id.initialize({
  client_id,
  callback: ({ credential }) => auth.providerToken("google", { client_id, id_token: credential }),
});
```

`GET config` lists the configured providers and their client IDs, so the frontend doesn't need
to hard-code them.

## Account takeover protection

The preset never signs someone into an existing local account just because a provider reports
the same email address:

```python
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = False
```

One provider that doesn't verify email addresses would otherwise let anyone take over any
account. A user who signed up with a password connects a social account from their settings
(`account/providers`) instead. The `dj_rest_jwt.W009` check warns if this is turned back on.
