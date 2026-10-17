"""Passkeys (WebAuthn level 2), the parts SirisOS needs: register a passkey
while signed in, and sign in with one. Written against the spec with
`cryptography` alone.

- Registration asks for no attestation ("none"): the person adding the
  passkey is already signed in, so the key is trusted because of who added
  it, not because of who made the authenticator.
- Sign-in checks everything the spec requires of an assertion: a fresh,
  single-use challenge; the client data's type and origin; the relying
  party's hash; user presence and verification (Face ID); the signature
  over authenticatorData || SHA-256(clientDataJSON); and the sign count.
- ES256 (every Apple passkey) and RS256 keys are accepted.
"""

from __future__ import annotations

import base64
import hashlib
import json
import struct
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

ES256, RS256 = -7, -257
FLAG_UP, FLAG_UV, FLAG_AT = 0x01, 0x04, 0x40


class WebAuthnError(ValueError):
    pass


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64url(text: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (ValueError, TypeError) as exc:
        raise WebAuthnError("Bad base64url.") from exc


# -- a small CBOR reader (RFC 8949), enough for attestation objects and COSE keys --


def cbor_decode(data: bytes, offset: int = 0) -> tuple[Any, int]:
    if offset >= len(data):
        raise WebAuthnError("Truncated CBOR.")
    head = data[offset]
    major, info = head >> 5, head & 0x1F
    offset += 1
    if info < 24:
        arg = info
    elif info in (24, 25, 26, 27):
        size = 1 << (info - 24)
        if offset + size > len(data):
            raise WebAuthnError("Truncated CBOR.")
        arg = int.from_bytes(data[offset:offset + size], "big")
        offset += size
    else:
        raise WebAuthnError("Unsupported CBOR (indefinite length).")
    if major == 0:
        return arg, offset
    if major == 1:
        return -1 - arg, offset
    if major in (2, 3):
        if offset + arg > len(data):
            raise WebAuthnError("Truncated CBOR.")
        raw = data[offset:offset + arg]
        return (raw if major == 2 else raw.decode("utf-8")), offset + arg
    if major == 4:
        items = []
        for _ in range(arg):
            item, offset = cbor_decode(data, offset)
            items.append(item)
        return items, offset
    if major == 5:
        out: dict[Any, Any] = {}
        for _ in range(arg):
            k, offset = cbor_decode(data, offset)
            v, offset = cbor_decode(data, offset)
            out[k] = v
        return out, offset
    if major == 7 and info in (20, 21, 22):
        return {20: False, 21: True, 22: None}[info], offset
    raise WebAuthnError("Unsupported CBOR item.")


def cose_to_spki(cose: dict[int, Any]) -> tuple[bytes, int]:
    """A COSE public key as (DER SubjectPublicKeyInfo, alg)."""
    kty, alg = cose.get(1), cose.get(3)
    if kty == 2 and alg == ES256 and cose.get(-1) == 1:
        x, y = cose.get(-2), cose.get(-3)
        if not (isinstance(x, bytes) and isinstance(y, bytes) and len(x) == len(y) == 32):
            raise WebAuthnError("Bad EC2 key.")
        key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b"\x04" + x + y)
    elif kty == 3 and alg == RS256:
        n, e = cose.get(-1), cose.get(-2)
        if not (isinstance(n, bytes) and isinstance(e, bytes)):
            raise WebAuthnError("Bad RSA key.")
        key = rsa.RSAPublicNumbers(int.from_bytes(e, "big"), int.from_bytes(n, "big")).public_key()
    else:
        raise WebAuthnError("Only ES256 and RS256 passkeys are supported.")
    return key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo), alg


@dataclass
class AuthData:
    rp_id_hash: bytes
    flags: int
    sign_count: int
    credential_id: bytes | None = None
    public_key: bytes | None = None  # DER SPKI
    alg: int | None = None


