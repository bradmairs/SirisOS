"""5.5: a race plan from recent running, recovery, the calendar feed, and Apple Health import."""

from __future__ import annotations

import json
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.training import health_import, plan, service
from tests.test_hub import AUTH, ENV

TODAY = date(2026, 10, 30)  # a Friday
posted: list[dict] = []


def days(recent_km_per_week: float = 20.0, last_night: dict | None = None) -> list[dict]:
    out = []
    for i in range(42, 0, -1):
        d = TODAY - timedelta(days=i)
        m = {"sleep_hours": 7.5, "heart_rate_variability": 60, "resting_heart_rate": 55}
        if d.weekday() in (1, 5):
            m["running_km"] = recent_km_per_week / 2
        out.append({"date": d.isoformat(), "metrics": m})
    out.append({"date": TODAY.isoformat(), "metrics": last_night or {"sleep_hours": 7.4}})
    return out


def handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/siris/hub/v1/health/days":
        return httpx.Response(200, json={"guest_mode": False, "days": days()})
    if request.url.path == "/siris/health/metrics":
        body = json.loads(request.content)
        posted.append(body)
        names = [m.get("name") for m in (body.get("data") or {}).get("metrics") or []]
        if body.get("data") and "step_count" not in names:  # like SirisAI: nothing it uses
            return httpx.Response(422, json={"detail": "No recognised metrics (got: walking_speed)."})
        return httpx.Response(200, json={"user_id": "brad", "format": "health_auto_export", "days": {"2026-10-29": {"steps": 9000}}, "ignored": []})
    return httpx.Response(404)


@pytest.fixture
def client(monkeypatch, tmp_path):
    for env, name in (("SIRISOS_TRAINING_PATH", "t.json"), ("SIRISOS_HEALTH_IMPORT_PATH", "h.json"), ("SIRISOS_FITNESS_PATH", "f.json")):
        monkeypatch.setenv(env, str(tmp_path / name))
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    monkeypatch.setattr(service.tasks, "today", lambda: TODAY)
    posted.clear()
    reset_hub(ENV)
    return TestClient(app)


def test_plan_builds_from_recent_running_and_tapers():
    weeks = plan.weekly_targets(20, date(2027, 1, 24), 21.1, TODAY)
    assert weeks[0] == {"week_of": "2026-10-26", "km": 20.0, "kind": "build"}
    assert weeks[1]["km"] == 22.0 and weeks[3]["kind"] == "easier"
    assert [w["kind"] for w in weeks[-3:]] == ["taper", "taper", "race"]
    assert max(w["km"] for w in weeks) <= 50
    race_week = plan.sessions(weeks[-1]["km"], 21.1, date.fromisoformat(weeks[-1]["week_of"]), date(2027, 1, 24))
    assert race_week[-1] == {"date": "2027-01-24", "kind": "race", "km": 21.1, "title": "Race day: 21.1 km"}
    assert all(s["kind"] != "long" for s in race_week)


def test_recovery_turns_hard_days_easy_or_rest():
    assert service.recovery(days(), TODAY)["level"] == "good"
    poor = service.recovery(days(last_night={"sleep_hours": 5.9}), TODAY)
    assert poor["level"] == "easy" and poor["notes"][0].startswith("You slept 5.9 h")
    worse = service.recovery(days(last_night={"sleep_hours": 5.9, "heart_rate_variability": 40, "resting_heart_rate": 62}), TODAY)
    assert worse["level"] == "rest" and len(worse["notes"]) == 3


def test_overview_today_and_the_fitness_goal(client):
    r = client.put("/api/v1/training/race", headers=AUTH, json={"name": "Run Melbourne 10 km", "date": "2027-01-24", "distance_km": 10})
    body = r.json()
    assert body["plan"]["start_km"] == 20.0 and body["this_week"]["km"] == 20.0
    # Fridays are rest days, but Thursday's tempo run wasn't done, so it moves to today (5.8).
    assert body["recovery"]["level"] == "good" and body["session"]["kind"] == "quality" and body["session"]["moved_from"] == "2026-10-29"
    tomorrow = service.today_session(service.build(service.race(), days(), TODAY), {"level": "easy"}, TODAY + timedelta(days=1))
    assert tomorrow["kind"] == "long" and tomorrow["changed"] and "instead" in tomorrow["title"]
    assert client.get("/api/v1/fitness", headers=AUTH).json()["goal_km"] == 20.0


def test_calendar_feed(client):
    client.put("/api/v1/training/race", headers=AUTH, json={"name": "10 km", "date": "2026-11-29", "distance_km": 10})
    path = client.get("/api/v1/training/feed", headers=AUTH).json()["path"]
    feed = client.get(path)
    assert feed.status_code == 200 and feed.headers["content-type"].startswith("text/calendar")
    assert "SUMMARY:Race day: 10 km" in feed.text and "DTSTART;VALUE=DATE:20261129" in feed.text
    assert client.get("/api/v1/training/calendar.ics", params={"t": "wrong-token-123"}).status_code == 404
    new = client.post("/api/v1/training/feed/new", headers=AUTH).json()["path"]
    assert client.get(path).status_code == 404 and client.get(new).status_code == 200


