"""Life admin from SirisAI 4.6 (SirisOS 7.3): documents, bills, trips,
conversation search and reply speed are passed through as they are."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from tests.test_hub import AUTH, ENV


@pytest.fixture
def seen():
    return []


@pytest.fixture
def client(monkeypatch, seen):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        seen.append((request.method, path, dict(request.url.params), request.content))
        if path == "/siris/documents" and request.method == "POST":
            if b"zip" in request.content[:400]:
                return httpx.Response(422, json={"detail": "Send a PDF, a photo (JPEG or PNG) or a text file."})
            return httpx.Response(200, json={"id": 7, "title": "Rates notice", "due": [{"date": "2026-11-20", "what": "pay", "amount": 412.5}], "reminders": 2})
        if path == "/siris/documents":
            return httpx.Response(200, json=[{"id": 7, "title": "Rates notice"}])
        if path == "/siris/documents/7":
            return httpx.Response(200, json={"deleted": 7} if request.method == "DELETE" else {"id": 7, "text": "..."})
        if path == "/siris/documents/8":
            return httpx.Response(404, json={"detail": "No such document"})
        if path == "/siris/bills":
            return httpx.Response(200, json=[{"id": 1, "label": "Netflix renews Mon 9 Nov for $22.99"}])
        if path == "/siris/bills/1/status":
            return httpx.Response(200, json={"id": 1, "status": json.loads(request.content)["status"]})
        if path == "/siris/travel":
            return httpx.Response(200, json=[{"destination": "Sydney", "nights": 3, "packing": ["Sunscreen"], "house": [], "weather": []}])
        if path == "/siris/travel/away":
            return httpx.Response(200, json={"away_mode": "automatic", "until": "2026-11-11"})
        if path == "/siris/timings":
            return httpx.Response(200, json={"stages": {"total": {"p50_ms": 900, "p95_ms": 2400, "count": 40}}, "recent": []})
        if path == "/siris/scheduler/jobs":
            return httpx.Response(200, json=[{"name": "reminders", "runs": 12, "last_seconds": 0.01, "running": False}])
        if path == "/siris/things":
            return httpx.Response(200, json={"id": 4, **json.loads(request.content)} if request.method == "POST" else [{"id": 4, "name": "TV"}])
        if path == "/siris/people/2/gifts":
            return httpx.Response(200, json={"ideas": ["coffee"], "last_seen": {"text": "6 days ago"}})
        if path == "/siris/people":
            return httpx.Response(200, json=[{"id": 2, "name": "Sam", "days_to_birthday": 5}])
        if path == "/siris/news":
            return httpx.Response(200, json={"stories": [{"title": "A"}], "episodes": [], "overnight": []})
        if path == "/siris/conversations/search":
            return httpx.Response(200, json=[{"conversation_id": "c1", "title": "NAS backups", "summary": "Nightly at 2am."}])
        return httpx.Response(404)

    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    reset_hub(ENV)
    return TestClient(app)


def test_documents_go_to_sirisai(client, seen):
    r = client.post("/api/v1/life/documents", headers=AUTH, files={"file": ("rates.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code == 200 and r.json()["reminders"] == 2
    assert seen[-1][0:2] == ("POST", "/siris/documents") and b"rates.pdf" in seen[-1][3]
    bad = client.post("/api/v1/life/documents", headers=AUTH, files={"file": ("x.zip", b"PK", "application/zip")})
    assert bad.status_code == 422 and "PDF" in bad.json()["detail"]
    assert client.get("/api/v1/life/documents", params={"q": "rates"}, headers=AUTH).json()[0]["id"] == 7
    assert seen[-1][2] == {"q": "rates"}
    assert client.delete("/api/v1/life/documents/7", headers=AUTH).json() == {"deleted": 7}
    assert client.get("/api/v1/life/documents/8", headers=AUTH).status_code == 404


def test_bills_and_travel(client, seen):
    assert client.get("/api/v1/life/bills", headers=AUTH).json()[0]["label"].startswith("Netflix")
    assert client.post("/api/v1/life/bills/1/status", json={"status": "done"}, headers=AUTH).json()["status"] == "done"
    assert client.post("/api/v1/life/bills/1/status", json={"status": "paid"}, headers=AUTH).status_code == 422
    assert client.get("/api/v1/life/travel", headers=AUTH).json()[0]["destination"] == "Sydney"
    assert client.post("/api/v1/life/travel/away", headers=AUTH).json()["away_mode"] == "automatic"
    assert seen[-1][2] == {"on": "true"}


def test_speed_and_conversation_search(client, seen):
    speed = client.get("/api/v1/life/speed", headers=AUTH).json()
    assert speed["timings"]["stages"]["total"]["p50_ms"] == 900 and speed["jobs"][0]["name"] == "reminders"
    found = client.get("/api/v1/assistant/conversations/search", params={"q": "nas", "since": "2026-11-01"}, headers=AUTH)
    assert found.json()[0]["title"] == "NAS backups" and seen[-1][2] == {"q": "nas", "since": "2026-11-01"}
    assert client.get("/api/v1/assistant/conversations/search", params={"since": "yesterday"}, headers=AUTH).status_code == 422


def test_needs_sign_in(client):
    assert client.get("/api/v1/life/bills").status_code == 401


def test_things_people_and_news(client, seen):
    assert client.get("/api/v1/life/things", headers=AUTH).json() == [{"id": 4, "name": "TV"}]
    assert client.post("/api/v1/life/things", json={"name": "Fridge", "warranty_months": 24}, headers=AUTH).json()["name"] == "Fridge"
    assert client.get("/api/v1/life/people", headers=AUTH).json()[0]["days_to_birthday"] == 5
    assert client.get("/api/v1/life/people/2/gifts", headers=AUTH).json()["ideas"] == ["coffee"]
    assert client.get("/api/v1/life/news", headers=AUTH).json()["stories"][0]["title"] == "A"
