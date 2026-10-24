"""4.4: yearly goals on Your year."""

from __future__ import annotations

import asyncio
from datetime import date, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app.career import store as career_store
from app.entrypoint import app
from app.goals import service
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.trends import log
from tests.test_hub import AUTH, ENV

TODAY = date(2026, 7, 2)  # the middle of the year


def handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/siris/hub/v1/health/days":
        return httpx.Response(200, json={"guest_mode": False, "days": [
            {"date": "2025-12-30", "metrics": {"running_km": 50}},   # last year: not counted
            {"date": "2026-01-10", "metrics": {"running_km": 300}},
            {"date": "2026-06-30", "metrics": {"running_km": 150.5}}]})
    return httpx.Response(404)


@pytest.fixture
def setup(monkeypatch, tmp_path):
    for env, name in (("SIRISOS_GOALS_PATH", "goals.json"), ("SIRISOS_TRENDS_PATH", "t.json"), ("SIRISOS_CAREER_PATH", "c.json"),
                      ("SIRISOS_TASKS_PATH", "tasks.json"), ("SIRISOS_WRAPUP_PATH", "w.json")):
        monkeypatch.setenv(env, str(tmp_path / name))
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    reset_hub(ENV)


def overview(year=2026, today=TODAY):
    return asyncio.run(service.overview(hub_service.get_hub(), year, today))


def test_measured_goals_track_themselves(setup):
    service.add(2026, service.Goal(title="Run 950 km", kind="running_km", target=950))
    service.add(2026, service.Goal(title="40 CPD hours", kind="cpd_hours", target=40))
    service.add(2026, service.Goal(title="Journal 100 days", kind="journal_days", target=100))
    doc = career_store.load()
    doc.cpd.records = [career_store.CpdRecord(id="1", date="2026-03-01", hours=25, title="Course"),
                       career_store.CpdRecord(id="2", date="2025-11-01", hours=9, title="Old")]
    career_store.save(doc)
    log.mark("journal", date(2026, 5, 1))
    body = overview()
    run, cpd, journal = body["goals"]
    assert body["through_year"] == 50 and run["unit"] == "km"
    assert (run["value"], run["percent"], run["state"]) == (450.5, 47, "on_track")   # 47% at 50% through: within 5
    assert (cpd["value"], cpd["percent"], cpd["state"]) == (25, 62, "on_track")
    assert (journal["value"], journal["state"]) == (1, "behind")


def test_chartered_application_goal_follows_readiness(setup):
    service.add(2026, service.Goal(title="Chartered application ready", kind="chartered_ready", target=100))
    doc = career_store.load()
    doc.application.area_of_practice = "Civil"
    doc.application.signed = True
    career_store.save(doc)
    goal = overview()["goals"][0]
    assert goal["unit"] == "%" and goal["source"] == "Chartered application"
    assert (goal["value"], goal["percent"], goal["state"]) == (25, 25, "behind")


def test_counted_and_done_goals(setup):
    books = service.add(2026, service.Goal(title="Read 12 books", kind="count", target=12, unit="books"))
    charter = service.add(2026, service.Goal(title="Get chartered", kind="done"))
    service.update(2026, books.id, {"progress": 12})
    service.update(2026, charter.id, {"done": True})
    states = [(g["title"], g["percent"], g["state"]) for g in overview()["goals"]]
    assert states == [("Read 12 books", 100, "done"), ("Get chartered", 100, "done")]
    service.delete(2026, books.id)
    assert [g["title"] for g in overview()["goals"]] == ["Get chartered"]
    with pytest.raises(LookupError):
        service.update(2026, "nope", {"done": True})


def test_january_asks_once_until_goals_are_set(setup):
    assert service.push_message(datetime(2027, 2, 1)) == []
    msg = service.push_message(datetime(2027, 1, 1, 9))
    assert msg[0]["key"] == "goals:2027" and msg[0]["url"] == "/year"
    assert overview(2027, date(2027, 1, 3))["set_them"] is True
    service.add(2027, service.Goal(title="Get chartered"))
    assert service.push_message(datetime(2027, 1, 2)) == [] and overview(2027, date(2027, 1, 3))["set_them"] is False


def test_api(setup):
    client = TestClient(app)
    assert client.get("/api/v1/goals").status_code == 401
    assert client.post("/api/v1/goals?year=2026", headers=AUTH, json={"title": "Run lots", "kind": "running_km"}).status_code == 422
    made = client.post("/api/v1/goals?year=2026", headers=AUTH, json={"title": "Read 12 books", "kind": "count", "target": 12, "unit": "books"}).json()
    assert client.patch(f"/api/v1/goals/{made['id']}?year=2026", headers=AUTH, json={"progress": 3}).json()["progress"] == 3
    body = client.get("/api/v1/goals?year=2026", headers=AUTH).json()
    assert body["year"] == 2026 and body["goals"][0]["value"] == 3
    assert client.delete(f"/api/v1/goals/{made['id']}?year=2026", headers=AUTH).status_code == 204
    assert client.delete(f"/api/v1/goals/{made['id']}?year=2026", headers=AUTH).status_code == 404
