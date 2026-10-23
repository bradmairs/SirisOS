"""Email triage (3.3): SirisAI's drafted replies read, sent as edited,
snoozed and left; and snoozing any inbox item."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.attention import api as attention_api
from app.brief.service import zone
from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from tests.test_hub import AUTH, ENV

REPLY = {"id": 12, "key": "triage:email:41", "kind": "review", "severity": "attention", "title": "Reply to Dana Lee: Werribee levels",
         "body": "Hi Brad, attached are the levels for…\n\nMy draft (saved in your Drafts folder):\n\nThanks Dana, I'll check them tomorrow.\n\nBrad",
         "source": "triage", "actions": [{"id": "send", "label": "Send reply", "style": "primary"}, {"id": "dismiss", "label": "I'll handle it"}],
         "status": "open", "created_at": "2026-10-23T06:00:00", "updated_at": "2026-10-23T06:00:00"}
OTHER = {**REPLY, "id": 13, "key": "x", "title": "This morning", "body": "2 emails need a reply.", "kind": "notice", "actions": []}


class FakeSirisAI:
    def __init__(self) -> None:
        self.acts: list[tuple[str, dict | None]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/siris/hub/v1/attention":
            return httpx.Response(200, json={"items": [REPLY, OTHER], "counts": {"open": 2, "urgent": 0}})
        if path.startswith("/siris/hub/v1/attention/12/"):
            self.acts.append((path, json.loads(request.content) if request.content else None))
            return httpx.Response(200, json={"item": {**REPLY, "status": "done"}, "result": {"sent": True}})
        return httpx.Response(404, json={"detail": "Not Found"})


@pytest.fixture
def ai(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_ATTENTION_STATE_PATH", str(tmp_path / "attention.json"))
    fake = FakeSirisAI()
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(fake))
    reset_hub(ENV)
    yield fake
    reset_hub({})


@pytest.fixture
def client():
    return TestClient(app)


def test_replies_are_parsed_into_who_subject_and_draft(client, ai):
    body = client.get("/api/v1/email/triage", headers=AUTH).json()
    assert body["unavailable"] is False and body["snoozed"] == 0
    assert body["replies"] == [{"id": "ai:12", "who": "Dana Lee", "subject": "Werribee levels", "snippet": "Hi Brad, attached are the levels for…",
                                "draft": "Thanks Dana, I'll check them tomorrow.\n\nBrad", "in_drafts_folder": True, "can_send": True,
                                "created_at": "2026-10-23T06:00:00"}]


def test_send_as_edited_goes_through_sirisai(client, ai):
    r = client.post("/api/v1/attention/ai:12/act", headers=AUTH, json={"action": "send", "body": "Thanks Dana, checking them now."})
    assert r.status_code == 200
    assert ai.acts[-1] == ("/siris/hub/v1/attention/12/act", {"action": "send", "body": "Thanks Dana, checking them now."})
    client.post("/api/v1/attention/ai:12/act", headers=AUTH, json={"action": "send"})
    assert ai.acts[-1][1] == {"action": "send"}  # no edit: SirisAI sends its own draft


def test_snoozing_hides_a_reply_and_an_inbox_item_until_then(client, ai):
    r = client.post("/api/v1/attention/ai:12/snooze", headers=AUTH, json={"until": "tomorrow"})
    assert r.status_code == 200 and r.json()["id"] == "ai:12"
    body = client.get("/api/v1/email/triage", headers=AUTH).json()
    assert body["replies"] == [] and body["snoozed"] == 1
    inbox = client.get("/api/v1/attention", headers=AUTH).json()
    assert [i["id"] for i in inbox["items"] if i["origin"] == "sirisai"] == ["ai:13"] and inbox["snoozed"] == 1
    assert client.post("/api/v1/attention/zz/snooze", headers=AUTH, json={"until": "tomorrow"}).status_code == 404
    assert client.post("/api/v1/attention/ai:12/snooze", headers=AUTH, json={"until": "someday"}).status_code == 422


def test_snooze_times():
    at = datetime(2026, 10, 23, 20, 0, tzinfo=zone())
    assert attention_api.snooze_until("later", at) == at + timedelta(hours=3)
    assert attention_api.snooze_until("tonight", at).date().isoformat() == "2026-10-24"  # already past 7 pm
    assert attention_api.snooze_until("tomorrow", at).hour == 8


def test_sirisai_down(client, monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_ATTENTION_STATE_PATH", str(tmp_path / "a.json"))
    reset_hub({})
    assert client.get("/api/v1/email/triage", headers=AUTH).json() == {"replies": [], "snoozed": 0, "unavailable": True}
