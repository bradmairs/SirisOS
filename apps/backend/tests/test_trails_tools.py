"""12.5: SirisTrails photos, GPX, trimming and joining."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.entrypoint import app
from app.trails import service, tools
from tests.test_hub import AUTH
from tests.test_trails import START, folder, hae_workout, track  # noqa: F401 - the fixture keeps each test in its own folder

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200


def one(minutes=75, start=START, n=40):
    (walk,) = service.from_auto_export({"data": {"workouts": [hae_workout("Outdoor Walk", minutes, start, track(n=n, start=start))]}})
    return walk


def test_photos_go_on_the_route_where_and_when_they_were_taken() -> None:
    walk = one()
    c = TestClient(app)
    # 10 minutes in, no GPS: the route point 10 minutes in (20 points of 30 s)
    taken = (START + timedelta(minutes=10)).replace(tzinfo=None).isoformat()  # EXIF's local time without an offset
    r = c.post(f"/api/v1/trails/{walk['id']}/photos", headers=AUTH, files={"photo": ("a.jpg", JPEG, "image/jpeg"), "thumb": ("t.jpg", JPEG, "image/jpeg")},
               data={"taken": taken, "w": "2048", "h": "1536"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["at"] == [round(-37.8 + 20 * 0.001, 6), 145.0] and 2.1 < p["km"] < 2.3
    # with GPS: that spot
    r = c.post(f"/api/v1/trails/{walk['id']}/photos", headers=AUTH, files={"photo": ("b.jpg", JPEG), "thumb": ("t.jpg", JPEG)},
               data={"lat": "-37.795", "lon": "145.0001"})
    assert r.json()["at"] == [-37.795, 145.0001] and r.json()["km"] < 1
    # a day later, no GPS: kept, but not on the map
    later = (START + timedelta(days=1)).isoformat()
    r = c.post(f"/api/v1/trails/{walk['id']}/photos", headers=AUTH, files={"photo": ("c.jpg", JPEG), "thumb": ("t.jpg", JPEG)}, data={"taken": later})
    assert r.json()["at"] is None
    photos = service.detail(walk["id"])["photos"]
    assert [x["km"] is None for x in photos] == [False, False, True] and photos[0]["km"] < photos[1]["km"]   # in order along the route
    got = c.get(f"/api/v1/trails/{walk['id']}/photos/{p['id']}?thumb=true", headers=AUTH)
    assert got.status_code == 200 and got.content == JPEG
    assert c.post(f"/api/v1/trails/{walk['id']}/photos", headers=AUTH, files={"photo": ("x.png", b"\x89PNG"), "thumb": ("t.jpg", JPEG)}).status_code == 422
    assert c.delete(f"/api/v1/trails/{walk['id']}/photos/{p['id']}", headers=AUTH).json() == {"ok": True}
    assert c.get(f"/api/v1/trails/{walk['id']}/photos/{p['id']}", headers=AUTH).status_code == 404
    assert c.get(f"/api/v1/trails/{walk['id']}/photos/..%2F..%2Findex", headers=AUTH).status_code in (404, 422)
    c.delete(f"/api/v1/trails/{walk['id']}", headers=AUTH)
    assert not tools._photo_dir(walk["id"]).exists()


def test_gpx_with_or_without_the_ends_near_home() -> None:
    # Home is where most walks start: five walks from the same spot, then the one to export
    for d in range(5):
        one(start=START + timedelta(days=d + 1))
    walk = one(start=START + timedelta(days=10))
    c = TestClient(app)
    full = c.get(f"/api/v1/trails/{walk['id']}/gpx", headers=AUTH)
    assert full.status_code == 200 and full.headers["content-type"].startswith("application/gpx+xml")
    assert full.text.count("<trkpt") == 40 and "<ele>" in full.text and "<time>2024-03-12T" in full.text
    hidden = c.get(f"/api/v1/trails/{walk['id']}/gpx?hide_home=true", headers=AUTH).text
    assert hidden.count("<trkpt") == 40 - 4                                    # the first 400 m (4 points ~111 m apart) left off
    assert 'lat="-37.800000"' not in hidden


def test_trim_keeps_the_original_and_join_can_be_split_again() -> None:
    walk = one(n=40)
    c = TestClient(app)
    r = c.post(f"/api/v1/trails/{walk['id']}/trim", headers=AUTH, json={"from_km": 0.5, "to_km": 3.0})
    assert r.status_code == 200 and r.json()["trimmed"] == [0.5, 3.0]
    assert 2.3 < r.json()["km"] < 2.6 and r.json()["minutes"] < walk["minutes"]
    assert c.post(f"/api/v1/trails/{walk['id']}/trim", headers=AUTH, json={"from_km": 3, "to_km": 1}).status_code == 422
    back = c.delete(f"/api/v1/trails/{walk['id']}/trim", headers=AUTH).json()
    assert "trimmed" not in back and back["km"] == walk["km"]

    from app.trails import service as s

    # 40 minutes later: the same walk, restarted (added directly: a 30 minute walk isn't kept on its own)
    later = s.add(kind="walk", start=START + timedelta(minutes=40), end=START + timedelta(minutes=70),
                  points=[[p[0] + 0.05, p[1], p[2], (START + timedelta(minutes=40, seconds=30 * i)).timestamp()] for i, p in enumerate(track(n=20))])
    joined = c.post(f"/api/v1/trails/{walk['id']}/join", headers=AUTH, json={"other": later["id"]}).json()
    assert len(service.load()["walks"]) == 1 and joined["joined"] == [later["id"]] and joined["minutes"] > walk["minutes"]
    split = c.delete(f"/api/v1/trails/{walk['id']}/join", headers=AUTH).json()
    assert len(service.load()["walks"]) == 2 and split["km"] == walk["km"] and service.detail(later["id"])["km"] == later["km"]
    far = s.add(kind="walk", start=START + timedelta(days=3), end=None, points=[[p[0], p[1], p[2], None] for p in track(n=10)])
    assert c.post(f"/api/v1/trails/{walk['id']}/join", headers=AUTH, json={"other": far["id"]}).status_code == 422
