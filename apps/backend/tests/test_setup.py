"""5.6: the setup checklist on System status."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from tests.test_hub import AUTH, ENV

STATE: dict = {}


def handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/siris/hub/v1":
        return httpx.Response(200, json={"user": "brad", "guest_mode": False, "features": {}})
    if path == "/siris/hub/v1/controls":
        return httpx.Response(200, json={"configured": True, "guest_mode": False, "controls": [{"entity_id": "light.k"}], "scenes": []})
    if path == "/siris/hub/v1/network":
        return httpx.Response(200, json={"configured": False, "guest_mode": False, "checked_at": "", "nodes": []})
    if path == "/siris/hub/v1/energy/usage":
        return httpx.Response(404) if STATE.get("old") else httpx.Response(200, json={"configured": True, "power": [{"entity_id": "sensor.p", "name": "P", "watts": 3}], "meters": [], "house_watts": None, "house_meter": None})
    if path == "/siris/hub/v1/health/days":
        return httpx.Response(200, json={"guest_mode": False, "days": []})
    return httpx.Response(404)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_DATA_DIR", str(tmp_path))
    for env in ("SIRISOS_SERVICE_KEY", "SIRISOS_TERMINAL_HOSTS", "SIRISOS_PUSH_SUBSCRIPTIONS_PATH", "SIRISOS_CAREER_PATH",
                "SIRISOS_HEALTH_IMPORT_PATH", "SIRISOS_BACKUP_PATH"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("SIRISOS_CAREER_PATH", str(tmp_path / "career.json"))
    monkeypatch.setenv("SIRISOS_BACKUP_PATH", str(tmp_path / "backups"))
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    STATE.clear()
    reset_hub(ENV)
    return TestClient(app)


def test_every_check_says_on_off_or_problem_with_a_fix(client):
    body = client.get("/api/v1/setup", headers=AUTH).json()
    items = {i["id"]: i for i in body["items"]}
    assert items["sirisai"]["state"] == "on"
    assert items["home-assistant"]["state"] == "on" and items["unifi"]["state"] == "off"
    assert items["unifi"]["settings"] == ["SIRISAI_UNIFI_BASE_URL", "SIRISAI_UNIFI_API_KEY"]
    assert items["power"]["state"] == "on" and "SIRISAI_ENERGY_METER_ENTITY_ID" in items["power"]["settings"]
    assert items["health"]["state"] == "off" and items["health"]["link"] == "/training#health"
    assert items["push"]["state"] == "off" and items["cpd"]["state"] == "off"
    assert items["service-key"]["state"] == "off" and items["terminal"]["state"] == "off"
    assert all(i["state"] in ("on", "off", "problem") for i in body["items"])
    assert all(i["fix"] for i in body["items"] if i["state"] != "on" and i["id"] != "backups")
    assert sum(body["counts"].values()) == len(body["items"])


def test_an_old_sirisai_and_a_short_key_are_problems(client, monkeypatch):
    STATE["old"] = True
    monkeypatch.setenv("SIRISOS_SERVICE_KEY", "short")
    items = {i["id"]: i for i in client.get("/api/v1/setup", headers=AUTH).json()["items"]}
    assert items["power"]["state"] == "off" and "3.11" in items["power"]["detail"]
    assert items["service-key"]["state"] == "problem"


def test_a_health_key_with_nothing_arriving_is_a_problem(client):
    from app.training import health_import

    health_import.new_key()
    items = {i["id"]: i for i in client.get("/api/v1/setup", headers=AUTH).json()["items"]}
    assert items["health"]["state"] == "problem" and "Health Auto Export" in items["health"]["fix"]
