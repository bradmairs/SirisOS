"""10.2: last month in short, on Home and filed in Siris once."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.budget import actuals
from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import get_hub, reset_hub
from app.mind import service as mind
from app.recap import api as recap_api
from app.recap import service as recap
from app.work import timesheet
from tests.test_hub import AUTH, ENV

TODAY = date(2026, 12, 2)


@pytest.fixture
def c(monkeypatch, tmp_path):
    for env, name in [("SIRISOS_RECAP_PATH", "recap.json"), ("SIRISOS_BUDGET_ACTUALS_PATH", "a.json"), ("SIRISOS_BUDGET_PATH", "b.json"),
                      ("SIRISOS_TIMESHEET_PATH", "t.json"), ("SIRISOS_MIND_PATH", "m.json")]:
        monkeypatch.setenv(env, str(tmp_path / name))
    monkeypatch.setattr(recap_api, "_today", lambda: TODAY)
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/siris/hub/v1/health/days":
            days = []
            d = date(2026, 10, 1)
            while d <= date(2026, 11, 30):
                nov = d.month == 11
                days.append({"date": d.isoformat(), "metrics": {"sleep_hours": 7.2 if nov else 6.8, "resting_heart_rate": 55 if nov else 58,
                                                                 "steps": 9500, "mood_valence": 0.4}})
                d += timedelta(days=1)
            return httpx.Response(200, json={"guest_mode": False, "days": days})
        if request.url.path == "/siris/brain/capture":
            captured.append(json.loads(request.content))
            return httpx.Response(200, json={"title": "November 2026 recap"})
        return httpx.Response(404)

    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    reset_hub(ENV)
    client = TestClient(app)
    client.captured = captured  # type: ignore[attr-defined]
    return client


def test_recap_card_and_filing(c, monkeypatch):
    timesheet.add("Pump station review 6h", None, date(2026, 11, 3))
    timesheet.add("Design 7.5h", None, date(2026, 11, 4))
    doc = mind.load()
    doc["habits"] = [{"id": "h1", "name": "Stretch", "created": "2026-11-20", "done": ["2026-11-20", "2026-11-21", "2026-11-25"], "days": []}]
    doc["clarity"]["start"] = "2026-11-01"
    mind.save(doc)
    actuals.set_balance("Everyday", 1000, date(2026, 10, 31), kind="everyday")
    actuals.set_balance("Everyday", 1600, date(2026, 11, 30), kind="everyday")

    r = c.get("/api/v1/recap", headers=AUTH).json()
    assert r["month"] == "2026-11" and r["show"] and r["title"] == "November 2026 recap"
    assert r["health"]["sleep_hours"] == {"value": 7.2, "before": 6.8}
    assert r["habits"] == [{"name": "Stretch", "kept": 3, "of": 11, "rate": 0.27}]
    assert r["work"]["timesheet_hours"] == 13.5
    assert r["money"]["net_worth_change"] == 600
    text = r["text"]
    assert "Slept 7.2 h a night (from 6.8)" in text and "Net worth up $600" in text and "13.5 h on the timesheet" in text
    assert "Stretch: 3 of 11 days" in text and "Mood mostly slightly pleasant" in text
    assert "larity" not in text and "gym" not in text.lower()

    msgs = asyncio.run(recap.push_message(get_hub(), datetime(2026, 12, 1, 8, 5)))
    assert msgs[0]["key"] == "recap:2026-11" and msgs[0]["title"] == "Your November in short"
    assert c.captured[0]["title"] == "November 2026 recap" and c.captured[0]["tags"] == ["monthly-recap"]
    assert asyncio.run(recap.push_message(get_hub(), datetime(2026, 12, 1, 9, 0))) == []  # filed once
    assert len(c.captured) == 1

    c.post("/api/v1/recap/2026-11/seen", headers=AUTH)
    assert c.get("/api/v1/recap", headers=AUTH).json()["show"] is False
    assert c.post("/api/v1/recap/nope/seen", headers=AUTH).status_code == 422


def test_not_before_8am_on_the_1st_or_after_the_first_week(c):
    assert asyncio.run(recap.push_message(get_hub(), datetime(2026, 12, 1, 7, 0))) == []
    assert asyncio.run(recap.push_message(get_hub(), datetime(2026, 12, 9, 9, 0))) == []
