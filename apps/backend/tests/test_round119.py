"""11.9: edit habits, each day's working hours, the Server handbook, and Home learning where you go."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.assist import homeuse
from app.entrypoint import app
from app.work import service as work
from tests.test_hub import AUTH


@pytest.fixture
def client(monkeypatch, tmp_path):
    for env, name in (("SIRISOS_MIND_PATH", "mind.json"), ("SIRISOS_WORK_PATH", "work.json"), ("SIRISOS_HANDBOOK_PATH", "handbook.json"),
                      ("SIRISOS_HOME_USAGE_PATH", "home-usage.json"), ("SIRISOS_HOME_SCHEDULE_PATH", "home-schedule.json")):
        monkeypatch.setenv(env, str(tmp_path / name))
    return TestClient(app, headers=AUTH)


# -- habits ---------------------------------------------------------------------------


def test_a_habit_can_be_renamed_moved_stopped_and_brought_back(client):
    for name in ("Stretch", "Read", "Walk"):
        client.post("/api/v1/mind/habits", json={"name": name})
    ids = {h["name"]: h["id"] for h in client.get("/api/v1/mind/habits").json()["habits"]}
    r = client.patch(f"/api/v1/mind/habits/{ids['Read']}", json={"name": "Read 20 pages", "days": [0, 2, 4]}).json()
    read = next(h for h in r["habits"] if h["id"] == ids["Read"])
    assert read["name"] == "Read 20 pages" and read["days"] == [0, 2, 4]
    order = [h["name"] for h in client.patch(f"/api/v1/mind/habits/{ids['Walk']}", json={"move": -1}).json()["habits"]]
    assert order == ["Stretch", "Walk", "Read 20 pages"]
    assert [h["name"] for h in client.patch(f"/api/v1/mind/habits/{ids['Stretch']}", json={"move": -1}).json()["habits"]][0] == "Stretch"  # already first
    client.post(f"/api/v1/mind/habits/{ids['Walk']}/check", json={"done": True})
    stopped = client.patch(f"/api/v1/mind/habits/{ids['Walk']}", json={"archived": True}).json()
    assert [h["name"] for h in stopped["habits"]] == ["Stretch", "Read 20 pages"]
    assert stopped["stopped"] == [{"id": ids["Walk"], "name": "Walk", "days_done": 1}]
    back = client.patch(f"/api/v1/mind/habits/{ids['Walk']}", json={"archived": False}).json()
    assert "Walk" in [h["name"] for h in back["habits"]] and back["stopped"] == []
    assert next(h for h in back["habits"] if h["name"] == "Walk")["streak"] >= 0  # its history came back with it


# -- working hours ----------------------------------------------------------------------


def test_each_day_has_its_own_working_hours_or_is_off(client):
    hours = [{"start": "08:00", "end": "16:30"}] * 4 + [{"start": "08:00", "end": "13:00"}, None, None]
    assert client.put("/api/v1/work/settings", json={"hours_by_day": hours}).json()["hours_by_day"][4] == {"start": "08:00", "end": "13:00"}
    friday = work.hours(datetime(2026, 11, 27, 12, 0))
    assert friday == {"start": "08:00", "end": "13:00", "on": True, "workday": True, "minutes_left": 60, "minutes_in": 240}
    saturday = work.hours(datetime(2026, 11, 28, 12, 0))
    assert saturday["workday"] is False and saturday["on"] is False and saturday["start"] == "08:00"
    assert work.day_hours(5) is None
    assert client.put("/api/v1/work/settings", json={"hours_by_day": [{"start": "17:00", "end": "09:00"}] + [None] * 6}).status_code == 422
    assert client.put("/api/v1/work/settings", json={"hours_by_day": None}).json()["hours_by_day"] is None
    assert work.day_hours(5) is None and work.day_hours(0) is not None  # back to Times of day, Monday to Friday


# -- the handbook ---------------------------------------------------------------------------


def test_your_own_handbook_commands(client):
    made = client.post("/api/v1/handbook", json={"cmd": "ssh me@nas", "what": "The NAS", "section": "Machines"}).json()["entries"]
    assert made[0]["cmd"] == "ssh me@nas" and made[0]["section"] == "Machines"
    eid = made[0]["id"]
    assert client.patch(f"/api/v1/handbook/{eid}", json={"what": "Sign in to the NAS", "section": ""}).json()["entries"][0] == {
        "id": eid, "cmd": "ssh me@nas", "what": "Sign in to the NAS", "section": "Mine"}
    assert client.delete(f"/api/v1/handbook/{eid}").json()["entries"] == []
    assert client.delete(f"/api/v1/handbook/{eid}").status_code == 404
    assert TestClient(app).get("/api/v1/handbook").status_code == 401


# -- Home learns where you go ------------------------------------------------------------------


def test_sections_you_open_at_a_time_of_day_are_offered_then(client):
    today = date(2026, 11, 26)
    for i in range(4):
        homeuse.record([{"phase": "evening", "widget": "/gym", "kind": "visit"}, {"phase": "evening", "widget": "/gym", "kind": "visit"}], date(2026, 11, 20 + i))
    homeuse.record([{"phase": "evening", "widget": "/budget", "kind": "visit"}, {"phase": "evening", "widget": "/", "kind": "visit"},
                    {"phase": "work", "widget": "loading-app-0", "kind": "seen"}], today)
    got = homeuse.learned(today)
    assert got["usually"] == {"evening": [{"path": "/gym", "days": 4}]}  # once a day each; budget only once; Home itself never
    assert got["sections"] == {"/budget": 1, "/gym": 4}
    assert "loading-app-0" not in got["phases"].get("work", {})


def test_the_server_decides_a_visits_part_of_the_day(client, monkeypatch):
    from app.home import context

    monkeypatch.setattr(context, "phase", lambda now: "morning")
    assert client.post("/api/v1/home/usage", json={"events": [{"phase": "", "widget": "/brief", "kind": "visit"}]}).json() == {"ok": True}
    assert homeuse.load()["visits"]["morning"]["/brief"]
