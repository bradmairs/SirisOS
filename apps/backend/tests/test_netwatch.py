"""5.3: network alerts: new devices, important ones offline, Trust and Block."""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.netwatch import service
from app.push import actions
from tests.test_hub import AUTH, ENV

blocked: list[tuple[str, dict]] = []
NODES = [
    {"id": "aa:00", "name": "UCG Ultra", "kind": "gateway", "online": True},
    {"id": "bb:01", "name": "Synology NAS", "kind": "client", "online": True},
    {"id": "bb:02", "name": "Brad's iPhone", "kind": "client", "online": True},
]


def handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/block"):
        blocked.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"id": request.url.path.split("/")[-2], "blocked": json.loads(request.content)["blocked"]})
    if request.url.path == "/siris/hub/v1/network":
        return httpx.Response(200, json={"configured": True, "guest_mode": False, "checked_at": "", "wan": None, "nodes": NODES})
    return httpx.Response(404)


@pytest.fixture
def client(monkeypatch, tmp_path):
    for env, name in (("SIRISOS_NETWATCH_PATH", "n.json"), ("SIRISOS_PUSH_ACTIONS_PATH", "used.json")):
        monkeypatch.setenv(env, str(tmp_path / name))
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    blocked.clear()
    reset_hub(ENV)
    return TestClient(app)


def test_baseline_then_new_devices_and_important_ones_offline(client):
    doc = service.load()
    assert service.observe(doc, NODES, 1000) == []  # the first look is the baseline
    newcomer = {"id": "cc:09", "name": "espressif", "kind": "client", "online": True, "wired": False}
    alerts = service.observe(doc, [*NODES, newcomer], 1100)
    assert [a["key"] for a in alerts] == ["net:new:cc:09"]
    assert alerts[0]["topic"] == "home" and [b["id"] for b in alerts[0]["actions"]] == ["trust", "block"]
    # The NAS goes, and the iPhone leaves the house: only the NAS matters, after 10 minutes.
    rest = [NODES[0], newcomer]
    assert service.observe(doc, rest, 1200) == []
    late = service.observe(doc, rest, 1200 + 600)
    assert [a["key"] for a in late] == ["net:offline:bb:01:1200"] and late[0]["title"] == "Synology NAS is offline"
    # Back again: the outage is over.
    service.observe(doc, [*NODES, newcomer], 1900)
    assert "bb:01" not in doc["missing_since"]


def test_checks_every_two_minutes_through_sirisai(client):
    hub = hub_service.get_hub()
    import asyncio

    assert asyncio.run(service.check(hub, now=10_000)) == []
    assert service.load()["baseline"] is True
    assert asyncio.run(service.check(hub, now=10_060)) == [] and service.load()["checked"] == 10_000


def test_view_trust_star_and_block(client):
    service.observe(doc := service.load(), NODES, 1000)
    service.observe(doc, [*NODES, {"id": "cc:09", "name": "espressif", "kind": "client"}], 1100)
    service.save(doc)
    devices = {d["id"]: d for d in client.get("/api/v1/netwatch", headers=AUTH).json()["devices"]}
    assert devices["cc:09"]["trusted"] is False and devices["bb:01"]["important"] is True and devices["bb:02"]["important"] is False
    assert next(iter(client.get("/api/v1/netwatch", headers=AUTH).json()["devices"]))["id"] == "cc:09"  # undecided first
    client.post("/api/v1/netwatch/bb:02/important", headers=AUTH, json={"important": True})
    r = client.post("/api/v1/netwatch/cc:09/block", headers=AUTH, json={"blocked": True})
    d = {x["id"]: x for x in r.json()["devices"]}
    assert d["cc:09"]["blocked"] and d["cc:09"]["trusted"] and d["bb:02"]["important"]
    assert blocked == [("/siris/hub/v1/network/cc:09/block", {"blocked": True})]
    assert client.post("/api/v1/netwatch/zz/trust", headers=AUTH).status_code == 404


def test_notification_buttons(client):
    service.observe(doc := service.load(), NODES, 1000)
    alert = service.observe(doc, [*NODES, {"id": "cc:09", "name": "espressif", "kind": "client"}], 1100)[0]
    service.save(doc)
    t = actions.sign(alert["target"], alert["actions"], alert["title"], alert["body"], alert["url"])
    r = client.post("/api/v1/push/act", json={"token": t, "action": "block"})
    assert r.status_code == 200 and r.json()["message"].startswith("Blocked.")
    assert blocked[-1] == ("/siris/hub/v1/network/cc:09/block", {"blocked": True})
