"""3.6: the fitness card and upkeep on System status (the iPhone widget went with iPhone shortcuts in 4.4)."""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service as hub_service
from app.hub import upkeep
from app.hub.service import reset_hub
from app.tasks import service as tasks
from app.tasks import store as task_store
from tests.test_hub import AUTH, ENV

TODAY = tasks.today()
MONDAY = TODAY - timedelta(days=TODAY.weekday())


def handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/siris/hub/v1/health/days":
        return httpx.Response(200, json={"guest_mode": False, "days": [
            {"date": MONDAY.isoformat(), "metrics": {"running_km": 5.2, "exercise_minutes": 35, "steps": 9000}},
            {"date": TODAY.isoformat(), "metrics": {"running_km": 4.0, "steps": 7000}}]})
    if path == "/siris/hub/v1/upkeep":
        return httpx.Response(200, json={"backups": {"newest": "2026-10-23T02:00:00+00:00", "count": 14, "stale": False}, "update": {"current": "2.14", "latest": None, "available": False}})
    if path in ("/siris/brain/tasks",):
        return httpx.Response(200, json={"tasks": []})
    if path == "/siris/hub/v1/reminders":
        return httpx.Response(200, json={"guest_mode": False, "reminders": []})
    if path == "/siris/hub/v1/calendar":
        return httpx.Response(200, json={"events": [], "guest_mode": False, "unavailable": False})
    if path == "/siris/hub/v1/attention":
        return httpx.Response(200, json={"items": [], "counts": {"open": 0, "urgent": 0}})
    return httpx.Response(404)


@pytest.fixture
def client(monkeypatch, tmp_path):
    for env, name in (("SIRISOS_TASKS_PATH", "tasks.json"), ("SIRISOS_FITNESS_PATH", "fitness.json"), ("SIRISOS_WRAPUP_PATH", "w.json"),
                      ("SIRISOS_SHORTCUT_KEYS_PATH", "keys.json"), ("SIRISOS_ATTENTION_STATE_PATH", "a.json")):
        monkeypatch.setenv(env, str(tmp_path / name))
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    reset_hub(ENV)
    yield TestClient(app)
    reset_hub({})


def test_fitness_week_and_goal(client):
    assert client.put("/api/v1/fitness/goal", headers=AUTH, json={"weekly_km": 20}).json() == {"goal_km": 20.0}
    body = client.get("/api/v1/fitness", headers=AUTH).json()
    assert body["available"] is True and body["goal_km"] == 20.0 and len(body["days"]) == 7 and body["days"][0]["date"] == MONDAY.isoformat()
    if TODAY != MONDAY:
        assert (body["km"], body["runs"], body["steps_avg"]) == (9.2, 2, 8000)
    assert client.put("/api/v1/fitness/goal", headers=AUTH, json={"weekly_km": None}).json() == {"goal_km": None}
    assert client.put("/api/v1/fitness/goal", headers=AUTH, json={"weekly_km": -1}).status_code == 422


def test_upkeep_has_backups_and_certificates(client, monkeypatch):
    from datetime import datetime, timezone

    monkeypatch.setattr(upkeep, "_expiry", lambda host, port, timeout=4.0: datetime.now(timezone.utc) + timedelta(days=10))
    body = client.get("/api/v1/hub/upkeep", headers=AUTH).json()
    assert body["sirisai"]["backups"]["count"] == 14 and body["sirisos"]["version"]
    certs = {c["host"]: c for c in body["certificates"]}
    assert "siris.local" in certs and certs["siris.local"]["warning"] is True and certs["siris.local"]["days_left"] in (9, 10)
    assert all(not h.startswith("http") for h in certs)
