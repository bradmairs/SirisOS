"""Meeting prep (3.2): the meeting's people, related Siris notes, the latest
emails from them, related tasks; notes filed into Siris with action lines
as tasks; and the 10-minute heads-up."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.brief.service import zone
from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.meetings import service
from app.tasks import store as task_store
from tests.test_hub import AUTH, ENV

SOON = (datetime.now(zone()) + timedelta(minutes=8)).replace(second=0, microsecond=0)
LATER = SOON + timedelta(hours=1)


class FakeSirisAI:
    def __init__(self) -> None:
        self.searches: list[str] = []
        self.email_params: list[list[tuple[str, str]]] = []
        self.captures: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/siris/hub/v1/calendar":
            return httpx.Response(200, json={"events": [
                {"title": "Werribee drainage design review", "start": SOON.isoformat(), "end": LATER.isoformat(), "all_day": False,
                 "location": "GVW Shepparton", "attendees": ["dana.lee@example.com", "sam_wu@example.com"]},
                {"title": "Lunch", "start": LATER.isoformat(), "end": (LATER + timedelta(hours=1)).isoformat(), "all_day": False, "attendees": []},
            ], "guest_mode": False, "unavailable": False})
        if path == "/siris/brain/search":
            q = request.url.params["q"]
            self.searches.append(q)
            hits = {"Werribee drainage design": [{"title": "Werribee Drainage", "type": "project", "excerpts": ["Levels due to Dana by Friday."]}],
                    "Dana Lee": [{"title": "Dana Lee", "type": "person", "excerpts": ["Senior engineer at GVW."]},
                                 {"title": "Werribee Drainage", "type": "project", "excerpts": []}]}
            return httpx.Response(200, json=hits.get(q, []))
        if path == "/siris/hub/v1/email/with":
            self.email_params.append(list(request.url.params.multi_items()))
            return httpx.Response(200, json={"guest_mode": False, "configured": True, "messages": [
                {"uid": "41", "sender": "Dana Lee", "subject": "Werribee levels", "date": "Tue, 20 Oct 2026 09:12:00 +1100", "snippet": "Attached."}]})
        if path == "/siris/brain/capture":
            self.captures.append(json.loads(request.content))
            return httpx.Response(200, json={"saved": True, "title": self.captures[-1]["title"]})
        if path in ("/siris/brain/tasks",):
            return httpx.Response(200, json={"tasks": [{"task": "Send Werribee levels", "note": "Werribee Drainage", "due": None, "type": "project"}]})
        if path == "/siris/hub/v1/reminders":
            return httpx.Response(200, json={"guest_mode": False, "reminders": []})
        return httpx.Response(404)


@pytest.fixture
def ai(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_TASKS_PATH", str(tmp_path / "tasks.json"))
    service._cache.clear()
    fake = FakeSirisAI()
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(fake))
    reset_hub(ENV)
    yield fake
    reset_hub({})
    service._cache.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_names_and_keywords():
    assert service.name_of("dana.lee@example.com") == "Dana Lee"
    assert service.name_of("sam_wu+gvw@example.com") == "Sam Wu Gvw"
    assert service.keywords("Weekly catch up re: Werribee drainage design review") == "Werribee drainage design"


def test_upcoming_lists_meetings_still_to_come(client, ai):
    body = client.get("/api/v1/meetings", headers=AUTH).json()
    if SOON.date() == datetime.now(zone()).date():
        assert body["meetings"][0]["title"] == "Werribee drainage design review"
        assert body["meetings"][0]["attendees"] == ["dana.lee@example.com", "sam_wu@example.com"]


def test_prep_brings_notes_emails_people_and_tasks(client, ai):
    r = client.get("/api/v1/meetings/prep", headers=AUTH, params={"title": "Werribee drainage design review", "start": SOON.isoformat()}).json()
    assert r["found"] is True and r["location"] == "GVW Shepparton"
    assert r["people"] == [{"email": "dana.lee@example.com", "name": "Dana Lee"}, {"email": "sam_wu@example.com", "name": "Sam Wu"}]
    assert [n["title"] for n in r["notes"]] == ["Werribee Drainage", "Dana Lee"]  # no duplicates
    assert ai.searches[:2] == ["Werribee drainage design", "Dana Lee"]
    assert r["emails"][0]["subject"] == "Werribee levels"
    assert ("address", "dana.lee@example.com") in ai.email_params[0] and ("address", "sam_wu@example.com") in ai.email_params[0]
    assert [t["title"] for t in r["tasks"]] == ["Send Werribee levels"]


def test_prep_for_a_meeting_not_on_the_calendar(client, ai):
    r = client.get("/api/v1/meetings/prep", headers=AUTH, params={"title": "Werribee drainage design"}).json()
    assert r["found"] is False and r["people"] == [] and r["emails"] is None and r["notes"]


def test_notes_go_to_siris_and_action_lines_become_tasks(client, ai):
    text = "Dana to send levels.\n- [ ] Update the pipe sizing tomorrow\nTODO: book site visit on Friday\nNice chat."
    r = client.post("/api/v1/meetings/notes", headers=AUTH, json={"title": "Werribee drainage design review", "start": SOON.isoformat(), "text": text}).json()
    assert r["tasks"] == ["Update the pipe sizing", "Book site visit"]
    assert ai.captures[0] == {"title": f"Meeting: Werribee drainage design review ({SOON.date().isoformat()})", "text": text, "tags": ["meeting"]}
    made = {t.title: t for t in task_store.load().tasks}
    assert made["Update the pipe sizing"].due and made["Book site visit"].notes.startswith("From Werribee drainage design review")


def test_heads_up_ten_minutes_before_a_meeting_with_people(ai):
    import asyncio

    msgs = asyncio.run(service.push_messages(hub_service.get_hub(), datetime.now(zone())))
    if SOON.date() == datetime.now(zone()).date():
        assert [m["title"] for m in msgs] == [f"In {int((SOON - datetime.now(zone())).total_seconds() // 60)} min: Werribee drainage design review"] or msgs[0]["title"].startswith("In ")
        assert msgs[0]["url"].startswith("/meeting?title=Werribee")
