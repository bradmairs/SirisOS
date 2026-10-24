"""The adaptive Home's context (3.1): part of the day, presence, wrap-up state."""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.brief.service import zone
from app.entrypoint import app
from app.home import context
from app.hub import service as hub_service
from app.hub.service import reset_hub
from tests.test_hub import AUTH, ENV


@pytest.fixture(autouse=True)
def _schedule(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_HOME_SCHEDULE_PATH", str(tmp_path / "home-schedule.json"))


@pytest.mark.parametrize("when,expected", [
    ("2026-10-22 07:30", "morning"),   # Thursday
    ("2026-10-22 08:29", "morning"),
    ("2026-10-22 08:30", "work"),      # work is 8:30 to 4:30 on weekdays
    ("2026-10-22 16:29", "work"),
    ("2026-10-22 16:30", "evening"),
    ("2026-10-24 08:45", "morning"),   # Saturday: no work
    ("2026-10-24 11:00", "weekend"),
    ("2026-10-24 16:45", "weekend"),
    ("2026-10-22 18:15", "evening"),
    ("2026-10-22 23:30", "night"),
    ("2026-10-23 03:00", "night"),
])
def test_phase(when, expected):
    assert context.phase(datetime.strptime(when, "%Y-%m-%d %H:%M")) == expected


def test_the_schedule_is_saved_checked_and_used():
    client = TestClient(app)
    got = client.get("/api/v1/home/schedule", headers=AUTH).json()
    assert got["weekday"] == {"morning": "05:00", "day": "08:30", "evening": "16:30", "night": "23:00"}
    got["weekday"]["day"] = "09:00"
    got["sections"]["work"] = ["Now", "Today", "Home"]
    assert client.put("/api/v1/home/schedule", headers=AUTH, json=got).status_code == 200
    assert context.phase(datetime(2026, 10, 22, 8, 45)) == "morning"
    assert client.get("/api/v1/home/schedule", headers=AUTH).json()["sections"]["work"] == ["Now", "Today", "Home"]
    bad_order = {**got, "weekday": {"morning": "05:00", "day": "18:00", "evening": "17:00", "night": "23:00"}}
    assert client.put("/api/v1/home/schedule", headers=AUTH, json=bad_order).status_code == 422
    bad_sections = {**got, "sections": {"work": ["Now", "Now", "Home"]}}
    assert client.put("/api/v1/home/schedule", headers=AUTH, json=bad_sections).status_code == 422
    assert client.put("/api/v1/home/schedule", headers=AUTH, json={**got, "weekday": {**got["weekday"], "night": "25:00"}}).status_code == 422


@pytest.fixture
def ai(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_WRAPUP_PATH", str(tmp_path / "wrapup.json"))
    state = {"home": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/siris/hub/v1/presence":
            return httpx.Response(200, json={"home": state["home"], "checked_at": "2026-10-22T08:00:00"})
        return httpx.Response(404)

    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    reset_hub(ENV)
    yield state
    reset_hub({})


def test_context_has_presence_and_last_nights_top_3(ai, tmp_path):
    import json

    today = datetime.now(zone()).date()
    (tmp_path / "wrapup.json").write_text(json.dumps({(today - timedelta(days=1)).isoformat(): {"top3": ["Draft the report"]}}))
    body = TestClient(app).get("/api/v1/home/context", headers=AUTH).json()
    assert body["phase"] in ("morning", "work", "weekend", "evening", "night")
    assert body["home"] is False and body["top3"] == ["Draft the report"] and body["wrapped_up"] is False
    assert sorted(body["sections"]) == ["Home", "Now", "Today"]


def test_context_without_sirisai(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_WRAPUP_PATH", str(tmp_path / "wrapup.json"))
    reset_hub({})
    body = TestClient(app).get("/api/v1/home/context", headers=AUTH).json()
    assert body["home"] is None and body["top3"] == []
