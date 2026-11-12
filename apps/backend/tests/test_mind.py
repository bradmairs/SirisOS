from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.mind import api as mind_api, service
from tests.test_hub import AUTH


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_MIND_PATH", str(tmp_path / "mind.json"))
    return TestClient(app, headers=AUTH)


def days_back(n: int, metrics) -> list[dict]:
    t = service.today()
    return [{"date": (t - timedelta(days=n - 1 - i)).isoformat(), "metrics": metrics(i)} for i in range(n)]


def test_mood_from_apple_or_the_quick_log_on_one_scale():
    assert service.valence({"mood_valence": 0.4}) == 0.4
    assert service.valence({"mood": 5}) == 1.0 and service.valence({"mood": 2}) == -0.5
    assert service.valence({}) is None
    assert service.word(0.5) == "Pleasant" and service.word(-0.9) == "Very unpleasant" and service.word(0.0) == "Neutral"


def test_the_tab_shows_mood_mindful_minutes_and_what_goes_with_a_better_mood(client, monkeypatch):
    # Even days: slept 8 h and mood 0.6; odd days: 6 h and -0.2.
    data = days_back(20, lambda i: {"mood_valence": 0.6 if i % 2 == 0 else -0.2, "sleep_hours": 8 if i % 2 == 0 else 6, "mindful_minutes": 10})

    async def fake_get(hub, path, params=None, timeout=20.0):
        assert path == "/siris/hub/v1/health/days"
        return {"guest_mode": False, "days": data}

    monkeypatch.setattr(mind_api.sirisai_api, "get", fake_get)
    client.post("/api/v1/mind/sessions", json={"tool": "breathing", "seconds": 120})
    client.post("/api/v1/mind/journal", json={"kind": "gratitude", "text": "Coffee with Sam"})
    r = client.get("/api/v1/mind").json()
    assert r["available"] and len(r["days"]) == 20
    assert r["today"]["mindful_minutes"] == 10 and r["today"]["here_minutes"] == 2.0
    assert r["week"]["mindful_minutes"] == 72.0 and r["tools_minutes_week"] == 2.0
    assert [p["key"] for p in r["patterns"]] == ["sleep"]
    assert "better after 7 hours' sleep" in r["patterns"][0]["text"]
    assert r["journal"][0]["text"] == "Coffee with Sam"
    entry = r["journal"][0]["id"]
    assert client.delete(f"/api/v1/mind/journal/{entry}").status_code == 200
    assert client.delete(f"/api/v1/mind/journal/{entry}").status_code == 404


def test_without_sirisai_the_tools_still_work(client, monkeypatch):
    async def down(*a, **k):
        return None

    monkeypatch.setattr(mind_api.sirisai_api, "get", down)
    r = client.get("/api/v1/mind").json()
    assert r["available"] is False and r["days"] == []


def test_clarity_streak_slips_urges_and_plan(client):
    start = (service.today() - timedelta(days=10)).isoformat()
    r = client.post("/api/v1/mind/clarity/start", json={"date": start}).json()
    assert r["streak"] == 10 and r["best"] == 10 and r["next"] == {"days": 14, "left": 4}
    assert r["clear_last_30"] == 10
    r = client.post("/api/v1/mind/clarity/urge", json={"trigger": "bored", "outcome": "rode"}).json()
    assert r["urges_week"] == 1 and r["rode_out_week"] == 1 and r["triggers"] == [{"trigger": "bored", "count": 1}]
    r = client.post("/api/v1/mind/clarity/check", json={"status": "clear"}).json()
    assert r["checked_today"] == "clear" and r["streak"] == 10
    r = client.post("/api/v1/mind/clarity/urge", json={"trigger": "late night", "outcome": "slip"}).json()
    assert r["streak"] == 0 and r["best"] == 10 and r["checked_today"] == "slip"
    assert r["month"][-1]["status"] == "slip"
    r = client.put("/api/v1/mind/clarity/plan", json={"reasons": ["Be present", " "], "plan": ["Phone out of the bedroom"]}).json()
    assert r["reasons"] == ["Be present"] and r["plan"] == ["Phone out of the bedroom"]


def test_clarity_starts_on_the_first_clear_check(client):
    r = client.post("/api/v1/mind/clarity/check", json={"status": "clear"}).json()
    assert r["started"] == date.today().isoformat() or r["started"] == service.today().isoformat()
    assert r["streak"] == 0
