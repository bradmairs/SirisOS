"""10.1: recurring charges, cash flow to the next pay day, and plan suggestions, from the bank imports."""

from __future__ import annotations

import copy
from datetime import date, datetime, timedelta

import pytest

from app.budget import actuals, forecast
from app.budget import service as budget
from tests.test_budget import PLAN, client  # noqa: F401  (fixture)
from tests.test_hub import AUTH

TODAY = date(2026, 11, 19)


@pytest.fixture
def c(client, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setenv("SIRISOS_BUDGET_ACTUALS_PATH", str(tmp_path / "budget-actuals.json"))
    monkeypatch.setattr(budget, "today", lambda: TODAY)
    plan = copy.deepcopy(PLAN)
    plan["income"][0]["pay_day"] = "2026-11-27"  # fortnightly, next on Friday week
    plan["sections"]["expenses"].append({"name": "Subscriptions", "amount": 30, "every": "monthly"})
    assert client.put("/api/v1/budget", json=plan, headers=AUTH).status_code == 200
    return client


def _tx(d: date, desc: str, amount: float, **kw) -> dict:
    return {"id": f"{d.isoformat()}{desc[:6]}{amount}".replace(" ", "").replace(".", "").replace("-", "")[:30],
            "date": d.isoformat(), "description": desc, "amount": amount, "account": "Everyday", **kw}


def _seed(txs: list[dict], balance: float | None = 1500.0) -> None:
    doc = actuals.load()
    doc["transactions"] = txs
    actuals.save(doc)
    if balance is not None:
        actuals.set_balance("Everyday", balance, TODAY, kind="everyday")


def _history() -> list[dict]:
    """Three months: Netflix monthly (price up last time), the gym fortnightly, groceries most days, and pay."""
    out = []
    for i, d in enumerate([date(2026, 8, 22), date(2026, 9, 22), date(2026, 10, 22)]):
        out.append(_tx(d, "NETFLIX.COM MELBOURNE", -22.99 if i < 2 else -25.99))
    gym = date(2026, 8, 20)
    while gym < TODAY:
        out.append(_tx(gym, "ANYTIME FITNESS RICHMOND", -32.0))
        gym += timedelta(days=14)
    d = date(2026, 8, 20)
    k = 0
    while d < TODAY:
        if d.weekday() in (1, 4):
            out.append(_tx(d, f"WOOLWORTHS {1000 + k} MELBOURNE", -(115.0 + (k % 3) * 10)))
            k += 1
        d += timedelta(days=1)
    out.append(_tx(date(2026, 11, 13), "SALARY ACME", 3000.0))
    return out


def test_recurring_finds_steady_charges_and_flags_them(c):
    _seed(_history())
    r = c.get("/api/v1/budget/recurring", headers=AUTH).json()
    by = {i["key"]: i for i in r["items"]}
    assert set(by) == {"netflix.com melbourne", "anytime fitness"}  # groceries vary in amount and day: not a fixed charge
    nf = by["netflix.com melbourne"]
    assert nf["every"] == "monthly" and nf["next"] == "2026-11-21" and nf["amount"] == 25.99 and nf["was"] == 22.99
    assert set(nf["flags"]) == {"price_up", "not_in_budget", "check"}
    gym = by["anytime fitness"]
    assert gym["every"] == "fortnightly" and "check" not in gym["flags"]
    # Keeping Netflix clears "check"; ignoring a charge clears its flags and leaves it out of the total.
    r = c.put(f"/api/v1/budget/recurring/{nf['id']}", json={"status": "keep"}, headers=AUTH).json()
    assert "check" not in next(i for i in r["items"] if i["id"] == nf["id"])["flags"]
    r = c.put(f"/api/v1/budget/recurring/{gym['id']}", json={"status": "ignore"}, headers=AUTH).json()
    assert next(i for i in r["items"] if i["id"] == gym["id"])["flags"] == []
    assert r["per_month"] == pytest.approx(25.99 * 30.44 / 30, abs=0.01)
    assert c.put("/api/v1/budget/recurring/abcdef123456", json={"status": "keep"}, headers=AUTH).status_code == 404
    assert c.put(f"/api/v1/budget/recurring/{gym['id']}", json={"status": "delete"}, headers=AUTH).status_code == 422


def test_cashflow_runs_to_after_pay_and_finds_the_low_point(c):
    _seed(_history(), balance=400.0)
    cf = c.get("/api/v1/budget/cashflow", headers=AUTH).json()
    assert cf["ready"] and cf["start"] == 400.0 and cf["next_pay"] == "2026-11-27"
    assert cf["days"][0]["date"] == "2026-11-19" and cf["days"][-1]["date"] >= "2026-12-03"
    assert "last" in cf["basis"]  # from the imports, not the plan
    names = {b["name"][:7] for b in cf["bills"]}
    assert {"NETFLIX", "ANYTIME"} <= names
    # The low point is the day before pay, and with ~$29 a day going out from $400 it's under the $200 mark.
    assert cf["low"]["date"] == "2026-11-26" and cf["warn"]
    pay_day = next(d for d in cf["days"] if d["date"] == "2026-11-27")
    assert any(e["amount"] == 3000 for e in pay_day["events"])
    msgs = forecast.push_message(datetime(2026, 11, 19, 9, 5))
    assert msgs and msgs[0]["key"] == "cashflow:low:2026-11-26" and "before pay on Fri 27 Nov" in msgs[0]["body"]
    assert forecast.push_message(datetime(2026, 11, 19, 8, 0)) == []


def test_cashflow_needs_an_everyday_balance(c):
    _seed(_history(), balance=None)
    cf = c.get("/api/v1/budget/cashflow", headers=AUTH).json()
    assert cf["ready"] is False and "everyday" in cf["why"]


def test_suggestions_after_two_full_months(c):
    ids = {l["name"]: l["id"] for s in c.get("/api/v1/budget", headers=AUTH).json()["sections"].values() for l in s}
    txs = _history()
    for t in txs:
        if t["description"].startswith("WOOLWORTHS"):
            t["line_id"] = ids["Groceries"]
    _seed(txs)
    s = c.get("/api/v1/budget/suggestions", headers=AUTH).json()
    assert s["ready"] and s["months"] == ["2026-09", "2026-10"]
    g = next(i for i in s["items"] if i["name"] == "Groceries")
    # About 9 shops a month at ~$125 (~$1,100) against 200 a week (~$867): raise it, as a weekly amount.
    assert g["kind"] == "raise" and g["every"] == "weekly" and g["average"] > g["plan"]
    assert g["amount"] == round(g["monthly"] / (52 / 12))
    assert g["where"][0]["shop"].startswith("Woolworths")
    # Rent has nothing sorted on it (paid another way), so it isn't told to go down to nothing.
    assert not any(i["name"] in ("Rent", "Rego") for i in s["items"])


def test_suggestions_wait_for_two_months(c):
    _seed([_tx(date(2026, 11, 2), "WOOLWORTHS 1 MELBOURNE", -50.0)])
    s = c.get("/api/v1/budget/suggestions", headers=AUTH).json()
    assert s["ready"] is False and s["items"] == []
