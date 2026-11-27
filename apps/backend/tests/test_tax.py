"""11.18: tax-claimable receipts, by Australian financial year, with the ATO's rules."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.tax import service
from tests.test_hub import AUTH, ENV

RECEIPTS = [
    {"id": 7, "added_at": "2026-11-03T09:00:00", "title": "Order: 27in monitor", "sender": "Officeworks", "summary": "Officeworks, 3 Nov 2026, $1,249.00", "kind": "receipt"},
    {"id": 8, "added_at": "2026-10-01T09:00:00", "title": "Membership renewal", "sender": "Engineers Australia", "summary": "Total A$ 512.50", "kind": "receipt"},
    {"id": 9, "added_at": "2026-05-01T09:00:00", "title": "Shoes", "sender": "The Iconic", "summary": "$120", "kind": "receipt"},  # last year
]


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_TAX_PATH", str(tmp_path / "tax.json"))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/siris/documents" and request.url.params.get("kind") == "receipt":
            return httpx.Response(200, json=RECEIPTS)
        return httpx.Response(404)

    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    reset_hub(ENV)
    return TestClient(app, headers=AUTH)


def test_financial_years_end_on_30_june():
    assert service.fy_of("2026-06-30") == 2026 and service.fy_of("2026-07-01") == 2027 and service.fy_label(2027) == "2026-27"
    assert service.amount_in("JB Hi-Fi, 20 Oct 2026, $899.00") == 899.0 and service.amount_in("Total A$ 1,512.50 inc GST") == 1512.5
    assert service.amount_in("no money here") is None


def test_receipts_from_email_wait_to_be_sorted_with_a_guess(client):
    y = client.get("/api/v1/tax?fy=2027").json()
    assert y["label"] == "2026-27" and [r["doc_id"] for r in y["to_sort"]] == [7, 8]   # last year's shoes aren't in this year
    assert y["to_sort"][0] == {"doc_id": 7, "date": "2026-11-03", "vendor": "Officeworks", "description": "Order: 27in monitor", "amount": 1249.0, "category": "equipment"}
    assert y["to_sort"][1]["category"] == "professional" and y["to_sort"][1]["amount"] == 512.5
    client.post("/api/v1/tax/not-tax/8")
    client.post("/api/v1/tax/claims", json={"doc_id": 7, "date": "2026-11-03", "vendor": "Officeworks", "description": "Monitor", "amount": 1249, "category": "equipment", "work_pct": 80})
    y = client.get("/api/v1/tax?fy=2027").json()
    assert y["to_sort"] == []
    [monitor] = y["claims"]
    # Over $300: depreciated over its life, so not in this year's total.
    assert monitor["source"] == "email" and monitor["has_receipt"] and monitor["treatment"] == "depreciate" and y["total"] == 0
    assert any("over $300 to depreciate" in c["text"] for c in y["checks"])


def test_the_300_dollar_rule_and_the_work_share(client):
    add = lambda **kw: client.post("/api/v1/tax/claims", json={"date": "2026-08-01", "vendor": "Shop", "category": "other-work", **kw})  # noqa: E731
    assert add(amount=100, work_pct=50, has_receipt=False).status_code == 200
    assert add(amount=80, category="clothing", has_receipt=False).status_code == 200
    y = client.get("/api/v1/tax?fy=2027").json()
    assert y["work_total"] == 130.0 and y["checks"][0]["level"] == "ok"      # under $300: no receipts needed
    add(amount=200, category="equipment", has_receipt=True)                   # $300 or less: deducted in full
    add(amount=60, category="travel", reimbursed=True)                        # reimbursed: nothing
    y = client.get("/api/v1/tax?fy=2027").json()
    assert y["work_total"] == 330.0 and len(y["missing_receipts"]) == 2
    assert y["checks"][0]["level"] == "warn" and "2 have no receipt yet" in y["checks"][0]["text"]
    assert next(c for c in y["claims"] if c.get("reimbursed"))["claimable"] == 0


def test_working_from_home_and_the_car(client):
    client.put("/api/v1/tax/years/2027", json={"wfh_hours": 400, "car_km": 6000})
    client.post("/api/v1/tax/claims", json={"date": "2026-09-01", "vendor": "Telco", "amount": 70, "category": "phone-internet", "has_receipt": True})
    y = client.get("/api/v1/tax?fy=2027").json()
    assert y["wfh"]["claimable"] == 280.0 and y["car"]["claimable"] == 4400.0     # 400 h at 70c; capped at 5,000 km at 88c
    texts = " ".join(c["text"] for c in y["checks"])
    assert "counted twice" in texts and "capped at 5,000 km" in texts and "actual hours" in texts
    csv = client.get("/api/v1/tax/export?fy=2027")
    assert csv.status_code == 200 and "Tax claims 2026-27.csv" in csv.headers["content-disposition"]
    assert "Working from home: 400 hours at 70c" in csv.text and "Telco" in csv.text


def test_bad_claims_are_refused_and_claims_change(client):
    assert client.post("/api/v1/tax/claims", json={"date": "x", "vendor": "A", "amount": 5}).status_code == 422
    assert client.post("/api/v1/tax/claims", json={"date": "2026-08-01", "vendor": "A", "amount": 0}).status_code == 422
    c = client.post("/api/v1/tax/claims", json={"date": "2026-08-01", "vendor": "A", "amount": 5, "category": "donation"}).json()
    assert client.put(f"/api/v1/tax/claims/{c['id']}", json={"amount": 1.5}).json()["amount"] == 1.5
    y = client.get("/api/v1/tax?fy=2027").json()
    assert y["claims"][0]["claimable"] == 0 and "under $2" in y["claims"][0]["treatment_note"]
    assert client.delete(f"/api/v1/tax/claims/{c['id']}").json() == {"ok": True}
    assert client.delete(f"/api/v1/tax/claims/{c['id']}").status_code == 404


def test_email_being_down_still_shows_the_year(client, monkeypatch):
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(lambda r: httpx.Response(500)))
    reset_hub(ENV)
    y = client.get("/api/v1/tax?fy=2027").json()
    assert y["to_sort"] == [] and y["email_problem"]
