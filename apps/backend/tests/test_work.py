"""7.2: the Work dashboard and the working day from 8:00."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

import pytest

from app.brief.service import zone
from app.home import schedule
from app.hub import sirisai_api
from app.tasks import store as tasks_store
from app.work import service


@pytest.fixture(autouse=True)
def _paths(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_HOME_SCHEDULE_PATH", str(tmp_path / "home-schedule.json"))
    monkeypatch.setenv("SIRISOS_TASKS_PATH", str(tmp_path / "tasks.json"))
    monkeypatch.setenv("SIRISOS_PROJECTS_PATH", str(tmp_path / "projects.json"))
    monkeypatch.setenv("SIRISOS_CAREER_PATH", str(tmp_path / "career.json"))
    monkeypatch.setenv("SIRISOS_PROJECT_CONTEXT_PATH", str(tmp_path / "project-context.json"))


def test_a_schedule_on_the_old_830_start_moves_to_8_once(tmp_path):
    (tmp_path / "home-schedule.json").write_text(json.dumps({"weekday": {"morning": "05:00", "day": "08:30", "evening": "16:30", "night": "23:00"}}))
    assert schedule.load().weekday.day == "08:00"
    plan = schedule.load()
    plan.weekday = plan.weekday.model_copy(update={"day": "08:30"})
    schedule.save(plan)  # chosen again after the move: kept
    assert schedule.load().weekday.day == "08:30"


def test_the_dashboard_brings_the_working_day_together(monkeypatch):
    at = datetime(2026, 11, 5, 10, 0, tzinfo=zone())  # a Thursday

    async def get(hub, path, params=None, timeout=20.0):
        if path == "/siris/hub/v1/calendar":
            return {"events": [{"title": "Design review", "start": "2026-11-05T11:00:00+11:00", "end": "2026-11-05T12:00:00+11:00", "location": "Shepparton"},
                               {"title": "Tomorrow", "start": "2026-11-06T09:00:00+11:00"}]}
        if path == "/siris/brain/projects":
            return {"projects": [{"title": "GVW Sewer Upgrade", "path": "Work/GVW/Projects/GVW Sewer Upgrade.md", "status": "active"},
                                 {"title": "Home Lab", "path": "01-Projects/Home Lab.md", "status": "active"}]}
        if path == "/siris/brain/insights":
            return {"deadlines": [{"title": "GVW Sewer Upgrade", "due": "2026-11-20", "days_left": 15}]}
        if path == "/siris/brain/tasks":
            return {"tasks": [{"task": "Issue RFI 3", "note": "GVW Sewer Upgrade", "due": "2026-11-07"}, {"task": "Flash router", "note": "Home Lab"}]}
        return None

    monkeypatch.setattr(sirisai_api, "get", get)
    tasks_store.save(tasks_store.TasksDocument(tasks=[tasks_store.Task(title="Check the pump station drawings", due="2026-11-05"),
                                                      tasks_store.Task(title="Buy milk", due="2026-11-05")]))
    monkeypatch.setattr(service.tasks, "today", lambda: at.date())
    d = asyncio.run(service.dashboard(None, at))
    assert d["hours"] == {"start": "08:00", "end": "16:30", "on": True, "workday": True, "minutes_left": 390, "minutes_in": 120}
    assert "events" not in d and "next" not in d and "projects" not in d  # 7.31: no calendar, no projects
    assert [t["title"] for t in d["tasks"]["groups"]["today"]] == ["Check the pump station drawings"]
    assert [t["task"] for t in d["todos"]] == ["Issue RFI 3"]
    assert d["cpd"]["required"] == 150


def test_the_week_focus_apps_notes_and_logging_cpd(monkeypatch, tmp_path):
    """7.4: the visuals' data: work done this week (tasks and note to-dos), focus minutes, work app links, recent work notes, CPD."""
    from fastapi.testclient import TestClient

    from app.entrypoint import app
    from app.links import store as links
    from tests.test_hub import AUTH

    monkeypatch.setenv("SIRISOS_WORK_PATH", str(tmp_path / "work.json"))
    monkeypatch.setenv("SIRISOS_LINKS_PATH", str(tmp_path / "links.json"))
    at = datetime(2026, 11, 5, 10, 0, tzinfo=zone())  # a Thursday
    tasks_store.save(tasks_store.TasksDocument(tasks=[
        tasks_store.Task(title="Send the RFI to the client", done_at="2026-11-04T01:00:00+00:00", area="work"),
        tasks_store.Task(title="Buy milk", done_at="2026-11-04T01:00:00+00:00")]))
    service.add_focus(at.date(), 25)
    service.add_focus(at.date(), 25)
    service.add_todo_done(at.date())
    links.save(links.LinksDocument(groups=[links.LinkGroup(name="Apps", links=[
        links.Link(name="GVW", url="https://gvw.sirishome.org"), links.Link(name="Plex", url="http://plex.local")])]))

    async def get(hub, path, params=None, timeout=20.0):
        if path == "/siris/brain/recent":
            assert params == {"folder": "Work", "limit": 6}
            return [{"title": "Pump Stations", "path": "Work/GVW/Pump Stations.md", "as_of": "2026-11-05", "excerpt": "Wet wells", "tags": []}]
        return None

    monkeypatch.setattr(sirisai_api, "get", get)
    monkeypatch.setattr(service.tasks, "today", lambda: at.date())
    d = asyncio.run(service.dashboard(None, at))
    wk = {x["weekday"]: x for x in d["week"]["days"]}
    assert wk["Wed"]["done"] == 1 and wk["Thu"]["done"] == 1 and wk["Thu"]["focus_min"] == 50 and d["week"]["focus_today"] == 50
    assert [a["name"] for a in d["apps"]] == ["GVW"]
    assert d["notes"][0]["title"] == "Pump Stations"
    assert {m["category"] for m in d["cpd"]["minimums"]} == {"area", "risk", "business"}
    client = TestClient(app)
    r = client.post("/api/v1/work/cpd", headers=AUTH, json={"title": "Safety in design webinar", "hours": 1.5, "category": "risk", "date": "2026-11-05"}).json()
    assert r["record"]["basis"] == "you" and r["record"]["split"] == {"risk": 1.5}
    assert next(m for m in r["cpd"]["minimums"] if m["category"] == "risk")["hours"] >= 1.5
    assert client.post("/api/v1/work/focus", headers=AUTH, json={"minutes": 25}).json()["today"] >= 25
