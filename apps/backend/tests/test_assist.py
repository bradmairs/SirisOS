"""11.3: quick capture that files itself, a plan for the day, Home learning what you use, bills on the timeline,
patterns across sections, SirisAI's facts, goals that steer themselves, and while you were away."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.assist import away, capture, dayplan, goals_steer, homeuse, patterns
from app.brief.service import zone
from app.budget import actuals
from app.budget import service as budget
from app.hub import service as hub_service
from app.hub.service import get_hub, reset_hub
from tests.test_budget import PLAN, client  # noqa: F401  (fixture)
from tests.test_hub import AUTH, ENV

NOW = datetime(2026, 11, 24, 7, 40, tzinfo=zone())  # a Tuesday


@pytest.fixture
def c(client, monkeypatch, tmp_path):  # noqa: F811
    for env in ("BUDGET_ACTUALS", "MEALS", "GYM", "TASKS", "GOALS", "HOME_USAGE", "AWAY", "PATTERNS", "HOME_SCHEDULE"):
        monkeypatch.setenv(f"SIRISOS_{env}_PATH", str(tmp_path / f"{env.lower()}.json"))
    monkeypatch.delenv("SIRISOS_MEALIE_URL", raising=False)
    monkeypatch.setattr(budget, "today", lambda: NOW.date())
    from app.assist import api as assist_api
    from app.tasks import service as tasks

    monkeypatch.setattr(assist_api, "_now", lambda: NOW)
    monkeypatch.setattr(tasks, "today", lambda: NOW.date())
    assert client.put("/api/v1/budget", json=PLAN, headers=AUTH).status_code == 200
    state = {"events": [], "readiness": 80, "health_days": [], "inbox": []}

    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p == "/siris/hub/v1/calendar":
            return httpx.Response(200, json={"events": state["events"]})
        if p == "/siris/hub/v1/health/overview":
            return httpx.Response(200, json={"readiness": {"score": state["readiness"], "band": "Steady"}})
        if p == "/siris/hub/v1/health/days":
            return httpx.Response(200, json={"days": state["health_days"]})
        return httpx.Response(404)

    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    reset_hub(ENV)
    from app.attention import service as attention

    async def inbox(hub):
        return {"items": state["inbox"]}

    monkeypatch.setattr(attention, "inbox", inbox)
    return client, state


# -- 1. quick capture -------------------------------------------------------------------------------------------

def test_a_spend_goes_on_the_budget_and_the_bank_line_replaces_it_later(c):
    client, _ = c
    r = client.post("/api/v1/capture/route", json={"text": "spent $85.40 at Woolworths"}, headers=AUTH).json()
    assert r["handled"] and r["where"] == "Budget · Groceries" and r["said"] == "$85.40 at Woolworths"
    assert any(t.get("manual") and t["amount"] == -85.4 for t in actuals.load()["transactions"])
    csv = b"24/11/2026,-85.40,WOOLWORTHS 1234 MELBOURNE AU,1000.00\n"
    out = client.post("/api/v1/budget/actuals/import", files={"file": ("x.csv", csv, "text/csv")}, headers=AUTH).json()
    assert out["imported"] == 1 and out["replaced_by_hand"] == 1
    assert not any(t.get("manual") for t in actuals.load()["transactions"])
    r = client.post("/api/v1/capture/route", json={"text": "$12 coffee"}, headers=AUTH).json()
    assert client.post("/api/v1/capture/undo", json={"undo": r["undo"]}, headers=AUTH).json() == {"undone": True}
    assert not any(t.get("manual") for t in actuals.load()["transactions"])


def test_dinner_gym_note_task_and_a_note_for_siris(c):
    client, _ = c
    from app.gym import store as gym
    from app.meals import service as meals
    from app.tasks import store as task_store

    r = client.post("/api/v1/capture/route", json={"text": "Tacos Thursday"}, headers=AUTH).json()
    assert r["where"] == "Meals" and r["said"] == "Tacos, Thursday" and meals.load()["plan"]["2026-11-26"]["title"] == "Tacos"
    client.post("/api/v1/capture/route", json={"text": "dinner thursday: spag bol"}, headers=AUTH)
    assert client.post("/api/v1/capture/undo", json={"undo": {"kind": "dinner", "date": "2026-11-26", "before": {"title": "Tacos"}}}, headers=AUTH).json()["undone"]
    assert meals.load()["plan"]["2026-11-26"]["title"] == "Tacos"  # put back as it was

    no = client.post("/api/v1/capture/route", json={"text": "Bench felt heavy today"}, headers=AUTH).json()
    assert no["handled"] and no["where"] is None and "SirisGym" in no["error"]  # nothing to put it on, and never Siris
    doc = gym.load()
    doc.sessions.append(gym.Session(title="Upper 1", started_at=(NOW - timedelta(hours=2)).isoformat(), ended_at=(NOW - timedelta(hours=1)).isoformat()))
    gym.save(doc)
    r = client.post("/api/v1/capture/route", json={"text": "Bench felt heavy today"}, headers=AUTH).json()
    assert r["where"] == "SirisGym · Upper 1" and gym.load().sessions[-1].note == "Bench felt heavy today"

    r = client.post("/api/v1/capture/route", json={"text": "Call Sam back Friday"}, headers=AUTH).json()
    assert r["where"] == "Tasks" and r["said"].startswith("Call Sam back · Fri 27 Nov")
    assert any(t.title == "Call Sam back" and t.due == "2026-11-27" for t in task_store.load().tasks)
    assert client.post("/api/v1/capture/route", json={"text": "An idea about solar on the shed"}, headers=AUTH).json() == {"handled": False}


def test_understanding_lines():
    d = date(2026, 11, 22)
    assert capture.understand("paid 30 for the car wash", d)["amount"] == 30
    assert capture.understand("spent $12 on coffee yesterday", d)["date"] == date(2026, 11, 21)
    assert capture.understand("Meeting notes from Monday", d) is None
    assert capture.understand("buy milk", d) == {"kind": "task", "text": "buy milk"}
    assert capture.understand("https://example.com", d) is None


# -- 2. a plan for the day --------------------------------------------------------------------------------------

def test_the_plan_fits_tasks_round_the_calendar(c):
    client, state = c
    for t in ("Write the drainage report", "Call Sam", "Buy milk", "Pick up the parcel"):
        client.post("/api/v1/tasks", json={"text": f"{t} today"}, headers=AUTH)
    state["events"] = [{"title": "Site meeting", "start": "2026-11-24T09:00:00+11:00", "end": "2026-11-24T10:00:00+11:00"}]
    p = client.get("/api/v1/plan/today", headers=AUTH).json()
    kinds = {b["kind"]: b for b in p["blocks"]}
    assert kinds["deep"]["title"] == "Write the drainage report" and kinds["deep"]["minutes"] == 90
    assert not ("09:00" <= kinds["deep"]["start"] < "10:10")  # not in the meeting
    assert kinds["errand"]["title"] == "Errands: Buy milk, Pick up the parcel"
    assert p["events"] == [{"start": "09:00", "end": "10:00"}] and p["left"] == []
    state["readiness"] = 30
    r = dayplan.plan([{"id": "a", "title": "Write report", "area": "work"}, {"id": "b", "title": "Draft design notes", "area": "work"}],
                     [], 8 * 60, work=(480, 990), end=1200, readiness=30)
    assert len([b for b in r["blocks"] if b["kind"] == "deep"]) == 1 and "Low readiness" in r["left"][0]["why"]


# -- 3. Home learns what you use --------------------------------------------------------------------------------

def test_home_tucks_unused_cards_and_raises_used_ones(c):
    client, _ = c
    for i in range(12):
        day = NOW.date() - timedelta(days=i)
        homeuse.record([{"phase": "morning", "widget": "recap", "kind": "seen", "interactive": True},
                        {"phase": "morning", "widget": "weather", "kind": "seen", "interactive": False},
                        {"phase": "morning", "widget": "tasks", "kind": "seen", "interactive": True},
                        {"phase": "morning", "widget": "tasks", "kind": "tap"}], day)
    got = client.get("/api/v1/home/usage", headers=AUTH).json()["phases"]["morning"]
    assert got["recap"]["tucked"] and not got["weather"]["tucked"] and not got["tasks"]["tucked"]
    assert got["tasks"]["score"] == 1.0
    client.post("/api/v1/home/usage", json={"events": [{"phase": "morning", "widget": "recap", "kind": "tap"}]}, headers=AUTH)
    assert not client.get("/api/v1/home/usage", headers=AUTH).json()["phases"]["morning"]["recap"]["tucked"]
    assert client.put("/api/v1/home/usage", json={"on": False}, headers=AUTH).json()["on"] is False


# -- 5. patterns across sections --------------------------------------------------------------------------------

def test_patterns_need_to_be_clear_and_hold_both_halves():
    start = date(2026, 7, 1)
    days = [(start + timedelta(days=i)).isoformat() for i in range(100)]
    drinks = {d: (2.0 if i % 3 == 0 else 0.0) for i, d in enumerate(days)}
    hrv = {}
    for i, d in enumerate(days):
        prev = days[i - 1] if i else None
        hrv[d] = 55.0 + (i % 5) if prev and drinks[prev] else 70.0 + (i % 5)
    found = patterns.find({"alcohol_drinks": drinks, "heart_rate_variability": hrv}, days)
    assert found[0]["id"] == "drinks-hrv" and found[0]["worse"] and found[0]["try"].startswith("Try a dry week")
    assert found[0]["text"].startswith("After drinking, your HRV next morning 57") and "against 72" in found[0]["text"]
    # A difference that flips between halves isn't a pattern.
    flip = {d: (hrv[d] if i < 50 else 140 - hrv[d]) for i, d in enumerate(days)}
    assert not [p for p in patterns.find({"alcohol_drinks": drinks, "heart_rate_variability": flip}, days) if p["id"] == "drinks-hrv"]
    assert patterns.find({"alcohol_drinks": dict(list(drinks.items())[:10]), "heart_rate_variability": hrv}, days) == []


# -- 6. SirisAI's facts ------------------------------------------------------------------------------------------

def test_facts_for_sirisai_with_the_service_key(c, monkeypatch):
    client, _ = c
    csv = (b"03/10/2026,-70.00,BP CONNECT RICHMOND,1000\n15/10/2026,-65.50,AMPOL WALLAN,900\n20/10/2026,-30.00,WOOLWORTHS 1,800\n"
           b"05/11/2026,-80.00,BP CONNECT RICHMOND,700\n")
    client.post("/api/v1/budget/actuals/import", files={"file": ("x.csv", csv, "text/csv")}, headers=AUTH)
    key = "k" * 32
    monkeypatch.setenv("SIRISOS_SERVICE_KEY", key)
    svc = {"Authorization": f"Bearer {key}"}
    f = client.get("/api/v1/facts?topic=spending&q=bp&period=last-month", headers=svc).json()
    assert f["period"] == "October 2026" and f["spent"] == 70.0 and f["count"] == 1
    f = client.get("/api/v1/facts?topic=spending&period=this-year", headers=svc).json()
    assert f["spent"] == 245.5 and f["by_shop"][0]["name"].startswith("bp")
    client.post("/api/v1/capture/route", json={"text": "Spag bol tonight"}, headers=AUTH)
    m = client.get("/api/v1/facts?topic=meals&q=spag", headers=svc).json()
    assert m["last_time"] == {"date": "2026-11-24", "title": "Spag bol"}
    assert client.get("/api/v1/facts?topic=budget", headers=svc).json()["month"] == "2026-11"
    assert client.get("/api/v1/facts?topic=nope", headers=svc).status_code == 422
    assert client.post("/api/v1/capture/route", json={"text": "x"}, headers=svc).status_code == 403  # read only


# -- 7. goals that steer themselves ------------------------------------------------------------------------------

def test_goal_pace_and_a_step():
    g = {"kind": "running_km", "value": 900, "target": 1200, "state": "behind", "unit": "km", "title": "Run 1,200 km", "year": 2026}
    p = goals_steer.project(g, date(2026, 11, 22))
    assert p["projected_percent"] == 84 and p["weekly"] == 50
    assert goals_steer.step(g, p)["text"] == "Run 50 km this week: 4 runs of about 12 km."
    assert goals_steer.step({**g, "state": "on_track"}, p) is None
    assert goals_steer.project({"kind": "done", "value": 0, "target": None}, date(2026, 11, 22))["projected"] is None


def test_steer_endpoint_and_monday_push(c):
    client, _ = c
    client.post("/api/v1/goals", json={"title": "Read 24 books", "kind": "count", "target": 24, "progress": 6, "unit": "books"}, headers=AUTH)
    s = client.get("/api/v1/goals/steer", headers=AUTH).json()
    g = s["goals"][0]
    assert g["state"] == "behind" and g["projected_percent"] < 100 and "more books this week" in g["step"]["text"]
    msgs = asyncio.run(goals_steer.push_message(get_hub(), datetime(2026, 11, 23, 18, 5, tzinfo=zone())))
    assert msgs and msgs[0]["title"] == "Read 24 books: a step this week"


# -- 8. while you were away --------------------------------------------------------------------------------------

def test_away_summary_after_a_day_and_got_it(c):
    client, state = c
    assert client.get("/api/v1/away", headers=AUTH).json() == {"away": False}  # the first look starts the clock
    away.touch(NOW - timedelta(hours=30))
    state["inbox"] = [{"id": "a1", "title": "Backup failed", "severity": "urgent"}, {"id": "a2", "title": "Note", "severity": "info"}]
    client.post("/api/v1/tasks", json={"text": "Pay rego today"}, headers=AUTH)
    state["events"] = [{"title": "Dentist", "start": "2026-11-24T15:00:00+11:00", "end": "2026-11-24T16:00:00+11:00"}]
    s = client.get("/api/v1/away", headers=AUTH).json()
    assert s["away"] and s["away_for"] == "30 hours"
    assert [i["kind"] for i in s["items"]][:2] == ["inbox", "tasks"] and s["items"][0]["lines"] == ["Backup failed"]
    assert any(i["kind"] == "calendar" and "Dentist" in i["lines"][0] for i in s["items"])
    assert s["keys"] == ["inbox:a1"]
    client.post("/api/v1/away/done", json={"keys": s["keys"]}, headers=AUTH)
    from app.push import smart

    assert "inbox:a1" in smart.load()["seen"]
    assert client.get("/api/v1/away", headers=AUTH).json()["away"] is False


# -- 4. a charge that went up ------------------------------------------------------------------------------------

def test_price_rise_notification_once_per_price(c):
    client, _ = c
    from app.budget import forecast

    rows = "".join(f"{d:02d}/{m:02d}/2026,-{amt},NETFLIX.COM,1000\n" for (d, m, amt) in ((5, 7, "18.99"), (5, 8, "18.99"), (5, 9, "18.99"), (5, 10, "18.99"), (5, 11, "22.99")))
    client.post("/api/v1/budget/actuals/import", files={"file": ("n.csv", rows.encode(), "text/csv")}, headers=AUTH)
    msgs = forecast.price_rise_messages(NOW.replace(hour=10))
    assert msgs and msgs[0]["title"].endswith("went up $4.00") and msgs[0]["key"].endswith(":22.99")
    assert json.dumps(msgs)  # serialisable
