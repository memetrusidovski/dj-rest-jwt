import base64
import json
import struct

from allauth.account.models import EmailAddress
from allauth.mfa.totp.internal.auth import format_hotp_value, hotp_value, yield_hotp_counters_from_time
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from django.contrib.auth import get_user_model
from django.test import Client
from fido2 import cbor
from fido2.utils import sha256
from soft_webauthn import SoftWebauthnDevice

AUTH = "/api/auth/v1"
PASSWORD = "Correct-Horse-9-Battery"
ORIGIN = "https://testserver"


def b64url(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def b64url_decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def totp_code(secret):
    return format_hotp_value(hotp_value(secret, next(yield_hotp_counters_from_time())))


def make_user(email="alice@example.com", **extra):
    user = get_user_model().objects.create_user(
        username=email.split("@")[0], email=email, password=PASSWORD, **extra,
    )
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user


def pending_flows(body):
    return [f["id"] for f in (body.get("data") or {}).get("flows", []) if f.get("is_pending")]


class Api:
    """
    A client like a browser SPA (cookie transport) or, with header=True, like
    a native app (X-Auth-Transport: header, Bearer token).
    """

    def __init__(self, header=False):
        self.c = Client(enforce_csrf_checks=True, secure=True)
        self.header = header
        self.session_token = None
        self.access = None
        self.refresh = None

    def _headers(self, extra):
        headers = {}
        if self.header:
            headers["HTTP_X_AUTH_TRANSPORT"] = "header"
            if self.access:
                headers["HTTP_AUTHORIZATION"] = f"Bearer {self.access}"
        csrf = self.c.cookies.get("csrftoken")
        if csrf:
            headers["HTTP_X_CSRFTOKEN"] = csrf.value
        if self.session_token:
            headers["HTTP_X_SESSION_TOKEN"] = self.session_token
        headers.update(extra)
        return headers

    def call(self, method, path, data=None, **extra):
        kwargs = self._headers(extra)
        if data is not None:
            kwargs.update(data=json.dumps(data), content_type="application/json")
        resp = getattr(self.c, method)(path, **kwargs)
        try:
            body = resp.json()
        except ValueError:
            body = {}
        meta = body.get("meta") or {}
        if "session_token" in meta:
            self.session_token = meta["session_token"]
        if "access_token" in meta:
            self.access, self.refresh = meta["access_token"], meta.get("refresh_token")
            self.session_token = None
        if not self.header and self.cookie("access_token"):
            self.session_token = None
        return resp, body

    def cookie(self, name):
        c = self.c.cookies.get(name)
        return c.value if c and c.value else None

    def login(self, email="alice@example.com", password=PASSWORD):
        return self.call("post", f"{AUTH}/auth/login", {"email": email, "password": password})

    def refresh_tokens(self):
        if self.header:
            resp, body = self.call("post", f"{AUTH}/tokens/refresh", {"refresh_token": self.refresh})
            data = body.get("data") or {}
            if resp.status_code == 200:
                self.access = data["access_token"]
                self.refresh = data.get("refresh_token", self.refresh)
            return resp, body
        return self.call("post", f"{AUTH}/tokens/refresh", {})


class VerifyingDevice(SoftWebauthnDevice):
    """soft-webauthn, but reporting user verification (biometric/PIN) like a real passkey."""

    def create(self, options, origin):
        cred = super().create(options, origin)
        att = cbor.decode(cred["response"]["attestationObject"])
        auth_data = bytearray(att["authData"])
        auth_data[32] |= 0x04                       # UV flag; 'none' attestation is unsigned
        att["authData"] = bytes(auth_data)
        cred["response"]["attestationObject"] = cbor.encode(att)
        return cred

    def get(self, options, origin):
        if self.rp_id != options["publicKey"]["rpId"]:
            raise ValueError("rpId mismatch")
        self.sign_count += 1
        client_data = json.dumps({
            "type": "webauthn.get",
            "challenge": b64url(options["publicKey"]["challenge"]),
            "origin": origin,
        }).encode()
        auth_data = sha256(self.rp_id.encode()) + b"\x05" + struct.pack(">I", self.sign_count)
        signature = self.private_key.sign(auth_data + sha256(client_data), ec.ECDSA(hashes.SHA256()))
        return {
            "rawId": self.credential_id,
            "response": {
                "authenticatorData": auth_data, "clientDataJSON": client_data,
                "signature": signature, "userHandle": self.user_handle,
            },
        }


def decode_options(options):
    """allauth's JSON WebAuthn options -> the bytes soft-webauthn expects."""
    pk = dict(options["publicKey"] if "publicKey" in options else options)
    pk["challenge"] = b64url_decode(pk["challenge"])
    if "user" in pk:
        pk["user"] = {**pk["user"], "id": b64url_decode(pk["user"]["id"])}
    return {"publicKey": pk}


def encode_credential(cred):
    out = {"id": b64url(cred["rawId"]), "rawId": b64url(cred["rawId"]), "type": "public-key",
           "response": {}, "clientExtensionResults": {}}
    for k, v in cred["response"].items():
        out["response"][k] = b64url(v) if isinstance(v, bytes) else v
    return out


def google_identity(sub="g-123", email="alice@example.com"):
    return {"iss": "https://accounts.google.com", "aud": "test-google-client", "sub": sub,
            "email": email, "email_verified": True, "name": "Test"}


def google_login(api):
    return api.call("post", f"{AUTH}/auth/provider/token", {
        "provider": "google", "process": "login",
        "token": {"client_id": "test-google-client", "id_token": "header.payload.sig"},
    })
