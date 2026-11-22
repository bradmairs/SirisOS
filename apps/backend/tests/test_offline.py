"""11.4: working offline: questions asked with no connection, and the recent Siris notes kept for offline."""

from __future__ import annotations

import asyncio

import pytest

from app.assist import asklater
from app.hub import sirisai_api
from tests.test_budget import client  # noqa: F401  (fixture)
from tests.test_hub import AUTH


@pytest.fixture
def pushed(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_ASKED_PATH", str(tmp_path / "asked.json"))
    sent: list[dict] = []

    async def deliver(msgs):
        sent.extend(msgs)

    from app.push import notifier, store

    monkeypatch.setattr(notifier, "deliver", deliver)
    monkeypatch.setattr(store, "mark_sent", lambda keys: None)
    return sent


def test_a_question_asked_offline_is_answered_once_and_pushed(monkeypatch, pushed):
    asked: list[dict] = []

    async def post(hub, path, json=None, timeout=20.0):
        assert path == "/siris/chat"
        asked.append(json)
        return {"conversation_id": "c9", "response": "Bins go out Wednesday night.", "confirmation_required": False}

    monkeypatch.setattr(sirisai_api, "post", post)
    out = asyncio.run(asklater.answer(None, "When are the bins?", "c9", "2026-11-23T08:00:00"))
    assert out["answer"] == "Bins go out Wednesday night."
    assert asked == [{"prompt": "When are the bins?", "conversation_id": "c9"}]
    assert pushed[0]["title"] == "SirisAI answered: When are the bins?" and pushed[0]["url"] == "/assistant?c=c9"
    # The same question synced twice is asked once.
    again = asyncio.run(asklater.answer(None, "When are the bins?", "c9", "2026-11-23T08:00:00"))
    assert again["duplicate"] and len(asked) == 1 and len(pushed) == 1


def test_an_action_is_never_done_from_an_offline_question(monkeypatch, pushed):
    async def post(hub, path, json=None, timeout=20.0):
        return {"conversation_id": "c1", "response": "Turn off the lights?", "confirmation_required": True}

    monkeypatch.setattr(sirisai_api, "post", post)
    out = asyncio.run(asklater.answer(None, "Turn off the lights", None, "x"))
    assert "confirm" in out["answer"] and "open SirisAI" in pushed[0]["body"]


def test_sirisai_down_says_so_rather_than_losing_it(monkeypatch, pushed):
    async def post(hub, path, json=None, timeout=20.0):
        raise RuntimeError("No route to host")

    monkeypatch.setattr(sirisai_api, "post", post)
    out = asyncio.run(asklater.answer(None, "Hello", None, "y"))
    assert out["answer"].startswith("SirisAI couldn't answer it") and asklater.history()[-1]["prompt"] == "Hello"


def test_ask_later_and_recent_notes_endpoints(client, monkeypatch, pushed):  # noqa: F811
    async def post(hub, path, json=None, timeout=20.0):
        return {"conversation_id": "c2", "response": "Done thinking."}

    async def get(hub, path, params=None, timeout=20.0):
        assert path == "/siris/brain/recent" and params == {"limit": 30}
        return [{"title": "Pump station", "body": "…"}, {"nope": 1}, "x"]

    monkeypatch.setattr(sirisai_api, "post", post)
    monkeypatch.setattr(sirisai_api, "get", get)
    r = client.post("/api/v1/assistant/ask-later", json={"prompt": "Plan my week", "asked_at": "z"}, headers=AUTH)
    assert r.status_code == 202 and r.json() == {"asking": True}
    assert client.get("/api/v1/assistant/asked", headers=AUTH).json()["asked"][0]["answer"] == "Done thinking."
    assert client.get("/api/v1/brain/recent?limit=99", headers=AUTH).json() == [{"title": "Pump station"}]
    assert client.post("/api/v1/assistant/ask-later", json={"prompt": ""}, headers=AUTH).status_code == 422
