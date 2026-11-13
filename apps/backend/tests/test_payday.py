"""9.5: a pay day on each income line, the next one worked out, a SirisAI reminder kept in step, and Home on the day."""

import asyncio
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.budget import api as budget_api, service
from app.entrypoint import app
from tests.test_hub import AUTH


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_BUDGET_PATH", str(tmp_path / "budget.json"))
    return TestClient(app, headers=AUTH)


@pytest.mark.parametrize("pay_day,every,today,want", [
    ("2026-11-06", "fortnightly", "2026-11-13", "2026-11-20"),
    ("2026-11-06", "fortnightly", "2026-11-20", "2026-11-20"),  # on the day
    ("2026-11-06", "weekly", "2026-11-14", "2026-11-20"),
    ("2026-01-31", "monthly", "2026-02-10", "2026-02-28"),  # the 31st in February: its last day
    ("2026-01-31", "monthly", "2026-03-01", "2026-03-31"),
    ("2026-01-15", "quarterly", "2026-05-01", "2026-07-15"),
    ("2025-06-30", "yearly", "2026-07-01", "2027-06-30"),
    ("2027-01-01", "monthly", "2026-11-13", "2027-01-01"),  # a first pay day still to come
])
def test_the_next_pay_day(pay_day, every, today, want):
    assert service.next_pay({"pay_day": pay_day, "every": every}, date.fromisoformat(today)).isoformat() == want


def test_a_pay_day_is_kept_and_home_sees_it_on_the_day(client, monkeypatch):
    sent: list[tuple[str, dict]] = []

    async def fake_post(hub, path, json=None, **kw):
        sent.append((path, json))
        return {"id": len(sent)} if path == "/siris/hub/v1/reminders" else {}

    monkeypatch.setattr(budget_api.sirisai_api, "post", fake_post, raising=False)
    import app.hub.sirisai_api as real
    monkeypatch.setattr(real, "post", fake_post)
    monkeypatch.setattr(service, "today", lambda: date(2026, 11, 13))
    body = {"currency": "AUD", "income": [{"name": "Salary", "amount": 3200, "every": "fortnightly", "pay_day": "2026-10-30"},
                                          {"name": "Interest", "amount": 20, "every": "monthly"}], "sections": {}}
    r = client.put("/api/v1/budget", json=body).json()
    assert r["income"][0]["pay_day"] == "2026-10-30" and "pay_day" not in r["income"][1]
    assert r["pay_days"] == [{"id": r["income"][0]["id"], "name": "Salary", "amount": 3200, "every": "fortnightly", "next": "2026-11-13", "days": 0}]
    p = client.get("/api/v1/budget/pay-days").json()
    assert [x["name"] for x in p["today"]] == ["Salary"]
    assert client.put("/api/v1/budget", json={**body, "income": [{**body["income"][0], "pay_day": "not a date"}]}).status_code == 422


def test_sirisai_gets_one_reminder_at_8am_kept_in_step(client, monkeypatch):
    calls: list[tuple[str, dict | None]] = []

    async def fake_post(hub, path, json=None, **kw):
        calls.append((path, json))
        return {"id": 100 + len(calls)} if path == "/siris/hub/v1/reminders" else {}

    import app.hub.sirisai_api as real
    monkeypatch.setattr(real, "post", fake_post)
    monkeypatch.setattr(service, "today", lambda: date(2026, 11, 13))

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 13, 7, 0, tzinfo=tz)

    monkeypatch.setattr(service, "datetime", Clock)
    body = {"currency": "AUD", "income": [{"id": "sal", "name": "Salary", "amount": 3200, "every": "fortnightly", "pay_day": "2026-11-20"}], "sections": {}}
    client.put("/api/v1/budget", json=body)
    made = [c for c in calls if c[0] == "/siris/hub/v1/reminders"]
    assert len(made) == 1 and made[0][1]["due_at"].startswith("2026-11-20T08:00:00")
    assert made[0][1]["message"] == "Pay day: Salary, $3,200.00, is due in today."

    calls.clear()
    asyncio.run(service.sync_pay_reminders(None))
    assert calls == []  # nothing changed: SirisAI isn't asked again

    client.put("/api/v1/budget", json={**body, "income": [{**body["income"][0], "pay_day": "2026-11-27"}]})  # a new date
    assert calls[0][0] == "/siris/hub/v1/reminders/101/done" and calls[1][1]["due_at"].startswith("2026-11-27T08:00")

    calls.clear()
    client.put("/api/v1/budget", json={**body, "income": []})  # the line's gone
    assert [c[0] for c in calls] == ["/siris/hub/v1/reminders/102/done"]