def test_health_import_with_its_own_key(client):
    body = {"data": {"metrics": [{"name": "step_count", "units": "count", "data": [{"date": "2026-10-29 00:00:00 +1100", "qty": 9000}]}]}}
    assert client.post("/api/v1/health/import", json=body).status_code == 401
    key = client.post("/api/v1/health/import/key", headers=AUTH).json()["key"]
    r = client.post("/api/v1/health/import", json=body, headers={"Authorization": f"Bearer {key}"})
    # Read here and sent a day at a time in the plain shape, so any SirisAI version takes it (5.62).
    assert r.status_code == 200 and r.json()["format"] == "health_auto_export" and posted == [body]  # passed to SirisAI as it is (5.8)
    status = client.get("/api/v1/health/import/status", headers=AUTH).json()
    assert status["has_key"] and status["key_hint"] == key[-4:] and status["last_ok"]["days"] == ["2026-10-29"]
    assert client.post("/api/v1/health/import", content=b"nope", headers={"X-Health-Key": key}).status_code == 422
    client.post("/api/v1/health/import/key", headers=AUTH)
    assert client.post("/api/v1/health/import", json=body, headers={"Authorization": f"Bearer {key}"}).status_code == 401
    assert key not in json.dumps(health_import.status()) and key[:-4] not in json.dumps(health_import.status())


def test_every_attempt_is_logged_with_why(client):
    assert client.post("/api/v1/health/import", json={}).status_code == 401
    key = client.post("/api/v1/health/import/key", headers=AUTH).json()["key"]
    assert client.post("/api/v1/health/import", json={}, headers={"Authorization": "Bearer wrong"}).status_code == 401
    # Only metrics SirisOS doesn't use: fine, not an error the app would show.
    only_other = {"data": {"metrics": [{"name": "walking_speed", "units": "km/hr", "data": [{"date": "2026-10-29 00:00:00 +1100", "qty": 5}]}]}}
    r = client.post("/api/v1/health/import", json=only_other, headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 200 and len(posted) == 1  # SirisAI says there's nothing it uses
    attempts = client.get("/api/v1/health/import/status", headers=AUTH).json()["attempts"]
    assert [a["status"] for a in attempts] == [200, 401, 401]
    assert attempts[0]["outcome"] == "Nothing SirisAI uses in it (that's fine)"
    assert attempts[1]["outcome"].startswith("The key doesn't match") and attempts[2]["outcome"].startswith("No Authorization header")


def test_predictions_zones_paces_and_strength_days():
    from app.training import plan

    workouts = [
        {"date": "2026-10-20", "name": "Outdoor Run", "km": 10.0, "minutes": 50.0, "max_hr": 182},
        {"date": "2026-10-25", "name": "Outdoor Run", "km": 5.0, "minutes": 24.0, "max_hr": 188},
        {"date": "2026-08-01", "name": "Outdoor Run", "km": 5.0, "minutes": 20.0, "max_hr": 175},  # too old to predict from
        {"date": "2026-10-26", "name": "Outdoor Walk", "km": 6.0, "minutes": 70.0},
    ]
    p = service.predict(workouts, 21.1, TODAY)
    assert p == {"minutes": 110.3, "time": "1:50:20", "pace": "5:14/km", "from": "10 km in 50:00 on 2026-10-20"}  # not the old 5 km
    z = service.zones(workouts)
    assert z["max_hr"] == 188 and z["zones"][1] == {"name": "Zone 2, easy", "low": 113, "high": 132}
    assert service.paces(workouts, TODAY) == {"easy": "6:15/km", "long": "6:30/km", "tempo": "5:15/km", "ten_k": "5:00/km"}
    week = plan.sessions(30, 21.1, plan.monday(TODAY))
    assert [s["kind"] for s in week][:3] == ["mobility", "easy", "strength"]
    race_week = plan.sessions(20, 10, plan.monday(date(2026, 11, 29)), date(2026, 11, 29))
    assert not any(s["kind"] in ("strength", "mobility") for s in race_week)


def test_sickness_and_readiness_ease_the_day():
    rec = service.recovery([], TODAY, {"score": 80, "band": "Primed", "summary": "fine"}, {"today": ["wrist temperature +0.6 °C", "HRV 20% down"]})
    assert rec["level"] == "rest" and "getting sick" in rec["notes"][-1]
    assert service.recovery([], TODAY, {"score": 40, "band": "Recover", "summary": "HRV low"})["level"] == "easy"
