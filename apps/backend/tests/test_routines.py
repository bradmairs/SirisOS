"""10.4: weekend planner, garden, fuel to Shepparton, bins, bedroom, watch tonight, container updates, internet, catch-ups."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.brief.service import zone
from app.entrypoint import app
from app.household import bedroom, bins
from app.hub import service as hub_service
from app.hub.service import get_hub, reset_hub
from app.outdoors import fuel, garden, weekend
from app.routines import api as routines_api
from app.routines import catchups, lab
from tests.test_hub import AUTH, ENV

SAT = date(2026, 11, 28)
THU = datetime(2026, 11, 26, 17, 10, tzinfo=zone())


def _hours(start: date, days: int, rain_from: str | None = None, temp=17.0, past_days: int = 0) -> list[dict]:
    out = []
    for i in range(-24 * past_days, 24 * days):
        t = datetime.combine(start, datetime.min.time()) + timedelta(hours=i)
        stamp = t.strftime("%Y-%m-%dT%H:%M")
        wet = rain_from is not None and stamp >= rain_from
        out.append({"time": stamp, "temperature_c": temp, "rain_chance_percent": 80 if wet else 5, "rain_mm": 2.0 if wet else 0,
                    "conditions": "rain" if wet else "mainly clear", "uv_index": 3, "wind_kmh": 10})
    return out


@pytest.fixture
def world(monkeypatch, tmp_path):
    for env in ("WEEKEND", "GARDEN", "FUEL", "FUEL_CACHE", "BINS", "BEDROOM", "LAB"):
        monkeypatch.setenv(f"SIRISOS_{env}_PATH", str(tmp_path / f"{env.lower()}.json"))
    monkeypatch.setenv("SIRISOS_FAIR_FUEL_KEY", "consumer-123")
    monkeypatch.setattr(routines_api, "_now", lambda: THU)
    state = {"hours": _hours(THU.date(), 4), "past_rain": 0.0, "events": [], "people": [], "put": [], "fuel_headers": [], "osrm": 0,
             "readiness": {"score": 72, "band": "Steady"}}

    def handler(request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if host == "api.fuel.service.vic.gov.au":
            state["fuel_headers"].append(dict(request.headers))
            if path.endswith("/reference-data/stations"):
                return httpx.Response(200, json={"fuelStations": [
                    {"id": "s1", "name": "United Craigieburn", "brandId": "b1", "address": "1 Hume Hwy", "location": {"latitude": -37.60, "longitude": 144.94}},
                    {"id": "s2", "name": "BP Wallan", "brandId": "b2", "location": {"latitude": -37.47, "longitude": 144.96}},
                    {"id": "s3", "name": "Far Away Servo", "location": {"latitude": -37.60, "longitude": 145.30}},
                    {"id": "s4", "name": "Shepparton Shell", "location": {"latitude": -36.40, "longitude": 145.40}},
                    {"id": "s5", "name": "No location"}]})
            if path.endswith("/reference-data/brands"):
                return httpx.Response(200, json={"brands": [{"id": "b1", "name": "United"}, {"id": "b2", "name": "BP"}]})
            if path.endswith("/fuel/prices"):
                return httpx.Response(200, json={"fuelPriceDetails": [
                    {"fuelStation": {"id": "s1"}, "fuelPrices": [{"fuelType": "U91", "price": 181.9, "isAvailable": True}, {"fuelType": "DSL", "price": 199.9}]},
                    {"fuelStation": {"id": "s2"}, "fuelPrices": [{"fuelType": "U91", "price": 176.5, "isAvailable": True}]},
                    {"fuelStation": {"id": "s3"}, "fuelPrices": [{"fuelType": "U91", "price": 150.0, "isAvailable": True}]},
                    {"fuelStation": {"id": "s4"}, "fuelPrices": [{"fuelType": "U91", "price": 160.0, "isAvailable": True}]}]})
        if host == "router.project-osrm.org":
            state["osrm"] += 1
            # Home in Melbourne's north, straight up the Hume, then across to Shepparton.
            return httpx.Response(200, json={"routes": [{"geometry": {"coordinates": [[144.95, -37.70], [144.95, -37.40], [145.10, -37.00], [145.40, -36.38]]}}]})
        if path == "/siris/hub/v1/forecast/hourly":
            return httpx.Response(200, json={"latitude": -37.70, "longitude": 144.95, "hours": state["hours"], "past_rain_mm": state["past_rain"],
                                             "sun": [{"date": (THU.date() + timedelta(days=i)).isoformat(), "sunrise": f"{(THU.date() + timedelta(days=i)).isoformat()}T06:00",
                                                      "sunset": f"{(THU.date() + timedelta(days=i)).isoformat()}T20:00"} for i in range(4)]})
        if path == "/siris/hub/v1/calendar":
            return httpx.Response(200, json={"events": state["events"]})
        if path == "/siris/hub/v1/health/overview":
            return httpx.Response(200, json={"readiness": state["readiness"], "bedtime": {"bedtime": "22:30"}})
        if path == "/siris/hub/v1/health/days":
            return httpx.Response(200, json={"days": state.get("health_days", [])})
        if path == "/siris/hub/v1/sensors":
            return httpx.Response(200, json={"sensors": [{"entity_id": "sensor.bedroom_temperature", "state": "25.4"},
                                                         {"entity_id": "sensor.bedroom_humidity", "state": "55"}]})
        if path == "/siris/hub/v1/watch":
            return httpx.Response(200, json=state.get("watch", {}))
        if path == "/siris/hub/v1/internet":
            return httpx.Response(200, json=state.get("internet", {"available": True, "speeds": [], "outages": []}))
        if path == "/siris/hub/v1/containers":
            return httpx.Response(200, json={"available": True, "updates": [{"container": "sonarr"}], "up_to_date": [], "skipped": {}, "running": False})
        if path == "/siris/hub/v1/containers/update":
            return httpx.Response(200, json={"started": 1, "order": json.loads(request.content)["containers"] or ["sonarr"], "message": "Updating"})
        if path == "/siris/people" and request.method == "GET":
            return httpx.Response(200, json=state["people"])
        if path.startswith("/siris/people/") and request.method == "PUT":
            state["put"].append((path, json.loads(request.content)))
            pid = int(path.rsplit("/", 1)[1])
            for p in state["people"]:
                if p["id"] == pid:
                    p.update(json.loads(request.content))
            return httpx.Response(200, json={"id": pid})
        return httpx.Response(404)

    monkeypatch.setattr(hub_service, "transport", httpx.MockTransport(handler))
    reset_hub(ENV)
    return TestClient(app), state


# -- weekend ------------------------------------------------------------------------------------------------------

def test_weekend_windows_avoid_rain_and_the_calendar_and_pick_routes(world):
    c, state = world
    state["hours"] = _hours(THU.date(), 4, rain_from="2026-11-29T12:00")  # Sunday afternoon on: rain
    state["events"] = [{"title": "Brunch", "start": "2026-11-28T10:00:00+11:00", "end": "2026-11-28T12:00:00+11:00"}]
    c.put("/api/v1/weekend/routes", json={"routes": [{"name": "You Yangs loop", "kind": "hike", "hours": 2.5, "km": 9},
                                                       {"name": "Merri Creek walk", "kind": "walk", "hours": 1}]}, headers=AUTH)
    p = c.get("/api/v1/weekend", headers=AUTH).json()
    assert p["days"] == ["2026-11-28", "2026-11-29"]
    spans = [(w["date"], w["start"], w["end"]) for w in p["windows"]]
    assert ("2026-11-28", "06:00", "10:00") in spans  # before brunch
    assert all(not (w["date"] == "2026-11-28" and "10:00" <= w["start"] < "12:00") for w in p["windows"])  # not during it
    assert all(w["date"] != "2026-11-29" or w["end"] <= "12:00" for w in p["windows"])  # not in Sunday's rain
    morning = next(w for w in p["windows"] if w["start"] == "06:00" and w["date"] == "2026-11-28")
    assert morning["route"]["name"] == "You Yangs loop"  # the longest that fits 4 h
    assert weekend.describe(morning).startswith("Sat 6am–10am, mainly clear, 17–17°: You Yangs loop (2.5 h)")


def test_weekend_recover_day_picks_the_walk_and_push_on_thursday(world):
    c, state = world
    state["readiness"] = {"score": 35, "band": "Recover"}
    weekend.set_routes([{"name": "You Yangs loop", "kind": "hike", "hours": 2.5}, {"name": "Merri Creek walk", "kind": "walk", "hours": 1}])
    p = asyncio.run(weekend.plan(get_hub(), THU.date()))
    assert p["recover"] and all(w["route"]["name"] == "Merri Creek walk" for w in p["windows"])
    msgs = asyncio.run(weekend.push_message(get_hub(), THU))
    assert msgs and msgs[0]["key"] == "weekend:2026-11-28" and msgs[0]["body"].startswith("Best: ")
    assert asyncio.run(weekend.push_message(get_hub(), THU.replace(hour=12))) == []


# -- garden -------------------------------------------------------------------------------------------------------

def test_garden_waters_when_dry_and_skips_when_rain_is_coming(world):
    c, state = world
    assert c.get("/api/v1/garden", headers=AUTH).json() == {"on": False, "protocol": None, "last_watered": None}
    state["hours"] = _hours(THU.date(), 3, temp=31)
    g = c.put("/api/v1/garden", json={"on": True, "protocol": "Water the garden"}, headers=AUTH).json()
    assert g["water"] and g["hot"] and "water early or in the evening" in g["why"]
    msgs = asyncio.run(garden.push_message(get_hub(), THU.replace(hour=7)))
    assert msgs and msgs[0]["title"] == "Water the garden today"
    assert c.post("/api/v1/garden/watered", headers=AUTH).json()["last_watered"] == "2026-11-26"
    state["hours"] = _hours(THU.date(), 3, rain_from="2026-11-27T03:00")
    g = c.get("/api/v1/garden", headers=AUTH).json()
    assert not g["water"] and g["why"].startswith("Rain's coming")
    state["hours"], state["past_rain"] = _hours(THU.date(), 3), 12.0
    assert c.get("/api/v1/garden", headers=AUTH).json()["why"] == "12 mm has fallen in the last three days."


# -- fuel ---------------------------------------------------------------------------------------------------------

def test_fuel_finds_the_cheapest_in_the_first_30_km(world):
    c, state = world
    f = c.get("/api/v1/fuel", headers=AUTH).json()
    # s3 (150c) is far off the road and s4 (160c) is in Shepparton, past 30 km: BP Wallan's the cheapest on the way.
    assert f["best"]["name"] == "BP Wallan" and f["best"]["brand"] == "BP" and f["best"]["price"] == 176.5
    assert [o["id"] for o in f["options"]] == ["s2", "s1"] and f["saving_cents"] == 2.7
    assert 20 < f["best"]["km_in"] <= 30
    assert f["route_km"] == 30.0 and f["settings"]["fuel_type"] == "U91" and f["for"] is None  # Thursday: not the drive
    assert all(h["x-consumer-id"] == "consumer-123" and len(h["x-transactionid"]) == 36 for h in state["fuel_headers"])
    c.get("/api/v1/fuel", headers=AUTH)
    assert state["osrm"] == 1  # the route's kept
    wed = datetime(2026, 12, 2, 5, 35, tzinfo=zone())
    msgs = asyncio.run(fuel.push_message(get_hub(), wed))
    assert msgs[0]["title"] == "Fuel on the way: BP Wallan" and "U91 176.5¢" in msgs[0]["body"] and "Yesterday's prices" in msgs[0]["body"]
    assert asyncio.run(fuel.push_message(get_hub(), wed.replace(hour=9))) == []
    assert fuel.due(datetime(2026, 12, 1, 19, 0, tzinfo=zone()), fuel.settings()) == date(2026, 12, 2)  # Tuesday evening: tomorrow's
    f = c.put("/api/v1/fuel/settings", json={"fuel_type": "DSL"}, headers=AUTH).json()
    assert f["best"]["name"] == "United Craigieburn" and f["best"]["price"] == 199.9


def test_fuel_without_a_key_says_how_to_get_one(world, monkeypatch):
    c, _ = world
    monkeypatch.delenv("SIRISOS_FAIR_FUEL_KEY")
    f = c.get("/api/v1/fuel", headers=AUTH).json()
    assert not f["configured"] and "SIRISOS_FAIR_FUEL_KEY" in f["why"]


def test_station_locations_are_read_wherever_they_are():
    assert fuel.parse_station({"id": 1, "name": "A", "latitude": "-37.1", "longitude": "145.2"})["lat"] == -37.1
    assert fuel.parse_station({"id": 2, "name": "B", "address": {"latitude": -37.2, "longitude": 145.3, "suburb": "Wallan"}})["address"] == "Wallan"
    assert fuel.parse_station({"id": 3, "name": "C"}) is None


# -- bins ---------------------------------------------------------------------------------------------------------

def test_bin_night(world):
    c, _ = world
    r = c.put("/api/v1/bins", json={"bins": [{"kind": "rubbish", "every_weeks": 1, "first": "2026-11-06"},
                                             {"kind": "recycling", "every_weeks": 2, "first": "2026-11-06"},
                                             {"kind": "green", "every_weeks": 2, "first": "2026-11-13"}]}, headers=AUTH).json()
    assert r["next"] == {"date": "2026-11-27", "kinds": ["rubbish", "green"], "text": "Rubbish and green waste"}
    assert r["show"] and r["when"] == "tonight"  # Thursday 5pm, collection Friday
    msgs = bins.push_message(datetime(2026, 11, 26, 19, 0, tzinfo=zone()))
    assert msgs[0]["title"] == "Bins out tonight: rubbish and green waste"
    assert bins.on(date(2026, 12, 4)) == ["rubbish", "recycling"]
    assert bins.push_message(datetime(2026, 11, 27, 19, 0, tzinfo=zone())) == []  # nothing on Saturday
    assert c.put("/api/v1/bins", json={"bins": [{"kind": "rubbish", "every_weeks": 3, "first": "2026-11-06"}]}, headers=AUTH).status_code == 422


# -- bedroom ------------------------------------------------------------------------------------------------------

def test_bedroom_before_bed_and_the_best_temperature(world, monkeypatch):
    c, state = world
    b = c.put("/api/v1/bedroom", json={"temp_entity": "sensor.bedroom_temperature", "humidity_entity": "sensor.bedroom_humidity"}, headers=AUTH).json()
    assert b["show"] is False  # 5pm: not near bedtime
    late = datetime(2026, 11, 26, 21, 45, tzinfo=zone())
    monkeypatch.setattr(routines_api, "_now", lambda: late)
    b = c.get("/api/v1/bedroom", headers=AUTH).json()
    assert b["show"] and b["temp"] == 25.4 and b["advice"] == "Bedroom is 25.4°: fan or aircon for half an hour before bed?"
    assert bedroom.load()["nights"][-1] == {"date": "2026-11-26", "temp": 25.4, "humidity": 55.0, "sleep_date": "2026-11-27"}
    msgs = asyncio.run(bedroom.push_message(get_hub(), late))
    assert msgs[0]["key"] == "bedroom:2026-11-26"
    assert c.put("/api/v1/bedroom", json={"temp_entity": "light.lamp"}, headers=AUTH).status_code == 422
    nights = [{"date": f"n{i}", "temp": 18.5 if i % 2 else 24.5, "sleep_date": f"d{i}"} for i in range(16)]
    sleep = {f"d{i}": 7.8 if i % 2 else 6.4 for i in range(16)}
    assert bedroom.best_range(nights, sleep) == {"low": 18, "high": 20, "sleep": 7.8, "other": 6.4, "nights": 16}


# -- watch --------------------------------------------------------------------------------------------------------

def test_watch_tonight_fits_the_time_before_bed(world, monkeypatch):
    c, state = world
    state["watch"] = {"on_deck": [{"title": "Slow Horses: S04E03", "type": "episode", "show": "Slow Horses"}],
                      "new_unwatched": [{"title": "Dune: Part Two", "type": "movie"}, {"title": "The Bear: S03E01", "type": "episode", "show": "The Bear"}],
                      "episodes": [{"series": "Severance", "air_date": "2026-11-28"}], "movies": []}
    monkeypatch.setattr(routines_api, "_now", lambda: datetime(2026, 11, 26, 19, 30, tzinfo=zone()))
    w = c.get("/api/v1/watch/tonight", headers=AUTH).json()
    assert w["minutes_to_bed"] == 180 and [p["title"] for p in w["picks"]] == ["Slow Horses: S04E03", "Dune: Part Two", "The Bear: S03E01"]
    assert w["episodes"][0]["series"] == "Severance"
    monkeypatch.setattr(routines_api, "_now", lambda: datetime(2026, 11, 26, 21, 30, tzinfo=zone()))
    w = c.get("/api/v1/watch/tonight", headers=AUTH).json()
    assert [p["title"] for p in w["picks"]] == ["Slow Horses: S04E03", "The Bear: S03E01"]  # an hour: no film


# -- lab ----------------------------------------------------------------------------------------------------------

def test_containers_and_a_slow_internet_week(world):
    c, state = world
    assert c.get("/api/v1/lab/containers", headers=AUTH).json()["updates"][0]["container"] == "sonarr"
    assert c.post("/api/v1/lab/containers/update", json={"containers": ["sonarr"]}, headers=AUTH).json()["order"] == ["sonarr"]
    state["internet"] = {"available": True, "outages": [], "speeds": [
        {"at": f"2026-11-{d:02d}T{h:02d}:00:00+00:00", "down": down, "up": 18} for d, down in ((22, 92), (23, 40), (24, 38), (25, 41)) for h in (1, 7)]}
    i = c.put("/api/v1/lab/internet/plan", json={"down": 100, "up": 20}, headers=AUTH).json()
    assert [d["down"] for d in i["daily"]] == [92, 40, 38, 41] and len(i["slow"]) == 3 and i["share_of_plan"] == 40
    msgs = asyncio.run(lab.push_message(get_hub(), datetime(2026, 11, 26, 9, 5, tzinfo=zone())))
    assert msgs[0]["title"] == "The internet's been slow" and "About 40 Mbps for 3 days on a 100 Mbps plan" in msgs[0]["body"]


# -- catch-ups ----------------------------------------------------------------------------------------------------

def test_catchups_overdue_free_afternoon_and_caught_up(world):
    c, state = world
    state["people"] = [{"id": 1, "name": "Sam", "keep_in_touch_days": 30, "last_contact": "2026-09-01"},
                       {"id": 2, "name": "Alex", "keep_in_touch_days": 60, "last_contact": "2026-11-01"},
                       {"id": 3, "name": "Jo", "keep_in_touch_days": None}]
    state["events"] = [{"title": "Footy", "start": "2026-11-28T13:00:00+11:00", "end": "2026-11-28T16:00:00+11:00"}]
    o = c.get("/api/v1/catchups", headers=AUTH).json()
    assert [p["name"] for p in o["overdue"]] == ["Sam"] and o["overdue"][0]["days_since"] == 86
    assert {"date": "2026-11-28", "part": "afternoon"} not in o["free"] and {"date": "2026-11-29", "part": "afternoon"} in o["free"]
    msgs = asyncio.run(catchups.push_message(get_hub(), datetime(2026, 11, 27, 12, 5, tzinfo=zone())))
    assert msgs[0]["title"] == "Catch up with Sam?" and "Sunday afternoon's free" in msgs[0]["body"]
    o = c.post("/api/v1/catchups/1/done", headers=AUTH).json()
    assert state["put"][-1] == ("/siris/people/1", {"last_contact": "2026-11-26"}) and o["overdue"] == []
    c.put("/api/v1/catchups/3", json={"days": 14}, headers=AUTH)
    assert state["put"][-1] == ("/siris/people/3", {"keep_in_touch_days": 14})
