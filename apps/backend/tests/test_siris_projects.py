"""4.0: Projects, one page per Siris project."""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.siris_projects import service
from app.tasks import service as tasks
from app.tasks import store as task_store
from tests.test_hub import AUTH, ENV

TODAY = tasks.today()
asked: list[str] = []


def handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    asked.append(str(request.url))
    if path == "/siris/brain/projects":
        return httpx.Response(200, json={"projects": [
            {"title": "Akaroa Upgrade", "status": "done", "aliases": [], "path": "01-Projects/Akaroa Upgrade.md"},
            {"title": "CPEng Chartership", "status": "active", "aliases": ["CPEng"], "path": "01-Projects/CPEng Chartership.md"},
            {"title": "Werribee Drainage", "status": "active", "aliases": ["WD"], "path": "Work/GVW/Projects/Werribee Drainage.md"},
        ]})
    if path == "/siris/brain/insights":
        return httpx.Response(200, json={"deadlines": [{"title": "Werribee Drainage", "due": (TODAY + timedelta(days=4)).isoformat(), "days_left": 4}],
                                         "stale_projects": [{"title": "CPEng Chartership", "days_idle": 19}]})
    if path == "/siris/brain/tasks":
        return httpx.Response(200, json={"tasks": [{"task": "Send levels to Dana", "note": "Werribee Drainage", "due": None, "type": "project"},
                                                   {"task": "Book referee call", "note": "CPEng Chartership", "due": None, "type": "project"}]})
    if path == "/siris/brain/note":
        return httpx.Response(200, json={"title": "Werribee Drainage", "meta": {"areas": ["Work"], "source": "GVW"}, "as_of": "2026-10-20",
                                         "body": "# Werribee Drainage\n\nUpgrading the [[Werribee]] outfall drains for [[GVW|Greater Western Water]].\n\n## Connections\n- [[Dana Lee]]",
                                         "links": ["Dana Lee", "Werribee"], "backlinks": ["GVW Projects"]})
    if path == "/siris/hub/v1/reminders":
        return httpx.Response(200, json={"guest_mode": False, "reminders": []})
    if path == "/siris/hub/v1/calendar":
        return httpx.Response(200, json={"guest_mode": False, "unavailable": False, "events": [
            {"title": "WD design review", "start": f"{(TODAY + timedelta(days=2)).isoformat()}T10:00:00+11:00", "end": None, "all_day": False, "location": None, "calendar": "Work"},
            {"title": "Werribee site walk", "start": f"{(TODAY - timedelta(days=3)).isoformat()}T09:00:00+11:00", "end": None, "all_day": False, "location": None, "calendar": "Work"},
            {"title": "Dentist", "start": f"{TODAY.isoformat()}T15:00:00+11:00", "end": None, "all_day": False, "location": None, "calendar": "Home"},
            {"title": "Swords", "start": f"{TODAY.isoformat()}T15:00:00+11:00", "end": None, "all_day": False, "location": None, "calendar": "Home"},
        ]})
    if path == "/siris/hub/v1/email/about":
        return httpx.Response(200, json={"guest_mode": False, "configured": True, "messages": [
            {"uid": "41", "sender": "Dana Lee", "subject": "Werribee Drainage levels", "date": "Tue, 20 Oct 2026 09:12:00 +1100", "snippet": "Attached."}]})
    if path == "/siris/brain/done":
        return httpx.Response(200, json={"action": "project-done", "note": "Werribee Drainage"})
    return httpx.Response(404)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_TASKS_PATH", str(tmp_path / "tasks.json"))
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    asked.clear()
    reset_hub(ENV)
    yield TestClient(app)


def test_mentions_match_whole_words():
    assert service.mentions("WD design review", ["WD"])
    assert not service.mentions("Swords", ["WD"])
    assert not service.mentions("crowd at wd-40", ["WD"])
    assert service.names({"title": "Werribee Drainage", "aliases": ["WD", "x"]}) == ["Werribee Drainage", "WD"]


def test_overview_orders_by_deadline_and_finished_last(client):
    body = client.get("/api/v1/siris-projects", headers=AUTH).json()
    assert [p["title"] for p in body["projects"]] == ["Werribee Drainage", "CPEng Chartership", "Akaroa Upgrade"]
    wd, cpeng = body["projects"][:2]
    assert (wd["days_left"], wd["open_tasks"]) == (4, 1)
    assert cpeng["days_idle"] == 19 and cpeng["days_left"] is None


def test_a_project_page_gathers_everything(client):
    task_store.save(task_store.TasksDocument(tasks=[task_store.Task(id="a", title="Ring Dana about WD"), task_store.Task(id="b", title="Buy milk")]))
    body = client.get("/api/v1/siris-projects/werribee drainage", headers=AUTH).json()
    assert body["title"] == "Werribee Drainage" and body["names"] == ["Werribee Drainage", "WD"]
    assert body["about"] == "Upgrading the Werribee outfall drains for Greater Western Water."
    assert body["links"] == ["Dana Lee", "Werribee"] and body["backlinks"] == ["GVW Projects"] and body["areas"] == ["Work"]
    assert body["deadline"]["days_left"] == 4
    assert sorted(t["title"] for t in body["tasks"]) == ["Ring Dana about WD", "Send levels to Dana"]
    assert [e["title"] for e in body["meetings"]["upcoming"]] == ["WD design review"]
    assert body["emails"][0]["subject"] == "Werribee Drainage levels" and body["unavailable"] == []
    assert any(u.endswith("email/about?q=Werribee+Drainage&limit=6") for u in asked)  # "WD" is too short for a subject search


def test_aliases_find_tasks_and_meetings(client, monkeypatch):
    real = handler

    def with_alias(request):
        if request.url.path == "/siris/brain/projects":
            return httpx.Response(200, json={"projects": [{"title": "Werribee Drainage", "status": "active", "aliases": ["WD", "Werribee"], "path": ""}]})
        return real(request)

    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(with_alias))
    reset_hub(ENV)
    task_store.save(task_store.TasksDocument(tasks=[task_store.Task(id="a", title="Ring Dana about WD"), task_store.Task(id="b", title="Buy milk")]))
    body = client.get("/api/v1/siris-projects/Werribee Drainage", headers=AUTH).json()
    assert sorted(t["title"] for t in body["tasks"]) == ["Ring Dana about WD", "Send levels to Dana"]
    assert [e["title"] for e in body["meetings"]["upcoming"]] == ["WD design review"]
    assert [e["title"] for e in body["meetings"]["recent"]] == ["Werribee site walk"]


def test_unknown_project_and_actions(client):
    assert client.get("/api/v1/siris-projects/Nope", headers=AUTH).status_code == 404
    made = client.post("/api/v1/siris-projects/Werribee Drainage/tasks", headers=AUTH, json={"text": "send levels tomorrow"}).json()
    assert made["notes"] == "Project: Werribee Drainage" and made["due"] == (TODAY + timedelta(days=1)).isoformat()
    body = client.get("/api/v1/siris-projects/Werribee Drainage", headers=AUTH).json()
    assert any(t["id"] == f"sirisos:{made['id']}" for t in body["tasks"])
    assert client.post("/api/v1/siris-projects/Werribee Drainage/done", headers=AUTH).json()["action"] == "project-done"


def test_without_sirisai(client, monkeypatch):
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(lambda r: httpx.Response(404)))
    reset_hub(ENV)
    assert client.get("/api/v1/siris-projects", headers=AUTH).json() == {"projects": [], "available": False}
