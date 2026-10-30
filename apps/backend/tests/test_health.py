"""5.7: the Health section: everything from Health Auto Export, readiness, sleep, load, vitals, the brief."""

from __future__ import annotations

from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.health import ingest, scores
from app.hub import service as hub_service
from app.hub.service import reset_hub
from tests.test_hub import AUTH, ENV

TODAY = date(2026, 10, 30)


def history(n: int = 30, **today: float) -> scores.Days:
    out: scores.Days = {}
    for i in range(n, 0, -1):
        d = TODAY - timedelta(days=i)
        out[d.isoformat()] = {"heart_rate_variability": 60 + (i % 5) - 2, "resting_heart_rate": 55 + (i % 3) - 1,
                              "sleep_hours": 7.5 + (i % 3) * 0.2 - 0.2, "respiratory_rate": 14.0 + (i % 2) * 0.2,
                              "wrist_temperature": 34.5 + (i % 2) * 0.1, "exercise_minutes": 40 + (i % 4) * 5}
    out[TODAY.isoformat()] = {"heart_rate_variability": 60, "resting_heart_rate": 55, "sleep_hours": 7.6, **today}
    return out


def test_parses_everything_health_auto_export_sends():
    body = {"data": {"metrics": [
        {"name": "sleep_analysis", "units": "hr", "data": [{"date": "2026-10-30 00:00:00 +1100", "totalSleep": 7.2, "asleep": 7.2, "deep": 1.1,
                                                            "rem": 1.6, "core": 4.5, "awake": 0.3, "inBed": 7.8,
                                                            "sleepStart": "2026-10-29 22:41:00 +1100", "sleepEnd": "2026-10-30 06:30:00 +1100"}]},
        {"name": "heart_rate", "units": "count/min", "data": [{"date": "2026-10-30 00:00:00 +1100", "Min": 48, "Avg": 66, "Max": 151}]},
        {"name": "blood_oxygen_saturation", "units": "%", "data": [{"date": "2026-10-30 00:00:00 +1100", "qty": 0.97}]},
        {"name": "vo2_max", "units": "ml/(kg·min)", "data": [{"date": "2026-10-30 00:00:00 +1100", "qty": 48.2}]},
        {"name": "active_energy", "units": "kJ", "data": [{"date": "2026-10-30 00:00:00 +1100", "qty": 4184}]},
    ], "workouts": [{"name": "Outdoor Run", "start": "2026-10-30 06:45:00 +1100", "duration": 2700,
                     "distance": {"qty": 8.2, "units": "km"}, "activeEnergyBurned": {"qty": 2510, "units": "kJ"}, "avgHeartRate": {"qty": 152}}]}}
    p = ingest.parse(body)
    day = p["metrics"]["2026-10-30"]
    assert day["sleep_hours"] == 7.2 and day["sleep_deep_h"] == 1.1 and day["in_bed_h"] == 7.8
    assert (day["heart_rate_min"], day["heart_rate_avg"], day["heart_rate_max"]) == (48, 66, 151)
    assert day["blood_oxygen"] == 97.0 and day["vo2_max"] == 48.2 and day["active_energy_kcal"] == 1000.0 and day["running_km"] == 8.2
    assert p["sleep"]["2026-10-30"]["start"].startswith("2026-10-29 22:41")
    assert p["workouts"]["2026-10-30"][0] == {"name": "Outdoor Run", "start": "2026-10-30 06:45:00 +1100", "minutes": 45, "km": 8.2,
                                              "kcal": 600, "avg_hr": 152.0, "max_hr": None}


def test_readiness_moves_with_hrv_sleep_and_vitals():
    good = scores.readiness(history(heart_rate_variability=72, resting_heart_rate=52, sleep_hours=8.1), TODAY)
    assert good["band"] == "Primed" and good["score"] >= 70 and not good["early"]
    poor = scores.readiness(history(heart_rate_variability=44, resting_heart_rate=61, sleep_hours=5.2), TODAY)
    assert poor["band"] == "Recover" and poor["score"] < 45
    assert poor["contributors"][0]["score"] <= poor["contributors"][-1]["score"]
    sick = scores.readiness(history(respiratory_rate=16.0, wrist_temperature=35.3), TODAY)
    assert "coming down with something" in sick["advice"]
    assert next(c for c in sick["contributors"] if c["key"] == "vitals")["text"].startswith("Watch out")
    assert scores.readiness({TODAY.isoformat(): {"steps": 3000}}, TODAY) is None
    assert scores.readiness(history(3), TODAY)["early"] is True or scores.readiness(history(3), TODAY) is None


def test_sleep_load_and_vitals():
    data = history()
    data[TODAY.isoformat()].update(sleep_deep_h=1.2, sleep_rem_h=1.7)
    s = scores.sleep(data, {TODAY.isoformat(): {"start": "2026-10-29 22:40:00 +1100"}}, TODAY)
    assert s["need"] == 7.5 and s["last_night"]["hours"] == 7.6 and 80 <= s["score"] <= 100 and len(s["nights"]) == 14
    load = scores.load(data, TODAY)
    assert load["zone"] == "sweet spot" and 0.8 <= load["ratio"] <= 1.3
    v = {x["key"]: x for x in scores.vitals(data, TODAY)}
    assert v["heart_rate_variability"]["state"] == "normal" and len(v["heart_rate_variability"]["series"]) == 30


@pytest.fixture
def client(monkeypatch, tmp_path):
    for env, name in (("SIRISOS_HEALTH_PATH", "h.json"), ("SIRISOS_HEALTH_IMPORT_PATH", "hi.json")):
        monkeypatch.setenv(env, str(tmp_path / name))
    data = history()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/siris/hub/v1/health/days":
            return httpx.Response(200, json={"guest_mode": False, "days": [{"date": d, "metrics": m} for d, m in sorted(data.items())]})
        if request.url.path == "/siris/health/metrics":
            return httpx.Response(200, json={"date": "x"})
        return httpx.Response(404)

    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    from app.health import service

    monkeypatch.setattr(service.tasks, "today", lambda: TODAY)
    reset_hub(ENV)
    return TestClient(app)


def test_api_and_import_into_the_store(client):
    body = client.get("/api/v1/health", headers=AUTH).json()
    assert body["readiness"]["band"] in ("Primed", "Steady") and body["sleep"]["need"] == 7.5
    assert body["activity"]["load"]["zone"] == "sweet spot" and body["sources"]["sirisai"]
    assert client.get("/api/v1/health/today", headers=AUTH).json()["readiness"]["score"] == body["readiness"]["score"]
    key = client.post("/api/v1/health/import/key", headers=AUTH).json()["key"]
    export = {"data": {"metrics": [{"name": "vo2_max", "units": "ml/(kg·min)", "data": [{"date": "2026-10-30 00:00:00 +1100", "qty": 48.2}]}]}}
    assert client.post("/api/v1/health/import", json=export, headers={"Authorization": f"Bearer {key}"}).status_code == 200
    assert ingest.load()["metrics"]["2026-10-30"]["vo2_max"] == 48.2
    vitals = {v["key"]: v for v in client.get("/api/v1/health", headers=AUTH).json()["vitals"]}
    assert vitals["vo2_max"]["value"] == 48.2


def test_the_brief_leads_with_readiness():
    from datetime import datetime

    from app.brief.service import compose

    brief = compose(datetime(2026, 10, 30, 7, 0), "brad", {"readiness": {"score": 78, "band": "Primed", "advice": "A good day to push.", "contributors": []}}, [])
    assert brief["headline"][0] == "Readiness 78, primed: A good day to push." and brief["readiness"]["score"] == 78
