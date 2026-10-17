"""The week view: events, forecast, what's due and CPD for Monday to Sunday."""

from __future__ import annotations

import asyncio
from datetime import date

import httpx
import pytest

from app.career import cpd, store
from app.hub import service
from app.hub.service import Hub
from app.week import service as week

EVENTS = [
    {"title": "School holidays", "start": "2026-10-10", "end": "2026-10-14", "all_day": True, "location": None, "calendar": "Home"},
    {"title": "Stormwater webinar (IPWEA)", "start": "2026-10-14T12:00:00+11:00", "end": "2026-10-14T13:30:00+11:00", "all_day": False, "location": "Online", "calendar": "Work"},
    {"title": "Footy", "start": "2026-10-17T14:00:00+11:00", "end": "2026-10-17T17:00:00+11:00", "all_day": False, "location": None, "calendar": "Home"},
]


class SirisAI:
    def __init__(self) -> None:
        self.paths: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.paths.append(request.url.path)
        if request.url.path == "/siris/hub/v1/calendar":
            assert dict(request.url.params) == {"start": "2026-10-12", "end": "2026-10-19"}
            return httpx.Response(200, json={"events": EVENTS, "guest_mode": False, "unavailable": False})
        if request.url.path == "/siris/hub/v1/forecast":
            return httpx.Response(200, json={"days": [{"date": "2026-10-15", "conditions": "Showers", "high_c": 18, "low_c": 9, "rain_chance_percent": 80}], "unavailable": False})
        if request.url.path == "/siris/brain/insights":
            return httpx.Response(200, json={"deadlines": [{"title": "Werribee Drainage", "days_left": 2}],
                                             "overdue_tasks": [{"task": "Send levels to Dana", "note": "Werribee Drainage", "days_late": 3}]})
        return httpx.Response(404)


@pytest.fixture
def hub(tmp_path, monkeypatch):
    monkeypatch.setenv("SIRISOS_CAREER_PATH", str(tmp_path / "career.json"))
    fake = SirisAI()
    monkeypatch.setattr(service, "transport", httpx.MockTransport(fake))
    monkeypatch.setattr(service, "_shared", None)
    return Hub({"SIRISAI_URL": "http://sirisai:8000", "SIRISAI_API_KEY": "k"})


def test_a_week_holds_each_days_events_forecast_and_whats_due(hub):
    doc = store.load()
    doc.goals = [store.Goal(title="Referee 2 for CPEng", target_date="2026-10-16")]
    doc, _ = cpd.merge(doc, [cpd.CpdRecord(id="r1", date="2026-10-13", title="Pump station design course", hours=3)], "ea.csv")
    store.save(doc)

    body = asyncio.run(week.week(hub, date(2026, 10, 15), today=date(2026, 10, 15)))
    assert body["start"] == "2026-10-12" and body["end"] == "2026-10-19"
    days = {d["date"]: d for d in body["days"]}
    assert [d["date"] for d in body["days"]][0] == "2026-10-12" and len(days) == 7
    # A multi-day all-day event shows on each day it covers, inside the week.
    assert [e["title"] for e in days["2026-10-12"]["events"]] == ["School holidays"]
    assert [e["title"] for e in days["2026-10-13"]["events"]] == ["School holidays"]
    assert days["2026-10-14"]["events"][-1]["cpd"] == {"hours": 1.5, "category": "area"}
    assert days["2026-10-15"]["forecast"]["conditions"] == "Showers"
    assert days["2026-10-17"]["due"] == [{"title": "Werribee Drainage", "kind": "project", "source": "Siris"}]
    assert days["2026-10-16"]["due"] == [{"title": "Referee 2 for CPEng", "kind": "goal", "source": "Career"}]
    assert days["2026-10-13"]["cpd_hours"] == 3
    assert body["cpd"] == {"logged": 3, "planned": 1.5}
    assert body["overdue"][0]["title"] == "Send levels to Dana"
    assert body["unavailable"] == []


def test_without_sirisai_it_still_shows_the_week_and_career(tmp_path, monkeypatch):
    monkeypatch.setenv("SIRISOS_CAREER_PATH", str(tmp_path / "career.json"))
    body = asyncio.run(week.week(Hub({}), date(2026, 10, 15), today=date(2026, 10, 15)))
    assert len(body["days"]) == 7 and body["unavailable"] == ["calendar"]
    assert all(d["events"] == [] for d in body["days"])
