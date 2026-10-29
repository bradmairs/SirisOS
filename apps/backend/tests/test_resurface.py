"""5.1: one older related Siris note a day."""

from __future__ import annotations

import asyncio
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.resurface import service
from app.tasks import store as task_store
from tests.test_hub import AUTH, ENV

TODAY = date(2026, 10, 29)
NOTES = {
    "Pipe Materials": {"as_of": "2026-03-01", "body": "PE100 vs DICL for rising mains."},
    "Pump Notes": {"as_of": "2026-10-20", "body": "Too recent."},
    "Old Pump Station Lessons": {"as_of": "2025-11-02", "body": "Wet wells need a bigger sump."},
    "GVW Variations": {"as_of": "2025-01-01", "body": "Work."},
}


def handler(request: httpx.Request) -> httpx.Response:
    path, q = request.url.path, request.url.params
    if path == "/siris/brain/projects":
        return httpx.Response(200, json={"projects": [{"title": "Home Lab", "status": "active", "aliases": [], "path": "01-Projects/Home Lab.md"}]})
    if path == "/siris/hub/v1/calendar":
        return httpx.Response(200, json={"events": [{"title": "GVW site walk"}], "guest_mode": False})
    if path == "/siris/brain/search":
        if q["q"] == "Home Lab":
            return httpx.Response(200, json=[
                {"title": "Home Lab", "path": "01-Projects/Home Lab.md", "type": "project", "score": 20, "excerpts": []},
                {"title": "Pump Notes", "path": "Notes/Pump Notes.md", "type": "note", "score": 9, "excerpts": ["recent"]},
                {"title": "GVW Variations", "path": "Work/GVW/GVW Variations.md", "type": "note", "score": 8, "excerpts": []},
                {"title": "Pipe Materials", "path": "Notes/Pipe Materials.md", "type": "note", "score": 5, "excerpts": ["PE100 vs DICL"]},
                {"title": "Old Pump Station Lessons", "path": "Notes/Old.md", "type": "note", "score": 4, "excerpts": ["Wet wells"]},
            ])
        return httpx.Response(200, json=[])
    if path == "/siris/brain/note":
        n = NOTES.get(q["title"])
        return httpx.Response(200, json={"title": q["title"], **n}) if n else httpx.Response(404)
    return httpx.Response(404)


@pytest.fixture
def setup(monkeypatch, tmp_path):
    for env, name in (("SIRISOS_RESURFACE_PATH", "r.json"), ("SIRISOS_TASKS_PATH", "t.json")):
        monkeypatch.setenv(env, str(tmp_path / name))
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    reset_hub(ENV)
    task_store.save(task_store.TasksDocument())


def run(coro):
    return asyncio.run(coro)


def test_picks_an_older_related_note_and_keeps_it_for_the_day(setup):
    hub = hub_service.get_hub()
    note = run(service.today_note(hub, TODAY))["note"]
    # Not the project itself, not a recent note, never a work note.
    assert note["title"] == "Pipe Materials"
    assert note["why"] == "Related to your project Home Lab" and note["age_days"] == 242 and note["excerpt"] == "PE100 vs DICL"
    assert run(service.today_note(hub, TODAY))["note"]["title"] == "Pipe Materials"
    # Shown recently: tomorrow it's someone else's turn.
    assert run(service.today_note(hub, date(2026, 10, 30)))["note"]["title"] == "Old Pump Station Lessons"


def test_not_useful_never_again_and_seen_closes_it(setup):
    client = TestClient(app)
    hub = hub_service.get_hub()
    run(service.today_note(hub, service.tasks.today()))
    first = client.get("/api/v1/resurface", headers=AUTH).json()["note"]["title"]
    r = client.post("/api/v1/resurface/respond", headers=AUTH, json={"title": first, "answer": "not_useful"})
    second = r.json()["note"]["title"]
    assert second != first and first in service._load()["dismissed"]
    client.post("/api/v1/resurface/respond", headers=AUTH, json={"title": second, "answer": "seen"})
    assert client.get("/api/v1/resurface", headers=AUTH).json() == {"note": None}
