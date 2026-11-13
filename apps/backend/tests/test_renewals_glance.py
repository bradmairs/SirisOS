"""9.4: documents and renewals, the iPhone widget's glance, habits in what helps and the review."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.mind import service as mind
from app.renewals import service as renewals
from tests.test_hub import AUTH


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_DATA_DIR", str(tmp_path))
    for env in ("SIRISOS_RENEWALS_PATH", "SIRISOS_GLANCE_PATH", "SIRISOS_MIND_PATH", "SIRISOS_GYM_PATH"):
        monkeypatch.delenv(env, raising=False)
    return TestClient(app, headers=AUTH)


def test_renewals_soonest_first_with_reminders(client):
    t = renewals.today()
    client.post("/api/v1/renewals", json={"name": "Passport", "kind": "passport", "expires": (t + timedelta(days=200)).isoformat()})
    r = client.post("/api/v1/renewals", json={"name": "Car rego", "kind": "rego", "expires": (t + timedelta(days=30)).isoformat()}).json()["renewals"]
    assert [(x["name"], x["days_left"], x["state"]) for x in r] == [("Car rego", 30, "soon"), ("Passport", 200, "fine")]
    morning = datetime.combine(t, datetime.min.time()).replace(hour=9, minute=5)
    [m] = renewals.push_messages(morning)
    assert m["title"].startswith("Car rego expires in 30 days") and m["url"] == "/life"
    assert renewals.push_messages(morning.replace(hour=8)) == []
    rego = r[0]["id"]
    r = client.patch(f"/api/v1/renewals/{rego}", json={"expires": (t + timedelta(days=395)).isoformat()}).json()["renewals"]
    assert r[0]["name"] == "Passport" and renewals.push_messages(morning) == []
    assert client.delete(f"/api/v1/renewals/{rego}").status_code == 200
    assert client.delete(f"/api/v1/renewals/{rego}").status_code == 404
    assert client.post("/api/v1/renewals", json={"name": "X", "expires": "soon"}).status_code == 422


def test_the_glance_opens_only_with_its_key(client, monkeypatch):
    plain = TestClient(app)
    assert plain.get("/api/v1/glance?key=nope").status_code == 401
    assert plain.post("/api/v1/glance/key").status_code == 401  # making a key needs you signed in
    assert client.get("/api/v1/glance/key").json()["set"] is False
    key = client.post("/api/v1/glance/key").json()["key"]
    t = renewals.today()
    renewals.add("Medicare card", "medicare", (t + timedelta(days=12)).isoformat())
    mind.add_habit("Stretch")
    from app.gym import api as gym_api
    import time
    monkeypatch.setitem(gym_api.rest_info, "until", time.time() + 60)
    monkeypatch.setitem(gym_api.rest_info, "next", "Bench, set 2")
    g = plain.get(f"/api/v1/glance?key={key}").json()
    assert g["renewal"] == {"name": "Medicare card", "days_left": 12}
    assert g["habits"] == {"done": 0, "of": 1, "left": ["Stretch"]}
    assert g["rest"]["next"] == "Bench, set 2"
    assert "tasks" in g and "readiness" in g and "event" in g
    assert plain.get("/api/v1/glance?key=glance_wrong").status_code == 401
    client.delete("/api/v1/glance/key")
    assert plain.get(f"/api/v1/glance?key={key}").status_code == 401


def test_habits_in_what_helps_and_the_review(client):
    t = mind.today()
    mind.add_habit("Stretch")
    doc = mind.load()
    h = doc["habits"][0]
    h["created"] = (t - timedelta(days=19)).isoformat()
    h["done"] = [(t - timedelta(days=i)).isoformat() for i in range(20) if i % 2 == 0]
    mind.save(doc)
    rows = [{"date": (t - timedelta(days=i)).isoformat(), "valence": 0.5 if i % 2 == 0 else -0.1} for i in range(20)]
    texts = [p["text"] for p in mind.patterns(rows, mind.load()["habits"])]
    assert "Your mood is better on days you ticked “Stretch” than on days you didn't." in texts

    monday = t - timedelta(days=t.weekday())
    days = [{"date": (monday - timedelta(days=7 - i)).isoformat(), "metrics": {"mood_valence": 0.1, "mindful_minutes": 5}} for i in range(7)]
    days += [{"date": (monday + timedelta(days=i)).isoformat(), "metrics": {"mood_valence": 0.5, "mindful_minutes": 10}} for i in range(t.weekday() + 1)]
    w = mind.week(days, monday, t)
    assert w["mood"] == 0.5 and w["mood_before"] == 0.1 and w["word"] == "Pleasant"
    assert w["mindful_minutes"] == 10 * (t.weekday() + 1) and w["mindful_before"] == 35
    assert w["habits"][0]["name"] == "Stretch" and w["habits"][0]["of"] == t.weekday() + 1
