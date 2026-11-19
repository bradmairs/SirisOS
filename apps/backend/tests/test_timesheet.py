"""9.8: rough timesheet notes in Work."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.work import timesheet
from tests.test_hub import AUTH


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_TIMESHEET_PATH", str(tmp_path / "timesheet.json"))
    return TestClient(app)


def test_the_time_comes_out_of_the_words():
    assert timesheet.parse("Pump station review 1.5h") == ("Pump station review", 1.5)
    assert timesheet.parse("90 min site meeting") == ("site meeting", 1.5)
    assert timesheet.parse("RFI responses 1:30") == ("RFI responses", 1.5)
    assert timesheet.parse("Design check 2 hours") == ("Design check", 2.0)
    assert timesheet.parse("Calcs 1h30") == ("Calcs", 1.5)
    assert timesheet.parse("Stage 2 report") == ("Stage 2 report", None)


def test_a_week_of_notes_with_totals_and_text_to_paste(client):
    r = client.post("/api/v1/work/timesheet", headers=AUTH, json={"what": "Pump station review 1.5h", "date": "2026-11-16", "code": "GVW-123"})
    assert r.status_code == 200 and r.json()["entry"]["hours"] == 1.5 and r.json()["entry"]["what"] == "Pump station review"
    client.post("/api/v1/work/timesheet", headers=AUTH, json={"what": "Team meeting", "hours": 0.5, "date": "2026-11-16"})
    client.post("/api/v1/work/timesheet", headers=AUTH, json={"what": "Hydraulic model 3h", "date": "2026-11-18", "code": "GVW-123"})
    assert client.post("/api/v1/work/timesheet", headers=AUTH, json={"what": "No time given", "date": "2026-11-18"}).status_code == 422
    w = client.get("/api/v1/work/timesheet?on=2026-11-19", headers=AUTH).json()
    assert w["week_of"] == "2026-11-16" and w["hours"] == 5.0
    assert [d["hours"] for d in w["days"]][:3] == [2.0, 0, 3.0]
    assert w["by_code"] == [{"code": "GVW-123", "hours": 4.5}, {"code": "No code", "hours": 0.5}]
    assert w["recent_codes"] == ["GVW-123"]
    assert w["text"].splitlines()[:3] == ["Mon 16 Nov (2 h)", "  1.5 h  Pump station review [GVW-123]", "  0.5 h  Team meeting"]
    entry = w["days"][0]["entries"][1]
    assert client.patch(f"/api/v1/work/timesheet/{entry['id']}", headers=AUTH, json={"hours": 0.75}).json()["hours"] == 5.25
    assert client.delete(f"/api/v1/work/timesheet/{entry['id']}", headers=AUTH).json() == {"deleted": entry["id"]}
    assert client.get("/api/v1/work/timesheet?on=2026-11-16", headers=AUTH).json()["hours"] == 4.5


def test_the_body_rings_join_a_saved_home_layout_hidden_where_the_defaults_hide_them(monkeypatch, tmp_path):
    """9.8: a schedule saved before the rings existed hides them at work, wind-down and night, as the defaults do."""
    import json

    from app.home import schedule

    path = tmp_path / "home-schedule.json"
    monkeypatch.setenv("SIRISOS_HOME_SCHEDULE_PATH", str(path))
    old = schedule.Schedule().model_dump()
    old.pop("body_rings")
    old["hidden"] = {p: [x for x in ids if x != "body-rings"] for p, ids in old["hidden"].items()}
    path.write_text(json.dumps(old))
    plan = schedule.load()
    assert "body-rings" in plan.hidden["work"] and "body-rings" in plan.hidden["night"]
    assert "body-rings" not in plan.hidden["morning"] and "body-rings" not in plan.hidden["evening"]
    assert plan.body_rings and json.loads(path.read_text())["body_rings"] is True


def test_a_named_focus_block_goes_on_the_timesheet(client):
    from datetime import datetime

    from app.brief.service import zone

    today = datetime.now(zone()).date().isoformat()
    client.post("/api/v1/work/focus", headers=AUTH, json={"minutes": 25, "label": "Hydraulic model", "code": "GVW-123"})
    client.post("/api/v1/work/focus", headers=AUTH, json={"minutes": 25, "label": "hydraulic model", "code": "GVW-123"})
    client.post("/api/v1/work/focus", headers=AUTH, json={"minutes": 25})   # no label: focus time only
    w = client.get(f"/api/v1/work/timesheet?on={today}", headers=AUTH).json()
    entries = [e for d in w["days"] for e in d["entries"]]
    assert len(entries) == 1 and entries[0]["what"] == "Hydraulic model" and entries[0]["hours"] == round(50 / 60, 2)


def test_the_friday_nudge_says_what_is_noted_and_what_looks_light(client):
    from datetime import date, datetime

    timesheet.add("Design 7.5h", None, date(2026, 11, 16))
    timesheet.add("Meetings 2.5h", None, date(2026, 11, 17))
    timesheet.add("Design 8h", None, date(2026, 11, 18))
    assert timesheet.push_message(datetime(2026, 11, 19, 16, 0)) == []   # Thursday
    assert timesheet.push_message(datetime(2026, 11, 20, 9, 0)) == []    # Friday morning
    msg = timesheet.push_message(datetime(2026, 11, 20, 15, 30))[0]
    assert msg["key"] == "timesheet:2026-11-16" and msg["url"] == "/work"
    assert msg["body"] == "18 h noted this week. Light: Tue 2.5 h, Thu 0 h, Fri 0 h. Copy it from Work."
