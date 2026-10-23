"""4.2: Home controls, relayed to SirisAI 2.36."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from tests.test_hub import AUTH, ENV

seen: list[tuple[str, str, dict | None]] = []
CONTROLS = {"configured": True, "guest_mode": False, "controls": [
    {"entity_id": "cover.garage_door", "name": "Garage door", "kind": "garage", "state": "closed", "brightness_pct": None, "confirm": "Open Garage door?"},
    {"entity_id": "light.kitchen", "name": "Kitchen", "kind": "light", "state": "on", "brightness_pct": 50, "confirm": None}],
    "scenes": [{"id": "siris:3", "name": "Wind down", "source": "siris"}]}


def handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content) if request.content else None
    seen.append((request.method, request.url.path, body))
    if request.url.path == "/siris/hub/v1/controls":
        return httpx.Response(200, json=CONTROLS)
    if request.url.path == "/siris/hub/v1/controls/cover.garage_door":
        if not body["confirmed"]:
            return httpx.Response(409, json={"detail": "Garage doors needs a yes first."})
        return httpx.Response(200, json={"entity_id": "cover.garage_door", "action": body["action"], "state": "open"})
    if request.url.path.startswith("/siris/hub/v1/scenes/"):
        return httpx.Response(200, json={"entity_id": request.url.path.split("/")[-2], "action": "run", "state": None})
    return httpx.Response(404)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    seen.clear()
    reset_hub(ENV)
    yield TestClient(app)


def test_controls_relay(client):
    assert client.get("/api/v1/assistant/controls", headers=AUTH).json()["controls"][1]["name"] == "Kitchen"
    held = client.post("/api/v1/assistant/controls/cover.garage_door", headers=AUTH, json={"action": "open"})
    assert held.status_code == 409 and "yes first" in held.json()["detail"]
    ok = client.post("/api/v1/assistant/controls/cover.garage_door", headers=AUTH, json={"action": "open", "confirmed": True})
    assert ok.json()["state"] == "open" and seen[-1] == ("POST", "/siris/hub/v1/controls/cover.garage_door", {"action": "open", "confirmed": True})
    assert client.post("/api/v1/assistant/scenes/siris:3/run", headers=AUTH).json()["action"] == "run"


def test_only_plain_ids_and_known_actions_get_through(client):
    assert client.post("/api/v1/assistant/controls/..%2Fprotocols", headers=AUTH, json={"action": "toggle"}).status_code in (404, 422)
    assert client.post("/api/v1/assistant/controls/light.kitchen", headers=AUTH, json={"action": "explode"}).status_code == 422
    assert client.post("/api/v1/assistant/scenes/script.evil/run", headers=AUTH).status_code == 422
    assert client.get("/api/v1/assistant/controls").status_code == 401
    assert not any("protocols" in p for _, p, _ in seen)
