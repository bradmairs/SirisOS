"""11.15: the privacy check, the wall display and the fuller monthly recap."""

from __future__ import annotations

import importlib.util
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.brief.service import zone
from app.entrypoint import app
from tests.test_hub import AUTH

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("privacy_check", ROOT / "scripts/privacy_check.py")
privacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(privacy)  # type: ignore[union-attr]


# -- the privacy check ------------------------------------------------------------------------------------------------

def test_lan_addresses_and_real_emails_are_caught_examples_are_not(monkeypatch):
    monkeypatch.delenv("PRIVACY_TERMS", raising=False)
    lines = [("a.py", 1, 'URL = "http://10.1.2.3:8000"'), ("b.md", 2, "write to someone@gmail.com"),  # privacy: ok (made-up examples for the check itself)
             ("c.py", 3, "e.g. http://172.20.0.5 privacy: ok"), ("d.py", 4, "x = 'me@example.com', 'bot@users.noreply.github.com'"),
             ("e.py", 5, "version 11.15.0 and 1.2.3.4")]
    found = privacy.check(lines, privacy.terms())
    assert len(found) == 2 and found[0].startswith("a.py:1: a LAN address") and found[1].startswith("b.md:2: an email address")


def test_your_private_list_is_matched_without_printing_it(monkeypatch):
    monkeypatch.setenv("PRIVACY_TERMS", "Elmstead Rd,5929,Jo Bloggs")
    found = privacy.check([("x.md", 7, "Expenses 5,929 a month"), ("y.py", 8, "lives on elmstead rd"), ("z.py", 9, "59290 is fine"),
                           ("w.py", 1, "Jo Bloggs's pay")], privacy.terms())
    assert [f.split(":")[0] for f in found] == ["x.md", "y.py", "w.py"]
    assert all("5929" not in f and "Elmstead" not in f for f in found)  # never the value itself


# -- the wall display -----------------------------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch, tmp_path):
    for env, name in (("SIRISOS_WALL_PATH", "wall.json"), ("SIRISOS_RECAP_PATH", "recap.json"), ("SIRISOS_GYM_PATH", "gym.json"),
                      ("SIRISOS_HOME_USAGE_PATH", "home-usage.json"), ("SIRISOS_RENEWALS_PATH", "renewals.json")):
        monkeypatch.setenv(env, str(tmp_path / name))
    return TestClient(app, headers=AUTH)


def test_the_wall_opens_with_its_own_key_and_reads_only_its_feed(client, monkeypatch):
    from app.home import context

    async def current(hub, now=None):
        return {"phase": "night", "events": [{"title": "Dentist", "start": f"{datetime.now(zone()).date()}T15:00:00", "end": None, "all_day": False},
                                             {"title": "Flight", "start": "2099-01-01T09:00:00", "all_day": False}],
                "weather_today": {"summary": "Sunny", "max_c": 24, "min_c": 12}}
    monkeypatch.setattr(context, "current", current)
    bare = TestClient(app)
    assert bare.get("/api/v1/wall?key=wall_nope").status_code == 401
    made = client.post("/api/v1/wall/key").json()
    assert made["key"].startswith("wall_") and made["path"] == f"/wall?key={made['key']}"
    feed = bare.get(f"/api/v1/wall?key={made['key']}").json()
    assert feed["dim"] is True and feed["weather"]["summary"] == "Sunny"
    assert [e["title"] for e in feed["today"]] == ["Dentist"] and [e["title"] for e in feed["tomorrow"]] == ["Flight"]
    assert set(feed) == {"now", "phase", "dim", "weather", "weather_tomorrow", "today", "tomorrow", "bins", "dinner", "parcels"}
    assert bare.get(f"/api/v1/tasks", headers={"Authorization": f"Bearer {made['key']}"}).status_code == 401  # opens nothing else
    client.delete("/api/v1/wall/key")
    assert bare.get(f"/api/v1/wall?key={made['key']}").status_code == 401


# -- the monthly recap --------------------------------------------------------------------------------------------------

def test_the_recap_has_the_gym_where_you_went_and_whats_renewing(client):
    from app.assist import homeuse
    from app.recap import service as recap

    client.post("/api/v1/gym/sessions", json={"id": "a", "title": "Push", "started_at": "2026-11-03T07:00:00+11:00", "ended_at": "2026-11-03T07:40:00+11:00",
                                              "entries": [{"exercise": "bench-press", "sets": [{"weight": 80, "reps": 8}] * 3}]})
    homeuse.record([{"phase": "evening", "widget": "/gym", "kind": "visit"}], date(2026, 11, 3))
    homeuse.record([{"phase": "evening", "widget": "/gym", "kind": "visit"}, {"phase": "morning", "widget": "/tasks", "kind": "visit"}], date(2026, 11, 4))
    client.post("/api/v1/renewals", json={"name": "Car rego", "kind": "rego", "expires": "2026-12-15"})
    g = recap.gym("2026-11")
    assert g["workouts"] == 1 and g["volume"] == 1920 and g["before"] == 0
    assert recap.places("2026-11")["top"][0] == {"path": "/gym", "days": 2}
    assert recap.ahead(date(2026, 12, 1)) == [{"name": "Car rego", "expires": "2026-12-15"}]
    text = recap.as_text({"gym": g, "places": recap.places("2026-11"), "ahead": recap.ahead(date(2026, 12, 1)), "goals": [{"title": "Run 500 km", "percent": 40, "through": 92}]})
    assert "1 workout (from 0), 1,920 kg lifted." in text and "Opened most: Gym (2 days), Tasks (1 days)." in text
    assert "Renewing soon: Car rego (15 Dec)." in text and "Behind on Run 500 km: 40% there, 92% through the year." in text
