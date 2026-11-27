"""11.16: Apple Pay taps into the budget, from an iPhone Shortcuts automation."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.budget import actuals, taps
from app.entrypoint import app
from tests.test_hub import AUTH

BUDGET = {"currency": "AUD", "income": [{"id": "pay", "name": "Pay", "amount": 5000, "every": "monthly"}],
          "sections": {"expenses": [], "savings": [], "spending": [{"id": "groc", "name": "Groceries", "amount": 800, "every": "monthly"},
                                                                    {"id": "fuel", "name": "Fuel", "amount": 300, "every": "monthly"}]}}


@pytest.fixture
def client(monkeypatch, tmp_path):
    for env, name in (("SIRISOS_BUDGET_PATH", "budget.json"), ("SIRISOS_BUDGET_ACTUALS_PATH", "budget-actuals.json"),
                      ("SIRISOS_BUDGET_TAPS_PATH", "budget-taps.json")):
        monkeypatch.setenv(env, str(tmp_path / name))
    c = TestClient(app, headers=AUTH)
    c.put("/api/v1/budget", json=BUDGET)
    return c


def test_a_tap_goes_on_the_right_line_with_its_own_key(client, tmp_path):
    key = client.post("/api/v1/budget/tap-key").json()["key"]
    assert key.startswith("pay_") and key not in (tmp_path / "budget-taps.json").read_text()
    bare = TestClient(app)
    assert bare.post("/api/v1/budget-tap", json={"merchant": "Woolworths", "amount": "$12.50"}).status_code == 401
    got = bare.post("/api/v1/budget-tap", json={"merchant": "WOOLWORTHS 1234 MELBOURNE", "amount": "$12.50", "card": "CommBank Debit"},
                    headers={"X-SirisOS-Key": key}).json()
    assert got["logged"] and got["line"] == "Groceries" and got["say"] == "Logged $12.50 at WOOLWORTHS 1234 MELBOURNE on Groceries."
    tx = actuals.load()["transactions"][-1]
    assert tx["amount"] == -12.5 and tx["manual"] and tx["account"] == "Apple Pay · CommBank Debit" and tx["line_id"] == "groc"
    assert bare.get("/api/v1/budget", headers={"X-SirisOS-Key": key}).status_code == 401  # the key opens nothing else
    s = client.get("/api/v1/budget/tap-key").json()
    assert s["on"] and s["taps"] == 1 and s["spent"] == 12.5 and s["unsorted"] == 0


def test_the_automation_firing_twice_is_one_spend(client):
    taps.new_key()
    assert taps.add("Shell Coles Express", "65.00")["logged"]
    assert not taps.add("Shell Coles Express", 65)["logged"]
    assert len(actuals.load()["transactions"]) == 1


def test_amounts_as_the_shortcut_sends_them():
    assert taps.amount_of("$12.50") == 12.5 and taps.amount_of("A$1,234.56") == 1234.56 and taps.amount_of("12,50") == 12.5
    assert taps.amount_of(7) == 7 and taps.amount_of("") is None and taps.amount_of("free") is None
    with pytest.raises(ValueError):
        taps.add("", "5")


def test_the_netbank_csv_replaces_the_tap_so_nothing_counts_twice(client):
    taps.new_key()
    taps.add("BUNNINGS 5551 HAWTHORN", "42.00", now=datetime(2026, 11, 20, 10, 0))
    csv = b"20/11/2026,-42.00,BUNNINGS 5551 HAWTHORN VIC AUS Card xx1234 Value Date: 19/11/2026,+1000.00\n"
    out = client.post("/api/v1/budget/actuals/import", files={"file": ("CSVData.csv", csv, "text/csv")}, data={"account": "Everyday"}).json()
    assert out["imported"] == 1 and out["replaced_by_hand"] == 1
    assert [t["account"] for t in actuals.load()["transactions"]] == ["Everyday"]
