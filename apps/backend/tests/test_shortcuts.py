"""Apple Shortcuts: keys, and the plain-text actions they open."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service
from app.hub.service import reset_hub
from tests.test_hub import AUTH


class SirisAI:
    def __init__(self) -> None:
        self.seen: list[tuple[str, dict | str]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        self.seen.append((request.url.path, body))
        if request.url.path == "/siris/brain/capture":
            return httpx.Response(200, json={"saved": True, "title": "Pit lids"})
        if request.url.path == "/siris/ask":
            return httpx.Response(200, text="Bin night is Tuesday.", headers={"X-Conversation-Id": "c1"})
        if request.url.path == "/siris/hub/v1/protocols/wind_down/run":
            return httpx.Response(200, json={"name": "wind_down", "ran": ["dim lights", "lock door"], "skipped": [], "failed": [], "can_undo": True})
        return httpx.Response(404)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SIRISOS_SHORTCUT_KEYS_PATH", str(tmp_path / "keys.json"))
    fake = SirisAI()
    monkeypatch.setattr(service, "transport", httpx.MockTransport(fake))
    reset_hub({"SIRISAI_URL": "http://sirisai:8000", "SIRISAI_API_KEY": "k"})
    c = TestClient(app)
    c.fake = fake  # type: ignore[attr-defined]
    yield c
    reset_hub({})


def test_keys_are_shown_once_stored_hashed_and_revocable(client, tmp_path):
    assert client.get("/api/v1/shortcuts/keys").status_code == 401
    made = client.post("/api/v1/shortcuts/keys", headers=AUTH, json={"label": "iPhone", "scopes": ["capture", "ask"]}).json()
    assert made["secret"].startswith("sk_") and made["scopes"] == ["capture", "ask"]
    stored = (tmp_path / "keys.json").read_text()
    assert made["secret"] not in stored
    listed = client.get("/api/v1/shortcuts/keys", headers=AUTH).json()["keys"]
    assert listed[0]["label"] == "iPhone" and "secret" not in listed[0] and "hash" not in listed[0]
    key = {"Authorization": f"Bearer {made['secret']}"}
    assert client.post("/api/v1/shortcuts/capture", headers=key, content="Check pit lids").status_code == 200
    assert client.get("/api/v1/shortcuts/keys", headers=AUTH).json()["keys"][0]["last_used"]
    # Not given "protocols"; a session token isn't a shortcut key; revoked keys stop at once.
    assert client.post("/api/v1/shortcuts/protocols/wind_down", headers=key).status_code == 403
    assert client.post("/api/v1/shortcuts/capture", headers=AUTH, content="x").status_code == 401
    assert client.delete(f"/api/v1/shortcuts/keys/{made['id']}", headers=AUTH).json() == {"revoked": True}
    assert client.post("/api/v1/shortcuts/capture", headers=key, content="x").status_code == 401


def test_actions_answer_plain_text(client):
    secret = client.post("/api/v1/shortcuts/keys", headers=AUTH, json={"label": "Siri", "scopes": ["capture", "ask", "today", "protocols"]}).json()["secret"]
    key = {"X-Shortcut-Key": secret}
    saved = client.post("/api/v1/shortcuts/capture", headers=key, content="Check the pit lids on Monday")
    assert saved.text == "Saved to Siris as “Pit lids”." and saved.headers["content-type"].startswith("text/plain")
    assert client.fake.seen[-1] == ("/siris/brain/capture", {"text": "Check the pit lids on Monday", "url": "", "tags": ["shortcut"]})
    client.post("/api/v1/shortcuts/capture", headers=key, content="https://www.ipwea.org/events")
    assert client.fake.seen[-1][1]["url"] == "https://www.ipwea.org/events" and client.fake.seen[-1][1]["text"] == ""
    asked = client.post("/api/v1/shortcuts/ask", headers=key, json={"text": "When is bin night?"})
    assert asked.text == "Bin night is Tuesday." and asked.headers["x-conversation-id"] == "c1"
    assert client.fake.seen[-1] == ("/siris/ask", {"prompt": "When is bin night?"})
    ran = client.post("/api/v1/shortcuts/protocols/wind_down", headers=key)
    assert ran.text == "Wind down done: 2 steps. You can undo it in SirisOS."
    assert client.fake.seen[-1][1] == {"confirmed": True}
    assert client.post("/api/v1/shortcuts/protocols/..%2Fx", headers=key).status_code in (404, 422)


def test_today_reads_the_brief_aloud(client, monkeypatch):
    from app.shortcuts import api as shortcuts_api

    async def build(hub, user, fresh=False):
        return {"greeting": "Good morning, Brad", "headline": ["21° today, showers.", "2 things on today."],
                "changes": {"label": "yesterday", "lines": ["5° warmer than yesterday."]}}

    monkeypatch.setattr(shortcuts_api.brief_service, "build", build)
    secret = client.post("/api/v1/shortcuts/keys", headers=AUTH, json={"scopes": ["today"]}).json()["secret"]
    spoken = client.get("/api/v1/shortcuts/today", headers={"Authorization": f"Bearer {secret}"}).text
    assert spoken == "Good morning. 21° today, showers. 2 things on today. Since yesterday: 5° warmer than yesterday."
