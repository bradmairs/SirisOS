"""12.6: SirisTrails streets explored, the wishlist, Home, the monthly recap and SirisAI's facts."""

import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.entrypoint import app
from app.trails import explore, places, service
from tests.test_hub import AUTH
from tests.test_trails import START, folder, hae_workout, track  # noqa: F401


def walks_in(town="Ballarat", n=5):
    body = {"data": {"workouts": [hae_workout("Outdoor Walk", 75, START + timedelta(days=d), track(start=START + timedelta(days=d))) for d in range(n)]}}
    made = service.from_auto_export(body)
    for w in made:
        service.set_place(w["id"], {"name": f"{town} walk", "place": f"{town}, Victoria, Australia", "locality": town, "region": "Victoria",
                                    "country": "Australia", "country_code": "AU"})
    return made


class Answer:
    def __init__(self, data): self.data = data
    def json(self): return self.data
    def raise_for_status(self): return None


def test_streets_explored_in_the_suburbs_you_walk_most(monkeypatch) -> None:
    walks_in()
    (sub,) = explore.suburbs(service.load()["walks"])
    assert sub["locality"] == "Ballarat" and sub["walks"] == 5 and sub["slug"] == "ballarat-victoria"
    # The walks go north along lon 145.0 from -37.8 for 4 km. One street along it, one 1 km east, one outside the boundary.
    ring = [[-37.81, 144.99], [-37.81, 145.02], [-37.75, 145.02], [-37.75, 144.99], [-37.81, 144.99]]
    calls = []

    def polite(client, method, url, **kw):
        calls.append(url)
        if method == "GET":
            return Answer([{"geojson": {"type": "Polygon", "coordinates": [[[p[1], p[0]] for p in ring]]}}])
        return Answer({"elements": [
            {"type": "way", "tags": {"name": "Walked St"}, "geometry": [{"lat": -37.80, "lon": 145.0}, {"lat": -37.78, "lon": 145.0}]},
            {"type": "way", "tags": {"name": "East St"}, "geometry": [{"lat": -37.80, "lon": 145.012}, {"lat": -37.78, "lon": 145.012}]},
            {"type": "way", "tags": {"name": "Far St"}, "geometry": [{"lat": -37.70, "lon": 145.0}, {"lat": -37.69, "lon": 145.0}]},
        ]})

    monkeypatch.setattr(places, "_polite", polite)
    assert explore.fetch_pending() == 1 and explore.fetch_pending() == 0          # one suburb a run, then not again for a while
    (o,) = explore.streets_overview()
    assert o["ready"] and (o["streets"], o["walked"]) == (2, 1) and 0.45 < o["share"] < 0.55
    d = TestClient(app).get("/api/v1/trails/streets/ballarat-victoria", headers=AUTH).json()
    assert {(l["name"], l["walked"]) for l in d["lines"]} == {("Walked St", True), ("East St", False)}
    assert TestClient(app).get("/api/v1/trails/streets/nowhere", headers=AUTH).status_code == 404


def test_the_wishlist_ticks_itself_off(monkeypatch) -> None:
    walks_in(n=1)
    line = [[145.0, -37.80 + i * 0.002] for i in range(10)]       # GeoJSON lon, lat: along the walk's first 2 km

    def polite(client, method, url, **kw):
        if url == explore.SEARCH:
            return Answer([{"osm_type": "relation", "osm_id": 42, "name": "Creek Trail", "category": "route", "type": "hiking", "lat": "-37.79", "lon": "145.0",
                            "address": {"state": "Victoria", "country": "Australia"}}])
        return Answer([{"osm_type": "relation", "osm_id": 42, "name": "Creek Trail", "category": "route", "type": "hiking", "lat": "-37.79", "lon": "145.0",
                        "address": {"state": "Victoria", "country": "Australia"}, "geojson": {"type": "LineString", "coordinates": line}}])

    class Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url, params=None): return Answer({"elevation": [100, 110, 130, 120, 150]})

    monkeypatch.setattr(places, "_polite", polite)
    monkeypatch.setattr(explore.httpx, "Client", Client)
    c = TestClient(app)
    hits = c.get("/api/v1/trails/wishlist/search?q=creek", headers=AUTH).json()
    assert hits == [{"osm": "R42", "name": "Creek Trail", "kind": "track", "where": "Victoria, Australia", "lat": -37.79, "lon": 145.0}]
    wish = c.post("/api/v1/trails/wishlist", headers=AUTH, json={"osm": "R42"}).json()
    assert wish["km"] == 2.0 and wish["ascent_m"] == 60 and wish["highest_m"] == 150
    assert wish["done"]["name"] == "Ballarat walk"                                  # the walk already covers it
    assert c.post("/api/v1/trails/wishlist", headers=AUTH, json={"osm": "R42"}).status_code == 422
    assert c.post("/api/v1/trails/wishlist", headers=AUTH, json={"osm": "../x"}).status_code == 422
    # a peak nobody has been to stays open
    far = {"id": "x_0000000001", "osm": "N1", "name": "Far Peak", "kind": "peak", "center": [-36.0, 146.0], "lines": [], "area": [], "done": None}
    explore._save_wishes([*explore.load_wishes(), far])
    assert explore.tick() == 0
    assert c.delete("/api/v1/trails/wishlist/x_0000000001", headers=AUTH).json() == {"ok": True} and len(explore.load_wishes()) == 1


