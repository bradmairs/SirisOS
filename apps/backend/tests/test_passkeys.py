"""Passkeys (WebAuthn), sign-in rate limiting and the security check, with a
software authenticator standing in for Face ID."""

from __future__ import annotations

import hashlib
import json
import struct

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.security import service, webauthn
from tests.test_hub import AUTH

ORIGIN = "https://sirisos.home"
RP = "sirisos.home"


def cbor(value) -> bytes:
    def head(major: int, n: int) -> bytes:
        if n < 24:
            return bytes([major << 5 | n])
        for info, size in ((24, 1), (25, 2), (26, 4), (27, 8)):
            if n < 1 << (8 * size):
                return bytes([major << 5 | info]) + n.to_bytes(size, "big")
        raise ValueError
    if isinstance(value, bool):
        return bytes([0xF5 if value else 0xF4])
    if isinstance(value, int):
        return head(0, value) if value >= 0 else head(1, -1 - value)
    if isinstance(value, bytes):
        return head(2, len(value)) + value
    if isinstance(value, str):
        raw = value.encode()
        return head(3, len(raw)) + raw
    if isinstance(value, list):
        return head(4, len(value)) + b"".join(cbor(v) for v in value)
    if isinstance(value, dict):
        return head(5, len(value)) + b"".join(cbor(k) + cbor(v) for k, v in value.items())
    raise TypeError(value)


class Authenticator:
    def __init__(self) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.cred_id = b"cred-" + bytes(range(16))
        self.count = 0

    def _auth_data(self, flags: int, attested: bool, rp: str = RP) -> bytes:
        out = hashlib.sha256(rp.encode()).digest() + bytes([flags]) + struct.pack(">I", self.count)
        if attested:
            nums = self.key.public_key().public_numbers()
            cose = {1: 2, 3: -7, -1: 1, -2: nums.x.to_bytes(32, "big"), -3: nums.y.to_bytes(32, "big")}
            out += b"\x00" * 16 + struct.pack(">H", len(self.cred_id)) + self.cred_id + cbor(cose)
        return out

    def create(self, challenge: str, origin: str = ORIGIN) -> dict:
        client = json.dumps({"type": "webauthn.create", "challenge": challenge, "origin": origin}).encode()
        att = cbor({"fmt": "none", "attStmt": {}, "authData": self._auth_data(0x45, True)})
        return {"clientDataJSON": webauthn.b64url(client), "attestationObject": webauthn.b64url(att)}

    def get(self, challenge: str, origin: str = ORIGIN, flags: int = 0x05, rp: str = RP) -> dict:
        self.count += 1
        client = json.dumps({"type": "webauthn.get", "challenge": challenge, "origin": origin}).encode()
        auth = self._auth_data(flags, False, rp)
        sig = self.key.sign(auth + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        return {"clientDataJSON": webauthn.b64url(client), "authenticatorData": webauthn.b64url(auth), "signature": webauthn.b64url(sig)}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SIRISOS_PASSKEYS_PATH", str(tmp_path / "passkeys.json"))
    service.reset()
    yield TestClient(app, headers={"Origin": ORIGIN})
    service.reset()


def _register(client, device: Authenticator) -> dict:
    options = client.post("/api/v1/auth/passkeys/register/options", headers=AUTH).json()
    assert options["rp"] == {"id": RP, "name": "SirisOS"} and options["authenticatorSelection"]["userVerification"] == "required"
    return client.post("/api/v1/auth/passkeys/register", headers=AUTH,
                       json={"challenge": options["challenge"], "response": device.create(options["challenge"]), "label": "iPhone"})


def _sign_in(client, device: Authenticator, **kw):
    options = client.post("/api/v1/auth/passkeys/login/options").json()
    return client.post("/api/v1/auth/passkeys/login", json={
        "challenge": options["challenge"], "id": webauthn.b64url(device.cred_id), "response": device.get(options["challenge"], **kw)})


def test_add_a_passkey_and_sign_in_with_it(client):
    phone = Authenticator()
    made = _register(client, phone)
    assert made.status_code == 200 and made.json()["label"] == "iPhone" and made.json()["rp_id"] == RP
    signed_in = _sign_in(client, phone)
    assert signed_in.status_code == 200
    token = signed_in.json()["access_token"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json() == {"username": "brad"}
    listed = client.get("/api/v1/auth/passkeys", headers=AUTH).json()["passkeys"]
    assert listed[0]["last_used"] and "public_key" not in listed[0]
    assert client.delete(f"/api/v1/auth/passkeys/{listed[0]['id']}", headers=AUTH).json() == {"removed": True}
    assert _sign_in(client, phone).status_code == 401


def test_every_check_on_an_assertion(client):
    phone = Authenticator()
    _register(client, phone)
    assert _sign_in(client, phone, origin="https://evil.example").status_code == 401        # wrong origin
    assert _sign_in(client, phone, rp="evil.example").status_code == 401                     # wrong relying party
    assert _sign_in(client, phone, flags=0x01).status_code == 401                            # no Face ID
    impostor = Authenticator()
    impostor.cred_id = phone.cred_id
    assert _sign_in(client, impostor).status_code == 401                                     # wrong key
    assert _sign_in(client, phone).status_code == 200                                        # the real one
    phone.count = 0                                                                          # counter went backwards
    assert _sign_in(client, phone).status_code == 401
    # A challenge is single use.
    phone.count = 100
    options = client.post("/api/v1/auth/passkeys/login/options").json()
    body = {"challenge": options["challenge"], "id": webauthn.b64url(phone.cred_id), "response": phone.get(options["challenge"])}
    assert client.post("/api/v1/auth/passkeys/login", json=body).status_code == 200
    assert client.post("/api/v1/auth/passkeys/login", json=body).status_code == 401


def test_passkeys_refuse_bare_ip_addresses_and_need_sign_in_to_add(client):
    assert client.post("/api/v1/auth/passkeys/register/options").status_code == 401
    ip = TestClient(app, headers={"Origin": "https://192.168.0.100:8444"})
    assert ip.post("/api/v1/auth/passkeys/login/options").status_code == 400


def test_wrong_passwords_are_rate_limited(client):
    for _ in range(service.MAX_FAILURES):
        assert client.post("/api/v1/auth/login", json={"username": "brad", "password": "nope"}).status_code == 401
    blocked = client.post("/api/v1/auth/login", json={"username": "brad", "password": "change-me"})
    assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) > 0
    # Another client isn't affected.
    other = client.post("/api/v1/auth/login", json={"username": "brad", "password": "change-me"}, headers={"X-Forwarded-For": "10.0.0.9"})
    assert other.status_code == 200


def test_security_check_flags_defaults(client, monkeypatch):
    checks = client.get("/api/v1/security", headers=AUTH).json()["checks"]
    titles = [c["title"] for c in checks]
    assert "Sign-in secret is a default or too short" in titles and "No passkey yet" in titles
    assert checks[0]["level"] == "critical"
