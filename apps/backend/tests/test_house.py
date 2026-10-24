"""4.5: the house: device placements, and the live network relayed from SirisAI."""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from tests.test_hub import AUTH, ENV

NETWORK = {"configured": True, "guest_mode": False, "checked_at": "2026-10-24T10:00:00+00:00", "wan": {"rx_bps": 1000, "tx_bps": 10, "isp": "ABB"},
           "nodes": [{"id": "aa:00", "name": "Cloud Gateway Ultra", "kind": "gateway", "model": "UCGULTRA", "wired": None, "online": True, "uplink": None, "rx_bps": 1, "tx_bps": 1}]}


def test_placements_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_HOUSE_PATH", str(tmp_path / "house.json"))
    client = TestClient(app)
    assert client.get("/api/v1/house/placements").status_code == 401
    assert client.get("/api/v1/house/placements", headers=AUTH).json() == {"placements": {}}
    body = {"placements": {"aa:00": {"room": "office"}, "light.kitchen": {"room": "kitchen", "x": 2.5, "z": 1.0}, "bb:09": {"room": "garage", "hidden": True}}}
    saved = client.put("/api/v1/house/placements", headers=AUTH, json=body).json()
    assert saved["placements"]["aa:00"] == {"room": "office", "hidden": False}
    assert client.get("/api/v1/house/placements", headers=AUTH).json() == saved
    assert client.put("/api/v1/house/placements", headers=AUTH, json={"placements": {"x": {"room": ""}}}).status_code == 422


def test_network_is_relayed(monkeypatch):
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(lambda r: httpx.Response(200, json=NETWORK) if r.url.path == "/siris/hub/v1/network" else httpx.Response(404)))
    reset_hub(ENV)
    assert TestClient(app).get("/api/v1/assistant/network", headers=AUTH).json()["nodes"][0]["name"] == "Cloud Gateway Ultra"