def test_home_the_monthly_recap_and_sirisais_facts() -> None:
    walks_in(n=3)
    c = TestClient(app)
    h = explore.home_card(datetime(2024, 3, 20, tzinfo=timezone.utc))
    assert h["latest"]["name"] == "Ballarat walk" and h["latest"]["times"] == 3 and h["year"]["walks"] == 3 and h["year"]["km"] == 12.6
    assert c.get("/api/v1/trails/home", headers=AUTH).status_code == 200
    r = explore.month_recap("2024-03")
    assert (r["walks"], r["before"], r["new_places"]) == (3, 0, ["Ballarat"])
    from app.recap import service as recap

    text = recap.as_text({"walks": r})
    assert "3 walks (from 0), 12.6 km and" in text and "new: Ballarat" in text
    f = c.get("/api/v1/facts?topic=walks&q=ballarat", headers=AUTH).json()
    assert f["count"] == 3 and f["walks"][0]["name"] == "Ballarat walk"
    f = c.get("/api/v1/facts?topic=walks&start=2024-03-03&end=2024-03-31", headers=AUTH).json()
    assert f["count"] == 2 and f["period"] == "2024-03-03 to 2024-03-31"


def test_a_track_piece_stands_for_the_whole_track(monkeypatch) -> None:
    pieces = [{"type": "way", "geometry": [{"lat": -38.0 + i * 0.01, "lon": 145.0}, {"lat": -38.0 + (i + 1) * 0.01, "lon": 145.0}]} for i in range(5)]
    asked = []

    def polite(client, method, url, **kw):
        asked.append(kw.get("data", {}).get("data", ""))
        return Answer({"elements": pieces})

    monkeypatch.setattr(places, "_polite", polite)
    whole = explore._whole_track(None, "W123", {"name": 'Two "Bays" Track'})
    assert len(whole) == 5 and round(sum(explore._length_m(l) for l in whole)) == 5560
    assert 'way(id:123)' in asked[0] and '"name"="Two Bays Track"' in asked[0]          # quotes can't break the query


def test_a_track_added_while_overpass_is_busy_is_completed_later(monkeypatch) -> None:
    import httpx

    piece = {"osm_type": "way", "osm_id": 7, "name": "Long Track", "category": "highway", "type": "path", "lat": "-38.0", "lon": "145.0",
             "geojson": {"type": "LineString", "coordinates": [[145.0, -38.0], [145.0, -37.996]]}}
    busy = {"on": True}

    def polite(client, method, url, **kw):
        if method == "POST":
            if busy["on"]:
                raise httpx.HTTPStatusError("502", request=None, response=None)
            return Answer({"elements": [{"type": "way", "geometry": [{"lat": -38.0 + i * 0.01, "lon": 145.0}, {"lat": -38.0 + (i + 1) * 0.01, "lon": 145.0}]} for i in range(3)]})
        return Answer([piece])

    class Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url, params=None): return Answer({"elevation": [10, 20]})

    monkeypatch.setattr(places, "_polite", polite)
    monkeypatch.setattr(explore.httpx, "Client", Client)
    wish = explore.add_wish("W7")
    assert wish["km"] == 0.4 and wish["whole_pending"] == 1
    assert explore.complete_pending() == 0 and explore.load_wishes()[0]["whole_pending"] == 2
    busy["on"] = False
    assert explore.complete_pending() == 1
    w = explore.load_wishes()[0]
    assert w["km"] == 3.3 and "whole_pending" not in w and len(w["lines"]) == 3
