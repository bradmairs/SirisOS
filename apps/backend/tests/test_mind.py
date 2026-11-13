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
    assert r["journal_count"] == 1 and "journal" not in r and r["locking"] is False
    entry = client.get("/api/v1/mind/journal").json()["journal"][0]["id"]  # no passkey: nothing to lock with
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


# -- 9.2 -------------------------------------------------------------------------------------------------------------

from datetime import datetime  # noqa: E402

from app.mind import api as _mind_api  # noqa: E402
from app.security import service as security, webauthn  # noqa: E402


def test_the_journal_and_clarity_open_only_with_face_id(client, monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_SECURITY_PATH", str(tmp_path / "security.json"))
    monkeypatch.setattr(_mind_api, "locking", lambda: True)
    key = security.Passkey(id="cred1", label="iPhone", public_key=webauthn.b64url(b"k"), alg=-7, sign_count=0, rp_id="testserver", created_at="2026-11-01")
    monkeypatch.setattr(security, "passkeys", lambda: [key])
    monkeypatch.setattr(security, "save_passkeys", lambda items: None)
    assert client.get("/api/v1/mind/clarity").status_code == 423
    assert client.get("/api/v1/mind/journal").status_code == 423
    assert client.post("/api/v1/mind/journal", json={"kind": "note", "text": "Writing still works locked"}).status_code == 200

    opts = client.post("/api/v1/mind/unlock/options").json()
    assert opts["allowCredentials"] == [{"type": "public-key", "id": "cred1"}]
    monkeypatch.setattr(webauthn, "verify_assertion", lambda *a, **k: (_ for _ in ()).throw(webauthn.WebAuthnError("Bad signature.")))
    assert client.post("/api/v1/mind/unlock", json={"challenge": opts["challenge"], "id": "cred1", "response": {}}).status_code == 401
    opts = client.post("/api/v1/mind/unlock/options").json()
    monkeypatch.setattr(webauthn, "verify_assertion", lambda *a, **k: 1)
    token = client.post("/api/v1/mind/unlock", json={"challenge": opts["challenge"], "id": "cred1", "response": {}}).json()["token"]
    assert client.post("/api/v1/mind/unlock", json={"challenge": opts["challenge"], "id": "cred1", "response": {}}).status_code == 401  # used once
    h = {"X-Mind-Unlock": token}
    assert client.get("/api/v1/mind/clarity", headers=h).status_code == 200
    assert client.get("/api/v1/mind/journal", headers=h).json()["journal"][0]["text"] == "Writing still works locked"
    client.post("/api/v1/mind/lock", headers=h)
    assert client.get("/api/v1/mind/clarity", headers=h).status_code == 423
    _mind_api._unlocked.clear()


def test_alcohol_caffeine_and_the_gym_in_what_helps():
    t = service.today()
    rows = []
    for i in range(20):
        d = (t - timedelta(days=19 - i)).isoformat()
        heavy = i % 2 == 1  # drinks on odd days, so even days are "the day after"
        rows.append({"date": d, "valence": -0.4 if i % 2 == 0 and i > 0 else 0.4, "alcohol_drinks": 4 if heavy else 0, "logged_any": 1,
                     "caffeine_mg": 100, "gym": i % 2 == 1})
    keys = [p["key"] for p in service.patterns(rows)]
    assert "alcohol" in keys and "gym" in keys and "caffeine" not in keys
    alcohol = next(p for p in service.patterns(rows) if p["key"] == "alcohol")
    assert alcohol["text"] == "Your mood is lower the day after 3 drinks or more than after fewer."


def test_the_moment_nudge_comes_half_an_hour_before_the_usual_time(client):
    t = service.today()
    doc = service.load()
    doc["clarity"]["start"] = (t - timedelta(days=5)).isoformat()
    doc["clarity"]["urges"] = [{"id": str(i), "at": f"{(t - timedelta(days=i)).isoformat()}T22:15:00+11:00", "trigger": "late night", "outcome": "rode"} for i in range(1, 4)]
    service.save(doc)
    c = client.get("/api/v1/mind/clarity").json()
    assert c["risky"] == {"hour": 22, "count": 3, "nudge_at": "21:30"} and c["nudge"] is False
    at = datetime.combine(t, datetime.min.time()).replace(hour=21, minute=40)
    assert service.push_message(at) == []  # off until you turn it on
    assert client.put("/api/v1/mind/clarity/nudge", json={"on": True}).json()["nudge"] is True
    [m] = service.push_message(at)
    assert (m["title"], m["body"], m["topic"]) == ("A moment for you", "Check in with yourself.", "nudges")
    assert service.push_message(at.replace(hour=20)) == [] and service.push_message(at.replace(hour=22, minute=5)) == []


def test_habits_with_streaks(client):
    h = client.post("/api/v1/mind/habits", json={"name": "Stretch"}).json()["habits"][0]
    t = service.today()
    for back in (3, 2, 1):
        client.post(f"/api/v1/mind/habits/{h['id']}/check", json={"date": (t - timedelta(days=back)).isoformat()})
    got = client.get("/api/v1/mind/habits").json()["habits"][0]
    assert got["streak"] == 3 and got["best"] == 3 and got["today"] is False  # not done today yet: the streak holds
    got = client.post(f"/api/v1/mind/habits/{h['id']}/check", json={}).json()["habits"][0]
    assert got["streak"] == 4 and got["today"] is True and got["month"][-1] == {"date": t.isoformat(), "done": True}
    got = client.post(f"/api/v1/mind/habits/{h['id']}/check", json={"done": False, "date": (t - timedelta(days=2)).isoformat()}).json()["habits"][0]
    assert got["streak"] == 2 and got["best"] == 2
    assert client.post(f"/api/v1/mind/habits/{h['id']}/check", json={"date": (t + timedelta(days=1)).isoformat()}).status_code == 422
    assert client.patch(f"/api/v1/mind/habits/{h['id']}", json={"archived": True}).json()["habits"] == []
    assert client.post("/api/v1/mind/habits/nope/check", json={}).status_code == 404
