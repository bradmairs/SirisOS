"""11.16: Ask Siris from a Shortcut, with its own key."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.ask import service as ask
from app.entrypoint import app
from app.hub import sirisai_api
from app.share import service as share
from tests.test_hub import AUTH


@pytest.fixture
def keyed(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_ASK_PATH", str(tmp_path / "ask.json"))
    monkeypatch.setenv("SIRISOS_SHARE_PATH", str(tmp_path / "share.json"))
    ask._recent.clear()
    ask._last.clear()
    key = TestClient(app, headers=AUTH).post("/api/v1/ask/key").json()["key"]
    asked: list[dict] = []

    async def post(hub, path, json=None, timeout=None):
        assert path == "/siris/chat"
        asked.append(json)
        if "lock" in json["prompt"]:
            return {"conversation_id": "c1", "confirmation_required": True}
        return {"conversation_id": json.get("conversation_id") or f"c{len(asked)}", "response": f"Answer to {json['prompt']}"}

    monkeypatch.setattr(sirisai_api, "post", post)
    return TestClient(app, headers={"X-SirisOS-Key": key}), key, asked, tmp_path


def test_the_key_is_shown_once_and_opens_nothing_else(keyed):
    bare, key, _, tmp = keyed
    assert key.startswith("sa_") and key not in (tmp / "ask.json").read_text()
    assert TestClient(app).post("/api/v1/ask", json={"text": "hi"}, headers={"X-SirisOS-Key": "sa_wrong"}).status_code == 401
    assert bare.get("/api/v1/tasks").status_code == 401
    assert TestClient(app).post("/api/v1/share", json={"text": "hi"}, headers={"X-SirisOS-Key": key}).status_code == 401  # not a share key
    assert not share.matches(key)
    assert TestClient(app, headers=AUTH).get("/api/v1/ask/key").json()["on"]


def test_a_question_is_answered_and_a_follow_up_carries_on(keyed):
    bare, _, asked, _ = keyed
    first = bare.post("/api/v1/ask", json={"text": "What's on today?"}).json()
    assert first == {"say": "Answer to What's on today?", "conversation_id": "c1", "link": "/assistant?c=c1"}
    bare.post("/api/v1/ask", json={"text": "And tomorrow?"})
    assert asked[1] == {"prompt": "And tomorrow?", "conversation_id": "c1"}
    bare.post("/api/v1/ask", json={"text": "Something else", "new": True})
    assert "conversation_id" not in asked[2]


def test_nothing_is_approved_from_the_shortcut(keyed):
    bare, _, asked, _ = keyed
    out = bare.post("/api/v1/ask", json={"text": "unlock the back door"}).json()
    assert out["say"].startswith("That needs your OK") and all("confirmed" not in a for a in asked)


def test_empty_wrong_and_too_many(keyed, monkeypatch):
    bare, *_ = keyed
    assert bare.post("/api/v1/ask", json={"text": "  "}).status_code == 422
    monkeypatch.setattr(ask, "LIMIT_PER_HOUR", 1)
    ask._recent.clear()
    assert bare.post("/api/v1/ask", json={"text": "one"}).status_code == 200
    assert bare.post("/api/v1/ask", json={"text": "two"}).status_code == 429


def test_turning_it_off_stops_the_key(keyed):
    bare, *_ = keyed
    TestClient(app, headers=AUTH).delete("/api/v1/ask/key")
    assert bare.post("/api/v1/ask", json={"text": "hi"}).status_code == 401
    assert not TestClient(app, headers=AUTH).get("/api/v1/ask/key").json()["on"]


def test_a_follow_up_window_ends():
    ask._last.clear()
    ask.remember("c9", now=100.0)
    assert ask.conversation(None, now=100.0 + ask.FOLLOW_UP_SECONDS - 1) == "c9"
    assert ask.conversation(None, now=100.0 + ask.FOLLOW_UP_SECONDS + 1) is None
    assert ask.conversation("explicit", now=0) == "explicit"
