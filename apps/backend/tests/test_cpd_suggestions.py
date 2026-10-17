"""CPD from the calendar, and the calendar range API it reads."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app.career import cpd, store, suggest
from app.entrypoint import app
from app.hub import service
from app.hub.service import reset_hub
from tests.test_hub import AUTH

TODAY = date(2026, 10, 17)
EVENTS = [
    {"title": "Stormwater webinar (IPWEA)", "start": "2026-10-14T12:00:00+11:00", "end": "2026-10-14T13:30:00+11:00", "all_day": False, "location": "Online", "calendar": "Work"},
    {"title": "Ozwater 2026", "start": "2026-06-12", "end": "2026-06-14", "all_day": True, "location": "Melbourne", "calendar": "Work"},
    {"title": "Safe design workshop", "start": "2026-10-28T09:00:00+11:00", "end": "2026-10-28T16:30:00+11:00", "all_day": False, "location": None, "calendar": "Work"},
    {"title": "Haircut", "start": "2026-10-15T17:00:00+11:00", "end": "2026-10-15T17:30:00+11:00", "all_day": False, "location": None, "calendar": "Home"},
]


@pytest.fixture
def career_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SIRISOS_CAREER_PATH", str(tmp_path / "career.json"))


def test_finds_cpd_looking_events_with_hours_and_a_category(career_file):
    found = suggest.suggestions(store.load(), EVENTS, TODAY)
    by = {s["title"]: s for s in found}
    assert set(by) == {"Stormwater webinar (IPWEA)", "Ozwater 2026", "Safe design workshop"}
    assert by["Stormwater webinar (IPWEA)"]["hours"] == 1.5 and by["Stormwater webinar (IPWEA)"]["upcoming"] is False
    assert by["Ozwater 2026"]["hours"] == 15.0  # two all-day days
    assert by["Safe design workshop"]["hours"] == 7.5 and by["Safe design workshop"]["upcoming"] is True
    assert by["Safe design workshop"]["category"] == "risk"


def test_drops_events_already_logged_or_dealt_with(career_file):
    doc = store.load()
    doc, _ = cpd.merge(doc, [cpd.CpdRecord(id="r1", date="2026-06-12", title="Ozwater 2026 conference", hours=14)], "ea.csv")
    doc = doc.model_copy(update={"cpd": doc.cpd.model_copy(update={"suggestions": {suggest.key(EVENTS[0]): "logged"}})})
    titles = [s["title"] for s in suggest.suggestions(doc, EVENTS, TODAY)]
    assert titles == ["Safe design workshop"]


def test_api_reads_sirisai_and_remembers_marks(career_file, monkeypatch):
    client = TestClient(app)
    # No SirisAI: nothing to suggest, and it says why.
    assert client.get("/api/v1/career/cpd/suggestions", headers=AUTH).json() == {"suggestions": [], "unavailable": True, "guest_mode": False}

    asked = []

    def sirisai(request: httpx.Request) -> httpx.Response:
        asked.append(dict(request.url.params))
        return httpx.Response(200, json={"start": "", "end": "", "guest_mode": False, "events": EVENTS, "unavailable": False})

    monkeypatch.setattr(service, "transport", httpx.MockTransport(sirisai))
    reset_hub({"SIRISAI_URL": "http://sirisai:8000", "SIRISAI_API_KEY": "ai-key"})
    try:
        cal = client.get("/api/v1/calendar", params={"start": "2026-10-12", "end": "2026-10-19"}, headers=AUTH).json()
        assert [e["title"] for e in cal["events"]][:1] == ["Stormwater webinar (IPWEA)"] and cal["unavailable"] is False
        assert asked[0] == {"start": "2026-10-12", "end": "2026-10-19"}
        assert client.get("/api/v1/calendar", params={"start": "2026-10-12", "end": "2026-10-12"}, headers=AUTH).status_code == 422

        found = client.get("/api/v1/career/cpd/suggestions", headers=AUTH).json()["suggestions"]
        webinar = next(s for s in found if s["title"].startswith("Stormwater"))
        assert client.post(f"/api/v1/career/cpd/suggestions/{webinar['key']}", headers=AUTH, json={"status": "logged"}).status_code == 200
        again = [s["title"] for s in client.get("/api/v1/career/cpd/suggestions", headers=AUTH).json()["suggestions"]]
        assert "Stormwater webinar (IPWEA)" not in again
    finally:
        reset_hub({})
