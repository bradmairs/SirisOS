"""The weekly review (3.5): the week's numbers, quiet projects, next week's
crunch points, the 'what matters' note (to Siris, and on This week) and the
Sunday notification."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.brief.service import zone
from app.career import store as career_store
from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.review import service
from app.tasks import service as tasks
from app.tasks import store as task_store
from tests.test_hub import AUTH, ENV

TODAY = tasks.today()
MONDAY, SUNDAY = service.week_of(TODAY)
NEXT = MONDAY + timedelta(days=7)


def _at(day: date, hour: int, minutes: int = 0) -> str:
    return datetime(day.year, day.month, day.day, hour, minutes, tzinfo=zone()).isoformat()


class FakeSirisAI:
    def __init__(self) -> None:
        self.captures: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path, params = request.url.path, request.url.params
        if path == "/siris/brain/insights":
            return httpx.Response(200, json={"summary": {"this_week": 12, "previous_week": 8},
                                             "stale_projects": [{"title": "Garden shed", "days_idle": 40}],
                                             "deadlines": [{"title": "Werribee Drainage", "days_left": (NEXT - TODAY).days + 2}]})
        if path == "/siris/hub/v1/health/days":
            return httpx.Response(200, json={"guest_mode": False, "days": [
                {"date": MONDAY.isoformat(), "metrics": {"running_km": 5.2, "exercise_minutes": 35}},
                {"date": TODAY.isoformat(), "metrics": {"running_km": 4.0, "exercise_minutes": 30}}]})
        if path == "/siris/hub/v1/calendar":
            start = date.fromisoformat(params["start"])
            if start == NEXT:
                tue = NEXT + timedelta(days=1)
                events = [{"title": f"Meeting {i}", "start": _at(tue, 9 + i), "end": _at(tue, 10 + i), "all_day": False} for i in range(4)]
                events.append({"title": "Site visit", "start": _at(NEXT + timedelta(days=3), 10), "end": _at(NEXT + timedelta(days=3), 12), "all_day": False})
                events.append({"title": "Design review", "start": _at(NEXT + timedelta(days=3), 11), "end": _at(NEXT + timedelta(days=3), 12), "all_day": False})
                return httpx.Response(200, json={"events": events, "guest_mode": False, "unavailable": False})
            return httpx.Response(200, json={"events": [{"title": "Standup", "start": _at(MONDAY, 9), "end": _at(MONDAY, 9, 15), "all_day": False}], "guest_mode": False, "unavailable": False})
        if path == "/siris/brain/capture":
            self.captures.append(json.loads(request.content))
            return httpx.Response(200, json={"saved": True, "title": self.captures[-1]["title"]})
        if path == "/siris/brain/tasks":
            return httpx.Response(200, json={"tasks": []})
        if path == "/siris/hub/v1/reminders":
            return httpx.Response(200, json={"guest_mode": False, "reminders": []})
        return httpx.Response(404)


@pytest.fixture
def ai(monkeypatch, tmp_path):
    for env, name in (("SIRISOS_TASKS_PATH", "tasks.json"), ("SIRISOS_WRAPUP_PATH", "wrapup.json"),
                      ("SIRISOS_CAREER_PATH", "career.json"), ("SIRISOS_REVIEW_PATH", "review.json")):
        monkeypatch.setenv(env, str(tmp_path / name))
    fake = FakeSirisAI()
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(fake))
    reset_hub(ENV)
    yield fake
    reset_hub({})


def test_the_week_in_numbers_and_whats_next(ai):
    t = tasks.add(task_store.Task(title="Send RFI"))
    doc = task_store.load()
    doc.tasks[0].done_at = datetime.now(zone()).isoformat()
    task_store.save(doc)
    tasks.add(task_store.Task(title="Submit the drainage report", due=(NEXT + timedelta(days=2)).isoformat()))
    career = career_store.load()
    career.cpd.records.append(career_store.CpdRecord(id="r1", title="IPWEA webinar", date=TODAY.isoformat(), hours=1.5))
    career_store.save(career)

    body = TestClient(app).get("/api/v1/review", headers=AUTH).json()
    n = body["numbers"]
    assert body["week_of"] == MONDAY.isoformat() and n["tasks_done"] == 1 and body["done"] == ["Send RFI"] and t.id
    assert (n["notes"], n["notes_before"], n["cpd_hours"], n["meetings"]) == (12, 8, 1.5, 1)
    if TODAY != MONDAY:
        assert (n["runs"], n["run_km"], n["exercise_minutes"]) == (2, 9.2, 65)
    assert body["quiet"][0]["title"] == "Garden shed"
    nxt = body["next_week"]
    assert nxt["meetings"] == 6
    assert [d["meetings"] for d in nxt["busy_days"]] == [4, 2] and nxt["busy_days"][1]["clashes"] == ["Site visit and Design review"]
    assert [t["title"] for t in nxt["tasks"]] == ["Submit the drainage report"]
    assert nxt["deadlines"][0]["title"] == "Werribee Drainage"


def test_what_matters_goes_to_siris_and_this_week(ai):
    client = TestClient(app)
    r = client.post("/api/v1/review", headers=AUTH, json={"focus": "Finish the Werribee report; book the dentist."}).json()
    assert r["saved_as"].startswith(f"Week {MONDAY.isocalendar().week} review")
    assert ai.captures[0]["tags"] == ["weekly-review"] and "Finish the Werribee report" in ai.captures[0]["text"]
    assert client.get("/api/v1/review", headers=AUTH).json()["saved"]["focus"].startswith("Finish")
    assert service.latest_focus(NEXT) == {"week_of": NEXT.isoformat(), "text": "Finish the Werribee report; book the dentist."}
    assert service.latest_focus(TODAY) is None


def test_the_sunday_notification(ai, monkeypatch):
    monkeypatch.setenv("SIRISOS_REVIEW_WEEKDAY", "6")
    monkeypatch.setenv("SIRISOS_REVIEW_HOUR", "16")
    sunday = datetime(SUNDAY.year, SUNDAY.month, SUNDAY.day, 17, tzinfo=zone())
    assert service.push_message(sunday)[0]["url"] == "/review"
    assert service.push_message(sunday.replace(hour=10)) == []
    assert service.push_message(sunday - timedelta(days=1)) == []
    import asyncio

    asyncio.run(service.save(hub_service.get_hub(), SUNDAY, ""))
    assert service.push_message(sunday) == []
