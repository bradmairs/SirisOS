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
    assert [e["title"] for e in d["events"]] == ["Design review"] and d["next"]["in_minutes"] == 60
    assert [t["title"] for t in d["tasks"]["groups"]["today"]] == ["Check the pump station drawings"]
    assert [p["title"] for p in d["projects"]] == ["GVW Sewer Upgrade"] and d["projects"][0]["open_tasks"] == 1
    assert [t["task"] for t in d["todos"]] == ["Issue RFI 3"]
    assert d["cpd"]["required"] == 150
