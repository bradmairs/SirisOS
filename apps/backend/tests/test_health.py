"""The Health section since 5.8: SirisAI keeps the data and works out the
scores; SirisOS shows them, moves its old store across once, passes the
phone's exports straight to SirisAI, and relays logs, goals, the backfill,
export and deletion."""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.health import migrate
from app.hub import service as hub_service
from app.hub.service import reset_hub
from tests.test_hub import AUTH, ENV

TODAY = date(2026, 10, 30)
OVERVIEW = {
    "guest_mode": False, "today": "2026-10-30", "available": True,
    "sources": {"days": 42, "imports": {"health_auto_export": {"at": "2026-10-30T06:00:00+00:00", "days": 1}}},
    "readiness": {"date": "2026-10-30", "score": 78, "band": "Primed", "advice": "A good day to push.", "early": False, "contributors": [], "summary": "HRV 64 ms"},
    "sleep": {"need": 7.5, "last_night": {"hours": 7.6}, "score": 88, "debt_7d": 0.5, "bedtime_spread_min": 20, "average_7d": 7.4, "nights": []},
    "activity": {"steps": 9000, "load": {"ratio": 1.1, "zone": "sweet spot", "acute_min_per_day": 40, "chronic_min_per_day": 36}, "workouts": []},
    "vitals": [], "weight": {"latest": 79.5, "trend": 79.8, "per_week": -0.2}, "getting_sick": None,
    "logged": {"water_ml": 750, "notes": []}, "insights": [{"factor": "late_meeting", "minutes": -38, "text": "After a meeting past 8pm you sleep 38 minutes less."}],
    "bedtime": {"bedtime": "22:30", "text": "Bed by 22:30"},
}


@pytest.fixture
def seen():
    return []


@pytest.fixture
def client(monkeypatch, tmp_path, seen):
    for env, name in (("SIRISOS_HEALTH_PATH", "h.json"), ("SIRISOS_HEALTH_IMPORT_PATH", "hi.json")):
        monkeypatch.setenv(env, str(tmp_path / name))
    monkeypatch.setattr(migrate, "_last_try", 0.0)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        seen.append((request.method, path, request.headers.get("x-health-source"), request.content))
        if path == "/siris/hub/v1/health/overview":
            return httpx.Response(200, json=OVERVIEW)
        if path == "/siris/health/metrics":
            body = json.loads(request.content)
            if body.get("data", {}).get("metrics") == []:
                return httpx.Response(422, json={"detail": "No recognised metrics (got: nothing)."})
            return httpx.Response(200, json={"format": "health_auto_export", "days": {"2026-10-30": {"vo2_max": 48.2}}})
        if path.startswith("/siris/tools/"):
            name = path.split("/")[3]
            return httpx.Response(200, json={"tool_call": {"name": name, "arguments": json.loads(request.content)["arguments"], "result": {"ran": name}}})
        if path == "/siris/health/export.csv":
            return httpx.Response(200, text="date,metric,value\n", headers={"content-disposition": 'attachment; filename="health.csv"'})
        if path == "/siris/health/report":
            return httpx.Response(200, text="<h1>Health summary</h1>")
        if path == "/siris/health/data":
            return httpx.Response(200, json={"readings": 3, "workouts": 0})
        if path == "/siris/health/apple-export":
            return httpx.Response(200, json={"source": "apple_export", "days": 365, "from": "2025-10-30"})
        return httpx.Response(404)

    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    reset_hub(ENV)
    return TestClient(app)


def test_the_health_section_is_sirisai_s(client):
    body = client.get("/api/v1/health", headers=AUTH).json()
    assert body["readiness"]["score"] == 78 and body["sleep"]["need"] == 7.5
    assert body["sources"] == {"sirisai": True, "health_auto_export": True, "days": 42, "imports": OVERVIEW["sources"]["imports"]}
    assert body["insights"][0]["minutes"] == -38 and body["bedtime"]["bedtime"] == "22:30" and body["migrating"] is False
    assert client.get("/api/v1/health/today", headers=AUTH).json()["readiness"]["score"] == 78


