"""Phone notifications: Web Push encryption and VAPID, subscriptions, and what gets sent."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import struct
from datetime import date, datetime, timedelta, timezone

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient

from app.career import store as career_store
from app.entrypoint import app
from app.hub import service as hub_service
from app.push import notifier, store, webpush


def _auth() -> dict[str, str]:
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": "brad", "iat": now, "exp": now + timedelta(hours=1), "iss": "sirisos-api"},
                       "change-this-development-secret", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


class Browser:
    """The user agent's side of RFC 8291: its keys, and decrypting what arrives."""

    def __init__(self) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.auth = b"0123456789abcdef"
        raw = self.key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        self.p256dh = webpush.b64url(raw)
        self.public = raw

    def subscription(self, endpoint: str = "https://push.example.com/send/abc") -> dict:
        return {"endpoint": endpoint, "keys": {"p256dh": self.p256dh, "auth": webpush.b64url(self.auth)}, "label": "iPhone"}

    def decrypt(self, body: bytes) -> bytes:
        salt, (rs, idlen) = body[:16], struct.unpack("!IB", body[16:21])
        as_public = body[21:21 + idlen]
        ciphertext = body[21 + idlen:]
        shared = self.key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public))

        def hkdf(salt_: bytes, ikm: bytes, info: bytes, n: int) -> bytes:
            prk = hmac.new(salt_, ikm, hashlib.sha256).digest()
            return hmac.new(prk, info + b"\x01", hashlib.sha256).digest()[:n]

        ikm = hkdf(self.auth, shared, b"WebPush: info\x00" + self.public + as_public, 32)
        cek = hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
        nonce = hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
        plain = AESGCM(cek).decrypt(nonce, ciphertext, None)
        assert rs == 4096 and plain.endswith(b"\x02")
        return plain[:-1]


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("SIRISOS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SIRISOS_CAREER_PATH", str(tmp_path / "career.json"))
    return tmp_path


def test_payload_decrypts_in_the_browser():
    browser = Browser()
    body = webpush.encrypt(b'{"title": "Hi"}', browser.p256dh, webpush.b64url(browser.auth))
    assert browser.decrypt(body) == b'{"title": "Hi"}'


def test_vapid_key_is_kept_and_signs_for_the_push_origin(data):
    first = webpush.vapid()
    assert webpush.vapid().public_key == first.public_key  # stored, not regenerated
    header = first.authorization("https://web.push.apple.com/abc/def", "mailto:me@example.com")
    token = header.split("t=")[1].split(",")[0]
    public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), webpush.unb64url(first.public_key))
    claims = jwt.decode(token, public, algorithms=["ES256"], audience="https://web.push.apple.com")
    assert claims["sub"] == "mailto:me@example.com"
    assert header.endswith(f"k={first.public_key}")


@pytest.mark.parametrize("configured, expected", [
    (None, webpush.DEFAULT_SUBJECT),
    ("mailto:sirisos@localhost", webpush.DEFAULT_SUBJECT),
    ("https://localhost:8443", webpush.DEFAULT_SUBJECT),
    ("mailto:me@siris.local", webpush.DEFAULT_SUBJECT),
    ("me@example.com", webpush.DEFAULT_SUBJECT),
    ("mailto:me@example.com", "mailto:me@example.com"),
    ("https://example.com", "https://example.com"),
])
def test_the_vapid_subject_is_one_apple_accepts(monkeypatch, configured, expected):
    if configured is None:
        monkeypatch.delenv("SIRISOS_VAPID_SUBJECT", raising=False)
    else:
        monkeypatch.setenv("SIRISOS_VAPID_SUBJECT", configured)
    assert webpush.subject() == expected


def test_subscribe_list_and_unsubscribe():
    client = TestClient(app)
    assert client.get("/api/v1/push/key").status_code == 401
    assert len(client.get("/api/v1/push/key", headers=_auth()).json()["public_key"]) > 80
    browser = Browser()
    sub = browser.subscription() | {"topics": ["apps", "brief"]}
    assert client.post("/api/v1/push/subscribe", headers=_auth(), json=sub).status_code == 200
    listed = client.get("/api/v1/push/subscriptions", headers=_auth()).json()["subscriptions"]
    assert listed == [{"endpoint": sub["endpoint"], "label": "iPhone", "topics": ["apps", "brief"], "created_at": listed[0]["created_at"]}]
    assert "keys" not in listed[0]
    # Plain http endpoints are refused.
    assert client.post("/api/v1/push/subscribe", headers=_auth(), json=browser.subscription("http://evil/x")).status_code == 422
    assert client.post("/api/v1/push/unsubscribe", headers=_auth(), json={"endpoint": sub["endpoint"]}).json() == {"removed": True}
    assert store.subscriptions() == []


def test_messages_from_the_inbox_brief_and_career():
    items = [
        {"id": "os:app:archive:down", "severity": "attention", "source": "hub", "title": "Engineering Archive is down", "body": ""},
        {"id": "ai:42", "severity": "urgent", "source": "security", "title": "Someone at the door", "body": "Front camera"},
        {"id": "os:archive:review:3", "severity": "info", "source": "archive", "title": "3 waiting", "body": ""},
    ]
    msgs = notifier.inbox_messages(items)
    assert [(m["topic"], m["urgency"]) for m in msgs] == [("apps", "normal"), ("inbox", "high")]

    zone = notifier.zone()
    assert notifier.brief_message(datetime(2026, 10, 17, 6, 0, tzinfo=zone)) == []
    assert notifier.brief_message(datetime(2026, 10, 17, 7, 5, tzinfo=zone))[0]["key"] == "brief:2026-10-17"

    doc = career_store.load()
    doc.goals = [career_store.Goal(id="g1", title="Submit CPEng application", target_date="2026-10-20", next_step="Referee 2"),
                 career_store.Goal(id="g2", title="Later", target_date="2026-12-01")]
    career = notifier.career_messages(doc, date(2026, 10, 17))
    assert [m["title"] for m in career] == ["Career goal due in 3 days"]
    assert "Referee 2" in career[0]["body"]


def test_each_notification_is_sent_once_and_gone_devices_are_dropped(monkeypatch):
    browser = Browser()
    store.upsert(store.Subscription.model_validate(browser.subscription() | {"topics": ["inbox"]}))
    store.upsert(store.Subscription.model_validate(Browser().subscription("https://push.example.com/send/gone")))
    received: list[dict] = []

    def push_service(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/gone"):
            return httpx.Response(410)
        assert request.headers["content-encoding"] == "aes128gcm"
        assert request.headers["authorization"].startswith("vapid t=")
        received.append(json.loads(browser.decrypt(request.content)))
        return httpx.Response(201)

    client = httpx.AsyncClient(transport=httpx.MockTransport(push_service))
    monkeypatch.setattr(notifier, "shared_client", lambda: client)

    async def fake_collect(hub, now):
        return [notifier.message("inbox:ai:1", "inbox", "Approve the lock-down?", "Front door", "/inbox", "high")]

    monkeypatch.setattr(notifier, "collect", fake_collect)
    assert asyncio.run(notifier.run_once(hub_service.Hub({}))) == 1
    assert received == [{"title": "Approve the lock-down?", "body": "Front door", "url": "/inbox", "tag": "inbox:ai:1"}]
    # The gone device was subscribed to every topic, got a 410 and was removed.
    assert [s.endpoint for s in store.subscriptions()] == ["https://push.example.com/send/abc"]
    # Already sent: nothing more.
    assert asyncio.run(notifier.run_once(hub_service.Hub({}))) == 0
