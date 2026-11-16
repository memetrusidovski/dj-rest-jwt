# Email templates

These override django-allauth's emails for the demo. Each email is

- `<name>_subject.txt`: the subject line
- `<name>_message.txt`: the plain-text body (allauth's own is used if absent here)
- `<name>_message.html`: optional HTML body, sent alongside the text

Edited here: email verification, password reset (code and link), sign-in code,
plus a shared HTML layout in `base_message.html`.

To copy every allauth email into your own project for editing:

    python manage.py copy_email_templates templates/

All emails and their variables: https://docs.allauth.org/en/latest/common/email.html
