"""5.4: power use: today's kWh from meters or power, the live view, Your year."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.power import service
from tests.test_hub import AUTH, ENV

DAY = date(2026, 10, 30)
USAGE = {"configured": True, "house_watts": 1250.0, "solar_watts": None, "house_meter": None,
         "power": [{"entity_id": "sensor.dishwasher_power", "name": "Dishwasher power", "watts": 1800}],
         "meters": []}


def handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/siris/hub/v1/energy/usage":
        return httpx.Response(200, json=USAGE)
    return httpx.Response(404)


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_POWER_PATH", str(tmp_path / "p.json"))
    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    reset_hub(ENV)


def test_house_meter_wins_and_a_reset_is_not_negative(setup):
    doc = service.load()
    u = {**USAGE, "house_meter": "sensor.house_energy",
         "meters": [{"entity_id": "sensor.house_energy", "kwh": 1000.0}, {"entity_id": "sensor.plug", "kwh": 5.0}]}
    service.record(doc, u, DAY, 0)
    u["meters"][0]["kwh"] = 1008.5
    assert service.record(doc, u, DAY, 600)["kwh"] == 8.5
    u["meters"][0]["kwh"] = 2.0  # the meter was replaced
    service.record(doc, u, DAY, 1200)
    u["meters"][0]["kwh"] = 3.0
    day = service.record(doc, u, DAY, 1800)
    assert day["kwh"] == 9.5 and day["method"] == "house meter"


def test_without_meters_the_power_is_integrated(setup):
    doc = service.load()
    service.record(doc, {**USAGE, "house_watts": 1000.0}, DAY, 0)
    assert service.record(doc, {**USAGE, "house_watts": 3000.0}, DAY, 1800)["kwh"] == 1.0  # 2 kW average for half an hour
    # A long gap isn't guessed.
    assert service.record(doc, {**USAGE, "house_watts": 3000.0}, DAY, 1800 + 7200)["kwh"] == 1.0
    no_house = {**USAGE, "house_watts": None}
    other = service.record(doc, no_house, date(2026, 10, 31), 0)
    assert other["watts"] == 1800 and other["method"] == "power"


def test_api_and_months(setup):
    doc = service.load()
    doc["days"] = {"2026-09-30": {"kwh": 12.0}, "2026-10-01": {"kwh": 10.5}, "2026-10-02": {"kwh": 9.0}}
    service.save(doc)
    assert service.by_month() == {"2026-09": 12.0, "2026-10": 19.5}
    body = TestClient(app).get("/api/v1/power", headers=AUTH).json()
    assert body["configured"] and body["house_watts"] == 1250 and body["power"][0]["name"] == "Dishwasher power"
