"""4.3: talk to SirisOS."""

from __future__ import annotations

import json
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.command import service
from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.tasks import store as task_store
from tests.test_hub import AUTH, ENV

TODAY = date(2026, 10, 23)  # a Friday
asked: list[tuple[str, dict | None]] = []


def handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content) if request.content else None
    asked.append((request.url.path, body))
    if request.url.path == "/siris/hub/v1/calendar":
        start = request.url.params["start"]
        events = [
            {"title": "Site visit, Werribee", "start": f"{start}T09:30:00+11:00", "end": None, "all_day": False, "location": None, "calendar": "Work"},
            {"title": "Bin night", "start": start, "end": None, "all_day": True, "location": None, "calendar": "Home"},
        ] if start == (TODAY + timedelta(days=1)).isoformat() else []
        return httpx.Response(200, json={"guest_mode": False, "unavailable": False, "events": events})
    if request.url.path == "/siris/ask":
        return httpx.Response(200, text="It'll be 19 degrees and showery.", headers={"X-Conversation-Id": "c1"})
    if request.url.path == "/siris/brain/capture":
        return httpx.Response(200, json={"saved": True, "title": "Werribee levels"})
    return httpx.Response(404)


@pytest.fixture
def run(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_TASKS_PATH", str(tmp_path / "tasks.json"))
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    asked.clear()
    reset_hub(ENV)
    import asyncio

    return lambda text: asyncio.run(service.run(hub_service.get_hub(), text, TODAY))


@pytest.mark.parametrize("text, title, due, at", [
    ("Add a task to call the plumber Friday", "Call the plumber", "2026-10-30", None),
    ("remind me to put the bins out tonight", "Put the bins out", "2026-10-23", "19:00"),
    ("add task send levels to Dana tomorrow at 9am", "Send levels to Dana", "2026-10-24", "09:00"),
    ("todo: renew rego", "Renew rego", None, None),
])
def test_tasks(run, text, title, due, at):
    r = run(text)
    assert r["intent"] == "task" and (r["task"]["title"], r["task"]["due"], r["task"]["time"]) == (title, due, at)
    assert task_store.load().tasks[-1].title == title


def test_task_reply_says_when(run):
    assert run("remind me to call Dad tomorrow at 5:30pm")["reply"] == "Added: Call Dad, tomorrow at 5:30 pm."


def test_cpd(run):
    r = run("Log 1.5 hours CPD for today's stormwater webinar")
    assert r["intent"] == "cpd" and r["reply"] == "I'll remind you tomorrow to log 1.5 hours for stormwater webinar in Engineers Australia."
    t = task_store.load().tasks[-1]
    assert t.title == "Log “Stormwater webinar” (1.5 h) as CPD in Engineers Australia" and t.due == "2026-10-24"
    assert run("record an hour of CPD on the AS3500 refresher")["reply"].startswith("I'll remind you tomorrow to log 1 hour for AS3500")


def test_whats_on(run):
    r = run("What's on tomorrow?")
    assert r["intent"] == "calendar" and r["reply"] == "Tomorrow: 9:30 am Site visit, Werribee; Bin night (all day)."
    assert run("what's on Tuesday")["reply"] == "Nothing in the calendar for Tuesday."
    assert run("what's on")["reply"] == "Nothing in the calendar today."


def test_note_and_ask(run):
    r = run("note: the Werribee levels are in the shared drive")
    assert r == {"intent": "note", "reply": "Saved to Siris.", "link": "/brain", "title": "Werribee levels"}
    assert asked[-1] == ("/siris/brain/capture", {"text": "the Werribee levels are in the shared drive", "tags": ["voice"]})
    r = run("what's the weather tomorrow")
    assert r["intent"] == "ask" and r["reply"] == "It'll be 19 degrees and showery." and r["conversation_id"] == "c1"
    assert asked[-1][1]["prompt"].endswith("what's the weather tomorrow")


def test_api(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_TASKS_PATH", str(tmp_path / "tasks.json"))
    client = TestClient(app)
    assert client.post("/api/v1/command", json={"text": "todo: x"}).status_code == 401
    assert client.post("/api/v1/command", headers=AUTH, json={"text": "todo: buy milk"}).json()["reply"] == "Added: Buy milk."
    assert client.post("/api/v1/command", headers=AUTH, json={"text": ""}).status_code == 422