def parse_auth_data(data: bytes) -> AuthData:
    if len(data) < 37:
        raise WebAuthnError("authenticatorData is too short.")
    out = AuthData(rp_id_hash=data[:32], flags=data[32], sign_count=struct.unpack(">I", data[33:37])[0])
    if out.flags & FLAG_AT:
        if len(data) < 55:
            raise WebAuthnError("Attested credential data is truncated.")
        length = struct.unpack(">H", data[53:55])[0]
        out.credential_id = data[55:55 + length]
        cose, _ = cbor_decode(data, 55 + length)
        if not isinstance(cose, dict):
            raise WebAuthnError("Bad credential public key.")
        out.public_key, out.alg = cose_to_spki(cose)
    return out


def origin_ok(origin: str, rp_id: str) -> bool:
    parts = urlsplit(origin)
    host = parts.hostname or ""
    secure = parts.scheme == "https" or (parts.scheme == "http" and host in ("localhost", "127.0.0.1"))
    return secure and (host == rp_id or host.endswith("." + rp_id))


def _client_data(raw_b64: str, kind: str, challenge: str, rp_id: str) -> bytes:
    raw = unb64url(raw_b64)
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise WebAuthnError("Bad clientDataJSON.") from exc
    if data.get("type") != kind:
        raise WebAuthnError("Wrong ceremony.")
    if data.get("challenge") != challenge:
        raise WebAuthnError("The challenge doesn't match: try again.")
    if not origin_ok(str(data.get("origin", "")), rp_id):
        raise WebAuthnError(f"This passkey ceremony came from {data.get('origin')!r}, not {rp_id}.")
    if data.get("crossOrigin"):
        raise WebAuthnError("Cross-origin passkey use isn't allowed.")
    return raw


def verify_registration(response: dict[str, Any], challenge: str, rp_id: str) -> AuthData:
    _client_data(str(response.get("clientDataJSON", "")), "webauthn.create", challenge, rp_id)
    attestation, _ = cbor_decode(unb64url(str(response.get("attestationObject", ""))))
    if not isinstance(attestation, dict) or not isinstance(attestation.get("authData"), bytes):
        raise WebAuthnError("Bad attestationObject.")
    auth = parse_auth_data(attestation["authData"])
    if auth.rp_id_hash != hashlib.sha256(rp_id.encode()).digest():
        raise WebAuthnError("The passkey was made for a different site.")
    if not auth.flags & FLAG_UP or not auth.flags & FLAG_UV:
        raise WebAuthnError("The passkey needs Face ID, Touch ID or a passcode.")
    if not auth.credential_id or not auth.public_key:
        raise WebAuthnError("No credential in the response.")
    return auth


def verify_assertion(response: dict[str, Any], challenge: str, rp_id: str, public_key_der: bytes, alg: int, stored_count: int) -> int:
    """Returns the new sign count; raises WebAuthnError on anything wrong."""
    client_raw = _client_data(str(response.get("clientDataJSON", "")), "webauthn.get", challenge, rp_id)
    auth_raw = unb64url(str(response.get("authenticatorData", "")))
    auth = parse_auth_data(auth_raw)
    if auth.rp_id_hash != hashlib.sha256(rp_id.encode()).digest():
        raise WebAuthnError("The passkey is for a different site.")
    if not auth.flags & FLAG_UP or not auth.flags & FLAG_UV:
        raise WebAuthnError("The passkey needs Face ID, Touch ID or a passcode.")
    signed = auth_raw + hashlib.sha256(client_raw).digest()
    signature = unb64url(str(response.get("signature", "")))
    key = serialization.load_der_public_key(public_key_der)
    try:
        if alg == ES256 and isinstance(key, ec.EllipticCurvePublicKey):
            key.verify(signature, signed, ec.ECDSA(hashes.SHA256()))
        elif alg == RS256 and isinstance(key, rsa.RSAPublicKey):
            key.verify(signature, signed, padding.PKCS1v15(), hashes.SHA256())
        else:
            raise WebAuthnError("Unknown key type.")
    except InvalidSignature as exc:
        raise WebAuthnError("The passkey's signature didn't check out.") from exc
    # Synced passkeys always report 0; a real counter must only go up.
    if (auth.sign_count or stored_count) and auth.sign_count <= stored_count:
        raise WebAuthnError("This passkey's counter went backwards: it may have been copied.")
    return auth.sign_count
