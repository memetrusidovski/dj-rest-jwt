"""
dj-rest-jwt: an API/JWT-first security layer over django-allauth headless.

allauth does the authentication itself (login, signup, MFA, passkeys, social
login, sessions, JWT minting and rotation). This package adds what an
API-first project still needs on top: clean URLs, httpOnly cookie transport
for browser SPAs alongside Bearer tokens for native apps, refresh-token reuse
detection, a DRF authentication class, an MFA-protected admin login, signup
anti-spam, a secure settings preset and system checks that enforce it.
"""
from .__version__ import __version__  # noqa: F401
