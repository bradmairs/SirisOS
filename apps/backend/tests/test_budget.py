"""The budget (7.6): saved whole, cleaned, totalled per month, with a monthly
history; subscriptions from SirisAI's bills become expense lines."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from tests.test_hub import AUTH, ENV

PLAN = {
    "currency": "aud",
    "income": [{"name": "Salary", "amount": 3000, "every": "fortnightly"}],
    "sections": {
        "expenses": [{"name": "Rent", "amount": 2000, "every": "monthly"}, {"name": "Rego", "amount": 900, "every": "yearly"}],
        "savings": [{"name": "Holiday", "amount": 500, "every": "monthly", "goal": 6000, "saved": 1000}],
        "spending": [{"name": "Groceries", "amount": 200, "every": "weekly"}],
    },
}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_BUDGET_PATH", str(tmp_path / "budget.json"))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/siris/bills":
            return httpx.Response(200, json=[
                {"service": "Netflix", "amount": 22.99, "subject": "Your membership", "status": "open", "label": "Netflix renews"},
                {"service": "Netflix", "amount": 22.99, "subject": "Again", "status": "open"},
                {"service": "Gym", "amount": 600, "subject": "Annual renewal", "status": "open"},
                {"service": "Spam", "amount": 5, "subject": "", "status": "ignored"},
                {"service": "NoAmount", "amount": None, "subject": "", "status": "open"},
            ])
        return httpx.Response(404)

    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    reset_hub(ENV)
    return TestClient(app)


def test_empty_then_saved_with_totals_and_history(client):
    empty = client.get("/api/v1/budget", headers=AUTH).json()
    assert empty["totals"] == {"income": 0, "expenses": 0, "savings": 0, "spending": 0, "left": 0}
    saved = client.put("/api/v1/budget", json=PLAN, headers=AUTH).json()
    assert saved["currency"] == "AUD"
    assert saved["totals"] == {"income": 6500.0, "expenses": 2075.0, "savings": 500.0, "spending": 866.67, "left": 3058.33}
    assert all(line["id"] for line in saved["income"])
    assert saved["sections"]["savings"][0]["goal"] == 6000
    assert len(saved["history"]) == 1 and saved["history"][0]["income"] == 6500
    again = client.put("/api/v1/budget", json=PLAN, headers=AUTH).json()
    assert len(again["history"]) == 1  # one entry per month
    assert client.get("/api/v1/budget", headers=AUTH).json()["totals"]["left"] == 3058.33


def test_bad_lines_are_refused(client):
    bad = {**PLAN, "income": [{"name": "Salary", "amount": -5, "every": "monthly"}]}
    assert client.put("/api/v1/budget", json=bad, headers=AUTH).status_code == 422
    odd = {**PLAN, "income": [{"name": "Salary", "amount": 5, "every": "daily"}]}
    assert client.put("/api/v1/budget", json=odd, headers=AUTH).status_code == 422


def test_bills_become_expense_lines(client):
    lines = client.get("/api/v1/budget/from-bills", headers=AUTH).json()
    assert lines == [
        {"name": "Netflix", "amount": 22.99, "every": "monthly", "note": "Netflix renews"},
        {"name": "Gym", "amount": 600, "every": "yearly", "note": ""},
    ]


def test_needs_sign_in(client):
    assert client.get("/api/v1/budget").status_code == 401
