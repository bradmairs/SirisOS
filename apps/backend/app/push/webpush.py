"""Web Push, sent straight to the browser's push service (RFC 8030), with
the payload encrypted for that one browser (RFC 8291, aes128gcm) and the
request signed with SirisOS's VAPID key (RFC 8292). Only `cryptography`
and PyJWT are needed; httpx does the sending.

The VAPID key pair is made on first use and kept in the data directory, so
subscriptions stay valid across restarts. SIRISOS_VAPID_SUBJECT (a mailto:
or https: URL) is who push services contact about misuse.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.services import json_store

RECORD_SIZE = 4096


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _raw_public(key: ec.EllipticCurvePublicKey) -> bytes:
    return key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    return hmac.new(prk, info + b"\x01", hashlib.sha256).digest()[:length]


def encrypt(payload: bytes, p256dh: str, auth: str, *, salt: bytes | None = None,
            server_key: ec.EllipticCurvePrivateKey | None = None) -> bytes:
    """The aes128gcm body for one subscription (RFC 8291 §3.4)."""
    ua_public = unb64url(p256dh)
    auth_secret = unb64url(auth)
    server_key = server_key or ec.generate_private_key(ec.SECP256R1())
    as_public = _raw_public(server_key.public_key())
    shared = server_key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public))
    ikm = _hkdf(auth_secret, shared, b"WebPush: info\x00" + ua_public + as_public, 32)
    salt = salt or os.urandom(16)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    if len(payload) > RECORD_SIZE - 17 - 86:
        raise ValueError("Push payload too large.")
    ciphertext = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    return salt + struct.pack("!IB", RECORD_SIZE, len(as_public)) + as_public + ciphertext


@dataclass
class Vapid:
    private_key: ec.EllipticCurvePrivateKey

    @property
    def public_key(self) -> str:
        """What the browser's pushManager.subscribe() needs (applicationServerKey)."""
        return b64url(_raw_public(self.private_key.public_key()))

    def authorization(self, endpoint: str, subject: str) -> str:
        parts = urlsplit(endpoint)
        claims = {"aud": f"{parts.scheme}://{parts.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": subject}
        token = jwt.encode(claims, self.private_key, algorithm="ES256")
        return f"vapid t={token}, k={self.public_key}"


def _vapid_path():
    return json_store.data_path("SIRISOS_VAPID_PATH", "push-vapid.json")


def vapid() -> Vapid:
    stored = json_store.read(_vapid_path(), None)
    if stored and stored.get("private_key"):
        key = serialization.load_pem_private_key(stored["private_key"].encode(), password=None)
        assert isinstance(key, ec.EllipticCurvePrivateKey)
        return Vapid(key)
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    json_store.write(_vapid_path(), {"private_key": pem})
    return Vapid(key)


def subject() -> str:
    return os.getenv("SIRISOS_VAPID_SUBJECT") or "mailto:sirisos@localhost"


class Gone(Exception):
    """The push service says this subscription no longer exists (404/410)."""


async def send(client: httpx.AsyncClient, subscription: dict[str, Any], message: dict[str, Any],
               *, ttl: int = 3600, urgency: str = "normal") -> None:
    endpoint = subscription["endpoint"]
    keys = subscription["keys"]
    body = encrypt(json.dumps(message, ensure_ascii=False).encode(), keys["p256dh"], keys["auth"])
    response = await client.post(endpoint, content=body, headers={
        "Authorization": vapid().authorization(endpoint, subject()),
        "Content-Encoding": "aes128gcm",
        "Content-Type": "application/octet-stream",
        "TTL": str(ttl),
        "Urgency": urgency,
    }, timeout=10.0)
    if response.status_code in (404, 410):
        raise Gone(endpoint)
    response.raise_for_status()
