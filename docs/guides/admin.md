# Django admin

The admin keeps working, and its sign-in goes through allauth: the same rate limits,
failed-login limits and MFA as the API.

```python title="urls.py"
urlpatterns = [
    path("admin/", include("dj_rest_jwt.admin_login")),   # must come before admin.site.urls
    path("admin/", admin.site.urls),
    ...
]
```

On startup dj-rest-jwt replaces `admin.site.login` with allauth's sign-in
(`admin/auth/login/`), followed by `admin/auth/login/mfa/` when the staff user has a second
factor. Staff with TOTP must enter a code; there is no way around it through the admin's own
form.

The admin is the one place that uses a Django session cookie as a credential, because it is
server-rendered. It is separate from the API's JWTs.

To keep Django's stock admin login, set `DJ_REST_JWT = {"ADMIN_LOGIN": False}` and leave out the
`admin_login` include. If `ADMIN_LOGIN` is on but the URLs are missing, the `dj_rest_jwt.E009`
check reports it.
