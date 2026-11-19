"""10.2: a trip on one card: the weather there, a packing list, bills while away, the out-of-office reminder."""

from __future__ import annotations

from datetime import date, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.hub import service as hub_service
from app.hub.service import reset_hub
from app.travel import api as travel_api
from app.travel import service
from tests.test_hub import AUTH, ENV

TODAY = date(2026, 11, 19)


@pytest.fixture
def c(monkeypatch, tmp_path):
    monkeypatch.setenv("SIRISOS_TRIPS_PATH", str(tmp_path / "trips.json"))
    monkeypatch.setenv("SIRISOS_RENEWALS_PATH", str(tmp_path / "renewals.json"))
    monkeypatch.setattr(travel_api, "_today", lambda: TODAY)
    monkeypatch.setattr(service, "date", type("D", (date,), {"today": staticmethod(lambda: TODAY)}))
    asked = []

    def handler(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        if request.url.host == "geocoding-api.open-meteo.com":
            name = request.url.params["name"]
            if name == "Nowhere":
                return httpx.Response(200, json={})
            if name == "Tokyo":
                return httpx.Response(200, json={"results": [{"name": "Tokyo", "admin1": "Tokyo", "country": "Japan", "country_code": "JP", "latitude": 35.69, "longitude": 139.69}]})
            return httpx.Response(200, json={"results": [{"name": "Hobart", "admin1": "Tasmania", "country": "Australia", "country_code": "AU", "latitude": -42.88, "longitude": 147.33}]})
        if request.url.host == "api.open-meteo.com":
            s, e = request.url.params["start_date"], request.url.params["end_date"]
            days = [d.isoformat() for d in (date.fromisoformat(s).fromordinal(o) for o in range(date.fromisoformat(s).toordinal(), date.fromisoformat(e).toordinal() + 1))]
            return httpx.Response(200, json={"daily": {"time": days, "weather_code": [61] * len(days), "temperature_2m_max": [14] * len(days),
                                                        "temperature_2m_min": [6] * len(days), "precipitation_probability_max": [70] * len(days), "uv_index_max": [3] * len(days)}})
        return httpx.Response(404)

    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    reset_hub(ENV)
    client = TestClient(app)
    client.asked = asked  # type: ignore[attr-defined]
    return client


def test_a_trip_with_weather_packing_and_out_of_office(c):
    t = c.post("/api/v1/travel", json={"destination": "Hobart", "start": "2026-11-27", "end": "2026-11-30"}, headers=AUTH).json()
    assert t["place"] == "Hobart, Tasmania, Australia" and t["nights"] == 3 and t["days_to_go"] == 8
    assert t["weather"]["days"][0] == {"date": "2026-11-27", "conditions": "Rain", "high_c": 14, "low_c": 6, "rain_chance": 70, "uv": 3}
    items = [p["item"] for p in t["packing"]]
    assert "4 sets of clothes" in items and "Rain jacket" in items and "Warm jacket" in items
    assert "Passport" not in items and "Sunscreen" not in items
    assert t["ooo_day"] == "2026-11-26"  # the Thursday before a Friday start
    # Only the place and dates go to Open-Meteo.
    assert all("Hobart" in u or "latitude" in u for u in c.asked)

    # Not on Home yet (8 days out), then from a week before.
    assert c.get("/api/v1/travel/current", headers=AUTH).json() == {"trip": None}
    assert service.current(date(2026, 11, 20))["id"] == t["id"]

    # Tick something packed, add an item; tick the out-of-office.
    packing = t["packing"] + [{"item": "Hiking boots", "done": False}]
    packing[0]["done"] = True
    t2 = c.patch(f"/api/v1/travel/{t['id']}", json={"packing": packing}, headers=AUTH).json()
    assert t2["packed"] == 1 and t2["to_pack"] == len(packing)

    msgs = service.push_message(datetime(2026, 11, 26, 15, 0))
    assert msgs and msgs[0]["key"] == f"travel:ooo:{t['id']}" and "Hobart" in msgs[0]["body"]
    assert service.push_message(datetime(2026, 11, 26, 14, 0)) == []
    c.patch(f"/api/v1/travel/{t['id']}", json={"ooo_done": True}, headers=AUTH)
    assert service.push_message(datetime(2026, 11, 26, 15, 0)) == []

    assert c.delete(f"/api/v1/travel/{t['id']}", headers=AUTH).json() == {"removed": True}
    assert c.patch("/api/v1/travel/../x", json={}, headers=AUTH).status_code == 404


def test_overseas_far_off_and_unknown_places(c):
    t = c.post("/api/v1/travel", json={"destination": "Tokyo", "start": "2027-01-10", "end": "2027-01-20"}, headers=AUTH).json()
    assert "Passport" in [p["item"] for p in t["packing"]] and "7 sets of clothes" in [p["item"] for p in t["packing"]]
    assert t["weather"]["days"] == [] and "forecast reaches it from" in t["weather"]["note"]
    u = c.post("/api/v1/travel", json={"destination": "Nowhere", "start": "2026-12-01", "end": "2026-12-02"}, headers=AUTH).json()
    assert u["place"] is None and "Couldn't find" in u["weather"]["note"]
    assert c.post("/api/v1/travel", json={"destination": "X", "start": "2026-12-05", "end": "2026-12-01"}, headers=AUTH).status_code == 422
    listing = c.get("/api/v1/travel", headers=AUTH).json()
    assert listing["next"]["destination"] == "Nowhere" and len(listing["upcoming"]) == 2


def test_bills_while_away(c, monkeypatch):
    from app.budget import forecast
    from app.renewals import service as renewals

    monkeypatch.setattr(forecast, "recurring", lambda *a, **k: [
        {"name": "NETFLIX.COM", "amount": 25.99, "next": "2026-11-28", "days": 30, "status": None}])
    renewals.add("Car rego", "car", "2026-11-29")
    t = c.post("/api/v1/travel", json={"destination": "Hobart", "start": "2026-11-27", "end": "2026-11-30"}, headers=AUTH).json()
    assert [(b["date"], b["kind"]) for b in t["bills"]] == [("2026-11-28", "charge"), ("2026-11-29", "renewal")]