def test_the_old_store_moves_to_sirisai_once(client, seen, tmp_path):
    days = {f"2026-0{m}-{d:02d}": {"steps": 1000 + d} for m in (6, 7, 8, 9) for d in range(1, 29)}
    (tmp_path / "h.json").write_text(json.dumps({"metrics": days, "sleep": {"2026-09-01": {"start": "x", "end": "y"}},
                                                 "workouts": {"2026-09-02": [{"name": "Run", "km": 5}]}}))
    client.get("/api/v1/health", headers=AUTH)
    posts = [s for s in seen if s[1] == "/siris/health/metrics"]
    assert len(posts) == 1 and all(s[2] == "sirisos" for s in posts)  # 112 days fit one part
    sent = json.loads(posts[0][3])
    assert len(sent["metrics"]) == 112 and sent["workouts"]["2026-09-02"][0]["km"] == 5
    assert not (tmp_path / "h.json").exists() and (tmp_path / "health-days.migrated.json").exists()
    client.get("/api/v1/health", headers=AUTH)
    assert len([s for s in seen if s[1] == "/siris/health/metrics"]) == 1


def test_imports_go_to_sirisai_as_they_are(client, seen):
    key = client.post("/api/v1/health/import/key", headers=AUTH).json()["key"]
    export = {"data": {"metrics": [{"name": "vo2_max", "units": "ml/(kg·min)", "data": [{"date": "2026-10-30 00:00:00 +1100", "qty": 48.2}]}]}}
    r = client.post("/api/v1/health/import", json=export, headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 200 and r.json()["days"] == {"2026-10-30": {"vo2_max": 48.2}}
    method, path, source, content = next(s for s in seen if s[1] == "/siris/health/metrics")
    assert source == "health_auto_export" and json.loads(content) == export
    empty = client.post("/api/v1/health/import", json={"data": {"metrics": []}}, headers={"Authorization": f"Bearer {key}"})
    assert empty.status_code == 200
    status = client.get("/api/v1/health/import/status", headers=AUTH).json()
    assert status["attempts"][0]["outcome"].startswith("Nothing SirisAI uses")


def test_logs_goals_export_report_backfill_and_delete(client, seen):
    assert client.post("/api/v1/health/log", json={"kind": "water", "amount": 250}, headers=AUTH).json()["logged"] == {"ran": "health_log"}
    assert client.post("/api/v1/health/log", json={"kind": "dance"}, headers=AUTH).status_code == 422
    assert client.get("/api/v1/health/goals", headers=AUTH).json()["goals"] == {"ran": "health_goals"}
    goal = client.post("/api/v1/health/goals", json={"metric": "running_km", "target": 1000, "end": "2026-12-31"}, headers=AUTH)
    assert goal.json()["goal"] == {"ran": "health_set_goal"}
    sent = json.loads(next(s for s in seen if s[1] == "/siris/tools/health_set_goal/run")[3])
    assert sent == {"arguments": {"metric": "running_km", "target": 1000.0, "end": "2026-12-31"}, "confirmed": True}
    csv = client.get("/api/v1/health/export.csv", headers=AUTH)
    assert csv.text.startswith("date,metric") and "health.csv" in csv.headers["content-disposition"]
    assert "Health summary" in client.get("/api/v1/health/report", headers=AUTH).text
    up = client.post("/api/v1/health/apple-export", files={"file": ("export.zip", b"PK..", "application/zip")}, headers=AUTH)
    assert up.json()["days"] == 365
    assert client.delete("/api/v1/health/data", params={"start": "2026-10-01", "end": "2026-10-31"}, headers=AUTH).json()["readings"] == 3


def test_the_brief_leads_with_readiness():
    from datetime import datetime

    from app.brief.service import compose

    brief = compose(datetime(2026, 10, 30, 7, 0), "brad", {"readiness": {"score": 78, "band": "Primed", "advice": "A good day to push.", "contributors": []}}, [])
    assert brief["headline"][0] == "Readiness 78, primed: A good day to push." and brief["readiness"]["score"] == 78
