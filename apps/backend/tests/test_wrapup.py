"""The evening wrap-up (2.10): today's tasks, CPD-looking meetings, tomorrow's
top 3 (as tasks, and in tomorrow's brief), the day's line and top 3 to Siris as memories, and the
once-a-day notification."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.brief.service import zone
from app.career import store as career_store
from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.tasks import service as tasks
from app.tasks import store as task_store
from app.wrapup import service
from tests.test_hub import AUTH, ENV


class FakeSirisAI:
    def __init__(self) -> None:
        self.captures: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        today = tasks.today().isoformat()
        if path == "/siris/hub/v1/calendar":
            return httpx.Response(200, json={"start": today, "end": today, "guest_mode": False, "unavailable": False, "events": [
                {"title": "IPWEA stormwater webinar", "start": f"{today}T12:00:00+11:00", "end": f"{today}T13:30:00+11:00", "all_day": False, "location": "Online"},
                {"title": "Werribee design review", "start": f"{today}T14:00:00+11:00", "end": f"{today}T15:00:00+11:00", "all_day": False},
                {"title": "Bin night", "start": today, "end": today, "all_day": True},
            ]})
        if path == "/siris/brain/capture":
            self.captures.append(json.loads(request.content))
            return httpx.Response(200, json={"saved": True, "title": f"Day {today}"})
        if path == "/siris/brain/tasks":
            return httpx.Response(200, json={"tasks": []})
        if path == "/siris/hub/v1/health/overview":
            return httpx.Response(200, json={"guest_mode": False, "available": True, "sources": {"days": 30, "imports": {}},
                                             "readiness": {"score": 72}, "energy": {"start": 79, "now": 31, "spent": {"awake": 20, "activity": 22, "stress": 6}},
                                             "bedtime": {"bedtime": "22:15", "text": "Bed by 10:15 pm for your 6:30 am site visit."}})
        if path == "/siris/hub/v1/reminders":
            return httpx.Response(200, json={"guest_mode": False, "reminders": []})
        return httpx.Response(404, json={"detail": "Not Found"})


@pytest.fixture
def ai(monkeypatch, tmp_path):
    for env, name in (("SIRISOS_TASKS_PATH", "tasks.json"), ("SIRISOS_WRAPUP_PATH", "wrapup.json"), ("SIRISOS_CAREER_PATH", "career.json")):
        monkeypatch.setenv(env, str(tmp_path / name))
    fake = FakeSirisAI()
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(fake))
    reset_hub(ENV)
    yield fake
    reset_hub({})


@pytest.fixture
def client():
    return TestClient(app)


def test_overview_has_todays_tasks_and_cpd_looking_meetings(client, ai):
    today, tomorrow = tasks.today(), tasks.today() + timedelta(days=1)
    done = tasks.add(task_store.Task(title="Send RFI", due=today.isoformat()))
    client.post(f"/api/v1/tasks/sirisos:{done.id}/done", headers=AUTH)
    tasks.add(task_store.Task(title="Call the plumber", due=today.isoformat()))
    tasks.add(task_store.Task(title="Draft the drainage report", due=tomorrow.isoformat()))
    body = client.get("/api/v1/wrapup", headers=AUTH).json()
    assert [t["title"] for t in body["done"]] == ["Send RFI"]
    assert [t["title"] for t in body["open"]] == ["Call the plumber"]
    assert body["suggested_top3"] == ["Draft the drainage report"]
    assert [m["title"] for m in body["meetings"]] == ["IPWEA stormwater webinar", "Werribee design review"]  # no all-day
    webinar, review = body["meetings"]
    assert webinar["cpd"]["hours"] == 1.5 and review["cpd"] is None
    assert body["saved"] is None
    # The day's body (6.1): energy spent against readiness, and tonight's bedtime.
    assert body["health"]["lines"] == ["Energy 79 → 31: a moderate day, against readiness 72.", "Bed by 10:15 pm for your 6:30 am site visit."]


def test_logging_a_meeting_as_cpd_adds_a_task_and_stops_suggesting_it(client, ai):
    webinar = client.get("/api/v1/wrapup", headers=AUTH).json()["meetings"][0]
    r = client.post(f"/api/v1/wrapup/cpd/{webinar['cpd']['key']}", headers=AUTH, json={"title": webinar["title"], "hours": 1.5}).json()
    assert r["task"]["title"] == "Log “IPWEA stormwater webinar” (1.5 h) as CPD in Engineers Australia"
    assert r["task"]["due"] == (tasks.today() + timedelta(days=1)).isoformat()
    assert career_store.load().cpd.suggestions[webinar["cpd"]["key"]] == "logged"
    assert client.get("/api/v1/wrapup", headers=AUTH).json()["meetings"][0]["cpd"] is None


def test_saving_makes_tomorrows_top_3_and_sends_memories_not_a_day_note(client, ai):
    tomorrow = (tasks.today() + timedelta(days=1)).isoformat()
    existing = tasks.add(task_store.Task(title="Draft the drainage report", due=(tasks.today() + timedelta(days=5)).isoformat()))
    r = client.post("/api/v1/wrapup", headers=AUTH, json={"top3": ["Draft the drainage report", "Call Dana", " "],
                     "journal": "Good site visit at Melrose; the pumps arrived. Ran 8 km after work!\nDom's parents are visiting on Saturday. ok"}).json()
    assert r["top3"] == ["Draft the drainage report", "Call Dana"] and r["journal_saved_as"] == "memories"
    titles = {t.title: t.due for t in task_store.load().tasks}
    assert titles["Call Dana"] == tomorrow and titles["Draft the drainage report"] == tomorrow  # moved up, not duplicated
    assert sum(1 for t in task_store.load().tasks if t.title == "Draft the drainage report") == 1 and existing.id
    today = tasks.today()
    # One memory per sentence, each filed on its own; tomorrow's top 3 stay out of Siris (5.61).
    d = today.strftime('%A %-d %B %Y')
    assert ai.captures == [
        {"text": f"{d}: Good site visit at Melrose; the pumps arrived.", "kind": "memory", "tags": ["wrap-up"]},
        {"text": f"{d}: Ran 8 km after work!", "kind": "memory", "tags": ["wrap-up"]},
        {"text": f"{d}: Dom's parents are visiting on Saturday.", "kind": "memory", "tags": ["wrap-up"]},
    ]
    assert not any("focus" in c["text"] or "Call Dana" in c["text"] for c in ai.captures)
    assert not any("title" in c for c in ai.captures)  # never a "Day …" note
    assert service.top3_for(tasks.today() + timedelta(days=1)) == ["Draft the drainage report", "Call Dana"]
    assert client.get("/api/v1/wrapup", headers=AUTH).json()["saved"]["top3"] == ["Draft the drainage report", "Call Dana"]
    assert client.post("/api/v1/wrapup", headers=AUTH, json={"top3": ["a", "b", "c", "d"]}).status_code == 422


def test_the_notification_comes_once_after_the_hour_until_it_is_done(ai, monkeypatch):
    monkeypatch.setenv("SIRISOS_WRAPUP_HOUR", "17")
    day = datetime.now(zone()).replace(hour=16, minute=0)
    assert service.push_message(day) == []
    msgs = service.push_message(day.replace(hour=17, minute=5))
    assert msgs[0]["title"] == "Wrap up your day" and msgs[0]["url"] == "/wrapup" and msgs[0]["key"].startswith("wrapup:")
    service._load()  # nothing saved yet
    import asyncio

    asyncio.run(service.save(hub_service.get_hub(), day.date(), [], ""))
    assert service.push_message(day.replace(hour=18)) == []
