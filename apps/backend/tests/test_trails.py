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

    answers = iter([Fake({"elements": [road, park]}), Fake({"address": {"suburb": "Kaiapoi", "state": "Canterbury", "country": "New Zealand"}})])
    monkeypatch.setattr(places, "_polite", lambda *a, **k: next(answers))
    pts = [[p[0], p[1], 10.0, None] for p in route] + [[route[0][0], route[0][1], 10.0, None]]
    info = places.describe(pts, "walk")
    assert info["name"] == "Abel Tasman National Park" and info["place"] == "Kaiapoi, Canterbury, New Zealand" and info["loop"]
    answers = iter([Fake({"elements": []}), Fake({"address": {"suburb": "Kaiapoi", "state": "Canterbury", "country": "New Zealand"}})])
    assert places.describe(pts, "walk")["name"] == "Kaiapoi loop"


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
