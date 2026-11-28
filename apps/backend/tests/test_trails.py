"""11.22: SirisTrails: walks of an hour or more and every hike, with their routes, from Apple Health."""

import io
import json
import time
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.entrypoint import app
from app.trails import service
from tests.test_hub import AUTH

START = datetime(2024, 3, 2, 8, 0, tzinfo=timezone(timedelta(hours=11)))


@pytest.fixture(autouse=True)
def folder(tmp_path, monkeypatch):
    monkeypatch.setenv("SIRISOS_TRAILS_PATH", str(tmp_path / "trails"))
    monkeypatch.setenv("SIRISOS_TRAILS_PLACES", "off")  # no background naming runs (or network) unless a test turns it on
    service._status.update(running=False)
    return tmp_path


def track(n=40, climb=5.0, start=START):
    """A walk north, climbing `climb` m per point with ±1 m of GPS noise, 30 s apart."""
    return [[-37.8 + i * 0.001, 145.0, 100 + i * climb + (1 if i % 2 else -1), (start + timedelta(seconds=30 * i)).isoformat()] for i in range(n)]


def hae_workout(name, minutes, start=START, points=None):
    pts = points if points is not None else track(start=start)
    return {"name": name, "start": start.strftime("%Y-%m-%d %H:%M:%S %z"), "end": (start + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S %z"),
            "duration": minutes * 60, "distance": {"qty": 4.2, "units": "km"}, "activeEnergyBurned": {"qty": 350, "units": "kcal"},
            "heartRate": {"avg": {"qty": 112}, "max": {"qty": 151}},
            "route": [{"lat": p[0], "lon": p[1], "altitude": p[2], "timestamp": p[3]} for p in pts]}


def test_walks_of_an_hour_and_every_hike_are_kept_with_their_numbers() -> None:
    body = {"data": {"workouts": [hae_workout("Outdoor Walk", 75), hae_workout("Outdoor Walk", 40, START + timedelta(days=1)),
                                  hae_workout("Hiking", 35, START + timedelta(days=2)), hae_workout("Indoor Walk", 90, START + timedelta(days=3)),
                                  hae_workout("Outdoor Run", 80, START + timedelta(days=4))]}}
    kept = service.from_auto_export(body)
    assert [w["kind"] for w in kept] == ["walk", "hike"]                       # 40 min walk, indoor walk and run left out
    walk = kept[0]
    assert walk["name"] == "Walk, Sat 2 Mar 2024" and walk["minutes"] == 75 and walk["km"] == 4.2
    assert walk["ascent_m"] == pytest.approx(195, abs=10) and walk["descent_m"] == 0    # the ±1 m noise isn't climbing
    assert walk["avg_hr"] == 112 and walk["max_hr"] == 151 and walk["kcal"] == 350 and walk["pace_min_per_km"] == pytest.approx(17.9, abs=0.1)
    assert walk["moving_minutes"] == pytest.approx(19.5, abs=0.6) and len(walk["line"]) <= service.MAP_POINTS
    assert service.from_auto_export(body) == []                                 # the same walks again: kept once
    service.strip_routes(body)
    assert all("route" not in w for w in body["data"]["workouts"])


def _export_zip(workouts_xml: str, gpx: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("apple_health_export/export.xml", f'<?xml version="1.0"?><HealthData><Record type="x"/>{workouts_xml}</HealthData>')
        z.writestr("apple_health_export/export_cda.xml", "<x/>")
        for name, text in gpx.items():
            z.writestr(f"apple_health_export/workout-routes/{name}", text)
    return buf.getvalue()


def _gpx(start: datetime, n=30) -> str:
    pts = "".join(f'<trkpt lon="{170.1 + i * 0.002:.4f}" lat="{-43.6 - i * 0.001:.4f}"><ele>{800 + i * 10}</ele>'
                  f'<time>{(start + timedelta(minutes=i)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}</time></trkpt>' for i in range(n))
    return f'<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>{pts}</trkseg></trk></gpx>'


def test_the_apple_health_export_brings_in_every_walk_and_hike_once(folder) -> None:
    hike = START - timedelta(days=400)
    xml = (f'<Workout workoutActivityType="HKWorkoutActivityTypeHiking" duration="4.5" durationUnit="hr" totalDistance="12.3" totalDistanceUnit="km" '
           f'startDate="{hike.strftime("%Y-%m-%d %H:%M:%S %z")}" endDate="{(hike + timedelta(hours=4.5)).strftime("%Y-%m-%d %H:%M:%S %z")}">'
           '<WorkoutStatistics type="HKQuantityTypeIdentifierHeartRate" average="121" maximum="160" unit="count/min"/>'
           '<WorkoutRoute><FileReference path="/workout-routes/route_hike.gpx"/></WorkoutRoute></Workout>'
           f'<Workout workoutActivityType="HKWorkoutActivityTypeWalking" duration="25" durationUnit="min" startDate="2024-01-01 09:00:00 +1100" endDate="2024-01-01 09:25:00 +1100">'
           '<WorkoutRoute><FileReference path="/workout-routes/route_short.gpx"/></WorkoutRoute></Workout>'
           '<Workout workoutActivityType="HKWorkoutActivityTypeWalking" duration="70" durationUnit="min" startDate="2024-01-02 09:00:00 +1100" endDate="2024-01-02 10:10:00 +1100"/>')
    path = folder / "export.zip"
    path.write_bytes(_export_zip(xml, {"route_hike.gpx": _gpx(hike), "route_short.gpx": _gpx(START)}))
    result = service.import_apple_export(path)
    assert result == {"workouts": 3, "added": 1, "already_here": 0, "no_route": 1}   # the 25 min walk isn't wanted; the 70 min one has no route
    [hike_walk] = service.load()["walks"]
    assert hike_walk["kind"] == "hike" and hike_walk["minutes"] == 270 and hike_walk["km"] == 12.3 and hike_walk["ascent_m"] == 290
    assert hike_walk["highest_m"] == 1090 and hike_walk["avg_hr"] == 121 and hike_walk["start_point"] == [-43.6, 170.1]
    assert service.import_apple_export(path)["already_here"] == 1


def test_the_screen_lists_shows_renames_deletes_and_an_export_uploads(folder) -> None:
    c = TestClient(app, headers=AUTH)
    service.from_auto_export({"data": {"workouts": [hae_workout("Hiking", 200)]}})
    listed = c.get("/api/v1/trails").json()
    assert listed["count"] == 1 and listed["hikes"] == 1 and listed["years"] == [2024]
    walk_id = listed["walks"][0]["id"]
    one = c.get(f"/api/v1/trails/{walk_id}").json()
    assert len(one["route"]) == 40 and one["profile"][0][0] == 0.0 and one["profile"][-1][0] > 4
    assert c.patch(f"/api/v1/trails/{walk_id}", json={"name": "Mt Feathertop", "note": "Razorback, clear day"}).json()["name"] == "Mt Feathertop"
    assert c.get("/api/v1/trails/../etc").status_code == 404
    assert c.delete(f"/api/v1/trails/{walk_id}").json() == {"ok": True}
    assert service.from_auto_export({"data": {"workouts": [hae_workout("Hiking", 200)]}}) == []   # deleted stays deleted
    assert c.post("/api/v1/trails/apple-export", files={"file": ("export.zip", b"not a zip")}).status_code == 422
    zipped = _export_zip("", {})
    assert c.post("/api/v1/trails/apple-export", files={"file": ("export.zip", zipped)}).json()["started"] is True
    for _ in range(50):
        if not c.get("/api/v1/trails/import").json().get("running"):
            break
        time.sleep(0.05)
    assert c.get("/api/v1/trails/import").json()["workouts"] == 0


def test_the_health_import_keeps_walks_and_passes_the_rest_on_without_routes(monkeypatch) -> None:
    from app.hub import sirisai_api
    from app.training import health_import

    sent = {}

    async def post(hub, path, json=None, timeout=None, headers=None):
        sent["body"] = json
        return {"days": {"2024-03-02": 1}, "format": "health_auto_export"}

    monkeypatch.setattr(sirisai_api, "post", post)
    monkeypatch.setattr(health_import, "check", lambda key: True)
    r = TestClient(app).post("/api/v1/health/import", headers={"Authorization": "Bearer k"},
                             content=json.dumps({"data": {"metrics": [], "workouts": [hae_workout("Outdoor Walk", 90)]}}))
    assert r.status_code == 200 and service.load()["walks"][0]["kind"] == "walk"
    assert "route" not in sent["body"]["data"]["workouts"][0]


# -- 12.1: names from where the walk went, splits, the smoothed profile ----------------------------------------------

def test_names_come_from_the_peak_track_park_or_place(monkeypatch) -> None:
    from app.trails import places

    route = [(-41.0 + i * 0.001, 173.0) for i in range(20)]
    track = {"type": "way", "tags": {"highway": "path", "name": "Falls River Track"},
             "geometry": [{"lat": p[0], "lon": p[1]} for p in route]}
    road = {"type": "way", "tags": {"highway": "track", "name": "Calwell Road"}, "geometry": [{"lat": p[0], "lon": p[1]} for p in route]}
    park = {"type": "relation", "tags": {"boundary": "national_park", "name": "Abel Tasman National Park"},
            "bounds": {"minlat": -41.1, "maxlat": -40.9, "minlon": 172.9, "maxlon": 173.1}}
    peak = {"type": "node", "lat": -40.981, "lon": 173.0, "tags": {"natural": "peak", "name": "獅子山 Lion Rock", "name:en": "Lion Rock"}}
    assert places.choose([track, park], route, None, "hike") == {"peak": None, "trail": "Falls River Track", "park": "Abel Tasman National Park"}
    assert places.choose([road, park], route, None, "hike")["trail"] is None             # a road isn't a walk's name
    assert places.choose([peak], route, (-40.981, 173.0), "hike")["peak"] == "Lion Rock"

    class Fake:
        def __init__(self, data): self.data = data
        def json(self): return self.data

    addr = Fake({"address": {"suburb": "Kaiapoi", "state": "Canterbury", "country": "New Zealand", "country_code": "nz"}})
    answers = iter([addr, Fake({"elements": [road, park]})])
    monkeypatch.setattr(places, "_polite", lambda *a, **k: next(answers))
    pts = [[p[0], p[1], 10.0, None] for p in route] + [[route[0][0], route[0][1], 10.0, None]]
    info = places.describe(pts, "walk")
    assert info["name"] == "Abel Tasman National Park" and info["place"] == "Kaiapoi, Canterbury, New Zealand" and info["loop"]
    assert (info["region"], info["country"], info["country_code"]) == ("Canterbury", "New Zealand", "NZ") and info["overpass_done"]
    answers = iter([addr])                                                           # the fast pass: Nominatim only
    assert places.describe(pts, "walk", overpass=False)["name"] == "Kaiapoi loop"
    # A hike: Nominatim's natural feature at the high point is the peak, even when Overpass is busy.
    hike_pts = [[p[0], p[1], 100.0 + i, None] for i, p in enumerate(route)]
    top = hike_pts[-1]
    answers = iter([addr, Fake({"category": "natural", "type": "peak", "lat": str(top[0]), "lon": str(top[1]), "name": "Mount Lofty"})])
    got = places.describe(hike_pts, "hike", overpass=False)
    assert got["name"] == "Mount Lofty" and got["peak"] == "Mount Lofty"


def test_a_place_names_the_walk_unless_youve_renamed_it() -> None:
    [walk, other] = service.from_auto_export({"data": {"workouts": [hae_workout("Hiking", 120), hae_workout("Hiking", 90, START + timedelta(days=9))]}})
    service.set_place(walk["id"], {"name": "Mount Lofty", "place": "Wonga Park, Victoria, Australia", "peak": "Mount Lofty", "loop": False})
    service.change(other["id"], name="With Sam")
    service.set_place(other["id"], {"name": "Warrandyte State Park", "place": "Warrandyte, Victoria, Australia", "retry": True})
    got = {w["id"]: w for w in service.load()["walks"]}
    assert got[walk["id"]]["name"] == "Mount Lofty" and got[walk["id"]]["landmarks"] == {"peak": "Mount Lofty"}
    assert got[other["id"]]["name"] == "With Sam" and got[other["id"]]["place"] == "Warrandyte, Victoria, Australia"
    assert got[other["id"]]["names_retry"] == 1                                     # Overpass was busy: looked up again later


def test_splits_and_a_smoothed_profile_with_positions() -> None:
    [walk] = service.from_auto_export({"data": {"workouts": [hae_workout("Hiking", 120, points=track(n=30))]}})
    d = service.detail(walk["id"])
    # 29 steps of ~111 m (3.2 km): three whole kilometres and a part
    assert [s["km"] for s in d["splits"]] == [1, 2, 3, 4] and d["splits"][-1]["length_km"] == pytest.approx(0.22, abs=0.03)
    assert d["splits"][0]["minutes"] == pytest.approx(4.5, abs=0.6)
    assert d["splits"][0]["up_m"] > 0
    assert [m[0] for m in d["km_marks"]] == [1, 2, 3] and len(d["profile"][0]) == 4
    noisy = [p[1] for p in d["profile"]]
    assert all(b >= a - 0.01 for a, b in zip(noisy, noisy[1:]))                     # the ±1 m wobble is smoothed out



def test_where_you_walked_by_country_and_state_with_records() -> None:
    a, b, c = service.from_auto_export({"data": {"workouts": [hae_workout("Hiking", 200), hae_workout("Outdoor Walk", 80, START + timedelta(days=3)),
                                                              hae_workout("Outdoor Walk", 90, START + timedelta(days=400))]}})
    service.set_place(a["id"], {"name": "Mount Lofty", "place": "Wonga Park, Victoria, Australia", "locality": "Wonga Park", "region": "Victoria", "country": "Australia", "country_code": "AU"})
    service.set_place(b["id"], {"name": "Kaiapoi loop", "place": "Kaiapoi, Canterbury, New Zealand", "locality": "Kaiapoi", "region": "Canterbury", "country": "New Zealand", "country_code": "NZ"})
    service.set_place(c["id"], {"name": "Ivanhoe walk", "place": "Ivanhoe, Victoria, Australia", "locality": "Ivanhoe", "region": "Victoria", "country": "Australia", "country_code": "AU"})
    s = service.summary()
    assert (s["countries"], s["regions"], s["places"]) == (2, 2, 3)
    au = next(x for x in s["where"] if x["country"] == "Australia")
    assert au["flag"] == "🇦🇺" and au["walks"] == 2 and au["regions"] == [{"region": "Victoria", "walks": 2, "km": 8.4, "places": 2}]
    assert s["records"]["longest_time"]["name"] == "Mount Lofty" and [y["year"] for y in s["by_year"]] == [2024, 2025]
    assert s["avg_km"] == 4.2 and service.summary(2025)["count"] == 1


def test_the_fast_pass_names_everything_then_overpass_a_few_at_a_time(monkeypatch) -> None:
    from app.trails import places

    monkeypatch.setenv("SIRISOS_TRAILS_PLACES", "on")
    walks = service.from_auto_export({"data": {"workouts": [hae_workout("Outdoor Walk", 80, START + timedelta(days=i)) for i in range(3)]}})
    calls = []

    def fake(points, kind, overpass=True):
        calls.append(overpass)
        return {"name": "Kaiapoi loop", "place": "Kaiapoi, Canterbury, New Zealand", "locality": "Kaiapoi", "region": "Canterbury",
                "country": "New Zealand", "country_code": "NZ", "loop": True, **({"trail": "Rangiora Track", "overpass_done": True} if overpass else {})}

    monkeypatch.setattr(places, "describe", fake)
    assert places.name_pending(overpass_limit=1) == 4                               # three fast, then one slow
    assert calls == [False, False, False, True]
    got = {w["id"]: w for w in service.load()["walks"]}
    assert sum(1 for w in got.values() if w.get("overpass_done")) == 1 and all(w["country"] == "New Zealand" for w in got.values())



def test_a_new_walk_is_named_straight_away_and_runs_never_overlap(monkeypatch) -> None:
    from app.hub import sirisai_api
    from app.trails import places
    from app.training import health_import

    started = []
    monkeypatch.setattr(places, "kick", lambda: started.append(True))

    async def post(hub, path, json=None, timeout=None, headers=None):
        return {"days": {}, "format": "health_auto_export"}

    monkeypatch.setattr(sirisai_api, "post", post)
    monkeypatch.setattr(health_import, "check", lambda key: True)
    TestClient(app).post("/api/v1/health/import", headers={"Authorization": "Bearer k"},
                         content=json.dumps({"data": {"workouts": [hae_workout("Hiking", 90)]}}))
    assert started == [True]                                                        # a walk arrived: naming kicked off
    TestClient(app).post("/api/v1/health/import", headers={"Authorization": "Bearer k"},
                         content=json.dumps({"data": {"workouts": [hae_workout("Outdoor Run", 90)]}}))
    assert started == [True]                                                        # nothing kept: nothing to name
    monkeypatch.setenv("SIRISOS_TRAILS_PLACES", "on")
    assert places._naming.acquire(blocking=False)
    try:
        assert places.name_pending() == 0                                           # a run already going: this one steps aside
    finally:
        places._naming.release()



def test_japans_prefectures_and_hikes_first(monkeypatch) -> None:
    from app.trails import places

    assert places._place_line({"city": "Hakone", "province": "Kanagawa Prefecture", "country": "Japan"})[1] == "Hakone, Kanagawa Prefecture, Japan"
    monkeypatch.setenv("SIRISOS_TRAILS_PLACES", "on")
    walk, hike = service.from_auto_export({"data": {"workouts": [hae_workout("Outdoor Walk", 80), hae_workout("Hiking", 80, START + timedelta(days=1))]}})
    order = []

    def fake(points, kind, overpass=True):
        order.append((kind, overpass))
        return {"name": "x", "place": "x", "region": "Kanagawa Prefecture", "country": "Japan", "country_code": "JP", "loop": False,
                **({"overpass_done": True} if overpass else {})}

    monkeypatch.setattr(places, "describe", fake)
    places.name_pending(overpass_limit=1)
    assert order[-1] == ("hike", True)                                              # the slow pass takes hikes first
    assert all(w["place_v"] == places.PLACE_VERSION for w in service.load()["walks"])
    order.clear()
    places.name_pending(overpass_limit=0)
    assert order == []                                                              # placed with a region: not looked up again



def test_each_walk_has_its_own_time_zone(tmp_path, monkeypatch) -> None:
    tab = tmp_path / "zone1970.tab"
    tab.write_text("AU\t-3352+15113\tAustralia/Sydney\tNSW\nAU\t-3749+14458\tAustralia/Melbourne\tVictoria\n"
                   "AU\t-2728+15302\tAustralia/Brisbane\tQueensland\nCN\t+3114+12128\tAsia/Shanghai\tBeijing Time\n"
                   "NZ\t-3652+17446\tPacific/Auckland\tmost of NZ\nNZ\t-4357-17633\tPacific/Chatham\tChatham Islands\n")
    monkeypatch.setenv("SIRISOS_TRAILS_ZONE_TAB", str(tab))
    service._zones.cache_clear(); service.tz_for.cache_clear()
    assert service.tz_for("AU", -37.8, 145.0) == "Australia/Melbourne"
    assert service.tz_for("AU", -27.5, 153.0) == "Australia/Brisbane"
    assert service.tz_for("AU", -28.6, 153.6, "New South Wales") == "Australia/Sydney"   # Byron Bay: nearer Brisbane, on Sydney time
    assert service.tz_for("NZ", -43.38, 172.65) == "Pacific/Auckland"
    assert service.tz_for("CN", 22.35, 114.18) == "Asia/Shanghai"                # Hong Kong: Nominatim says China; the same UTC+8
    assert service.tz_for(None, 0, 0) is None
    service._zones.cache_clear(); service.tz_for.cache_clear()



def test_a_missing_state_is_asked_for_at_state_level(monkeypatch) -> None:
    from app.trails import places

    class Fake:
        def __init__(self, data): self.data = data
        def json(self): return self.data

    answers = iter([Fake({"address": {"city": "Shinjuku", "ISO3166-2-lvl4": "JP-13", "country": "Japan", "country_code": "jp"}}), Fake({"name": "Tokyo"})])
    monkeypatch.setattr(places, "_polite", lambda *a, **k: next(answers))
    got = places.where(None, 35.69, 139.70)
    assert (got["region"], got["place"]) == ("Tokyo", "Shinjuku, Tokyo, Japan")


# -- 12.4 ----------------------------------------------------------------------------------------------------------

def loop_track(lat=-37.56, lon=143.85, n=60, start=START, reverse=False, shift=0):
    """A walk round a 1 km square, starting `shift` points in, either way round."""
    import math as m

    ring = []
    for i in range(n):
        a = 2 * m.pi * i / n
        ring.append((lat + 0.0045 * m.sin(a), lon + 0.0057 * m.cos(a)))
    ring = ring[shift:] + ring[:shift]
    if reverse:
        ring.reverse()
    ring.append(ring[0])
    return [[p[0], p[1], 50.0, (start + timedelta(seconds=60 * i)).isoformat()] for i, p in enumerate(ring)]


def test_the_same_route_is_found_either_way_round_and_wherever_you_started() -> None:
    from app.trails import insights

    days = [START + timedelta(days=d) for d in range(4)]
    body = {"data": {"workouts": [
        hae_workout("Outdoor Walk", 70, days[0], loop_track(start=days[0])),
        hae_workout("Outdoor Walk", 64, days[1], loop_track(start=days[1], reverse=True)),
        hae_workout("Outdoor Walk", 75, days[2], loop_track(start=days[2], shift=20)),
        hae_workout("Outdoor Walk", 70, days[3], loop_track(lat=-37.48, start=days[3])),  # the same shape 9 km away
    ]}}
    a, b, c, other = service.from_auto_export(body)
    groups = insights.repeats(service.load()["walks"])
    assert len(groups) == 1 and groups[0]["count"] == 3 and other["id"] not in [t["id"] for t in groups[0]["times"]]
    assert groups[0]["fastest"]["id"] == b["id"] and groups[0]["latest"] == c["id"]
    s = service.summary()
    assert {w["id"]: w["repeats"] for w in s["walks"]}[a["id"]] == 3 and s["repeats"][0]["count"] == 3
    d = service.detail(c["id"])
    assert d["repeat"]["count"] == 3 and service.detail(other["id"])["repeat"] is None


def test_trips_away_from_home_with_peaks_and_parks(monkeypatch) -> None:
    from app.trails import insights

    def walk(i, day, lat, lon, cc, country, region, town, **marks):
        return {"id": f"w_{i:012x}", "kind": "hike" if marks.get("peak") else "walk", "start": (START + timedelta(days=day)).isoformat(),
                "start_point": [lat, lon], "km": 5.0, "minutes": 80, "ascent_m": 100, "highest_m": 500 if marks.get("peak") else 40, "name": town,
                "country_code": cc, "country": country, "region": region, "place": f"{town}, {region}, {country}",
                "landmarks": {"locality": town, **marks}, "line": [[lat, lon], [lat + 0.01, lon]]}

    walks = [walk(i, i * 7, -37.56, 143.85, "AU", "Australia", "Victoria", "Ballarat", park="Lake Wendouree") for i in range(6)]
    walks += [walk(10, 60, 35.69, 139.70, "JP", "Japan", "Tokyo", "Shinjuku"), walk(11, 62, 35.66, 139.70, "JP", "Japan", "Tokyo", "Shibuya"),
              walk(12, 90, -38.55, 143.97, "AU", "Australia", "Victoria", "Lorne", peak="Teddys Lookout")]
    trips = insights.trips(walks, [{"id": "abcdef1234", "destination": "Tokyo", "start": (START + timedelta(days=59)).date().isoformat(),
                                    "end": (START + timedelta(days=63)).date().isoformat()}], walks)
    assert [t["name"] for t in trips] == ["Lorne, May 2024", "Tokyo, Japan, May 2024"]
    assert trips[1]["count"] == 2 and trips[1]["travel"]["id"] == "abcdef1234" and "travel" not in trips[0]
    marks = insights.landmarks(walks)
    assert marks["parks"][0] == {**marks["parks"][0], "name": "Lake Wendouree", "count": 6}
    assert marks["peaks"][0]["name"] == "Teddys Lookout" and marks["peaks"][0]["highest_m"] == 500


def test_the_weather_on_each_walk(monkeypatch) -> None:
    from app.trails import weather

    monkeypatch.setenv("SIRISOS_TRAILS_WEATHER", "on")
    (walk,) = service.from_auto_export({"data": {"workouts": [hae_workout("Outdoor Walk", 90)]}})
    hours = [(START.astimezone(timezone.utc).replace(minute=0) + timedelta(hours=h)) for h in range(-2, 4)]
    answer = {"hourly": {"time": [h.strftime("%Y-%m-%dT%H:%M") for h in hours], "temperature_2m": [9, 10, 12, 14, 15, 30],
                         "apparent_temperature": [7, 8, 9, 11, 12, 30], "precipitation": [5, 0, 0.4, 0.8, 0, 9], "weather_code": [65, 3, 61, 3, 2, 95],
                         "wind_speed_10m": [5, 5, 10, 20, 30, 50], "wind_gusts_10m": [9, 9, 20, 41, 50, 90], "relative_humidity_2m": [90, 90, 80, 70, 60, 50]}}
    asked = []

    class Client:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url, params=None):
            asked.append((url, params))
            return type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: answer})()

    monkeypatch.setattr(weather.httpx, "Client", Client)
    assert weather.fill_pending(now=START + timedelta(days=400)) == 1
    w = service.load()["walks"][0]["weather"]
    # 8:00 to 9:30: the hours from 8 to 9, so 12 and 14 degrees, not the storm after
    assert (w["temp_min_c"], w["temp_max_c"], w["rain_mm"], w["gust_kmh"], w["sky"]) == (12, 14, 1.2, 41, "Rain")
    assert asked[0][0] == weather.ARCHIVE and asked[0][1]["latitude"] == -37.8
    assert weather.fill_pending(now=START + timedelta(days=400)) == 0          # looked up once
    rec = service.summary()["weather_records"]
    assert rec["hottest"]["value"] == 14 and rec["wettest"]["value"] == 1.2 and walk["id"] == rec["coldest"]["id"]
