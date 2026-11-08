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


def test_january_asks_until_you_say_the_goals_are_set(setup):
    assert service.push_message(datetime(2027, 2, 1)) == []
    msg = service.push_message(datetime(2027, 1, 1, 9))
    assert msg[0]["key"] == "goals:set:2027" and msg[0]["url"] == "/year"  # one notification: the key doesn't change all month
    assert overview(2027, date(2027, 1, 3))["set_them"] is True
    service.add(2027, service.Goal(title="Get chartered"))
    assert overview(2027, date(2027, 1, 3))["set_them"] is False and overview(2027, date(2027, 1, 3))["setting_due"] is True  # 8.3
    service.mark("set", 2027)
    assert service.push_message(datetime(2027, 1, 2)) == [] and overview(2027, date(2027, 1, 3))["setting_due"] is False


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


def test_sirisai_asks_to_set_goals_all_january_until_you_say(setup, monkeypatch, tmp_path):
    from datetime import date

    from app.goals import service

    monkeypatch.setenv("SIRISOS_GOALS_PATH", str(tmp_path / "goals.json"))
    assert service.prompt(date(2027, 1, 3)) == {"kind": "set", "year": 2027, "goals": 0}
    service.add(2027, service.Goal(title="Run 1000 km", kind="running_km", target=1000))
    assert service.prompt(date(2027, 1, 28))["goals"] == 1, "still asking with goals in, until you say"
    service.mark("set", 2027)
    assert service.prompt(date(2027, 1, 29)) is None
    assert service.prompt(date(2027, 6, 1)) is None


def test_december_asks_for_a_review_and_carries_the_unfinished(setup, monkeypatch, tmp_path):
    from datetime import date

    from app.goals import service

    monkeypatch.setenv("SIRISOS_GOALS_PATH", str(tmp_path / "goals.json"))
    keep = service.add(2026, service.Goal(title="Read 12 books", kind="count", target=12, progress=7))
    done = service.add(2026, service.Goal(title="Get chartered", kind="done", done=True))
    service.add(2027, service.Goal(title="Read 12 books", kind="count", target=12))
    assert service.prompt(date(2026, 12, 2)) == {"kind": "review", "year": 2026, "goals": 2}
    assert service.prompt(date(2027, 1, 2))["kind"] == "review", "a missed December review is asked for in January first"
    other = service.add(2026, service.Goal(title="Learn Spanish", kind="done"))
    moved = service.carry(2026, [keep.id, other.id, done.id])
    assert [g.title for g in moved] == ["Get chartered", "Learn Spanish"] or [g.title for g in moved] == ["Learn Spanish", "Get chartered"]
    titles = [g.title for g in service.goals(2027)]
    assert titles.count("Read 12 books") == 1, "one already there isn't doubled"
    fresh = next(g for g in service.goals(2027) if g.title == "Learn Spanish")
    assert not fresh.done and fresh.notes.startswith("Carried from 2026")
    service.mark("review", 2026)
    assert service.prompt(date(2026, 12, 20)) is None
    assert service.goals(2026)[0].title == "Read 12 books", "the old year is left as it was"


def test_the_review_route_carries_only_whats_picked(setup, monkeypatch, tmp_path):
    client = TestClient(app)
    monkeypatch.setenv("SIRISOS_GOALS_PATH", str(tmp_path / "goals2.json"))
    a = service.add(2026, service.Goal(title="Swim", kind="done"))
    service.add(2026, service.Goal(title="Paint", kind="done"))
    r = client.post("/api/v1/goals/review?year=2026", headers=AUTH, json={"carry": [a.id]})
    assert r.status_code == 200 and [g["title"] for g in r.json()["carried"]] == ["Swim"] and r.json()["into"] == 2027
    assert client.post("/api/v1/goals/set?year=2027", headers=AUTH).status_code == 200
    assert "set:2027" in service._marks() and "review:2026" in service._marks()
