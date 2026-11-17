"""9.7: a picture for each exercise, from a public-domain library, yours, or none."""

from __future__ import annotations

from pathlib import Path

from app.gym import images, store
from tests.test_gym import AUTH, client  # noqa: F401 - the fixture


def test_names_match_carefully():
    assert images.guess("Machine Chest Press", "machine") == "Leverage_Chest_Press"
    assert images.guess("Single Arm Dumbbell Row", "dumbbell") == "One-Arm_Dumbbell_Row"
    assert images.guess("Cable Tricep Pushdown", "cable") == "Triceps_Pushdown"
    assert images.guess("Barbell Lunge", "barbell") == "Barbell_Lunge"
    assert images.guess("Barbell Shoulder Press", "barbell") != "Dumbbell_Shoulder_Press"   # never the other equipment
    assert images.guess("Zzz Mystery Move", "other") is None
    # 9.71: the library's "Air Bike" is a crunch on the floor; the bike is the stationary bike.
    assert images.guess("Air Bike", "other") is None and images.CURATED["air-bike"] == "Bicycling_Stationary"
    assert all(v is None or v in images.library()["by_id"] for v in images.CURATED.values())


def test_an_exercise_shows_its_picture_and_you_can_change_it(client, monkeypatch, tmp_path):  # noqa: F811
    fetched = []

    async def fake_file(lib_id: str, frame: int, client=None) -> Path:
        fetched.append((lib_id, frame))
        p = tmp_path / f"{lib_id}-{frame}.jpg"
        p.write_bytes(b"\xff\xd8jpeg")
        return p

    monkeypatch.setattr(images, "library_file", fake_file)
    got = client.get("/api/v1/gym/exercises/bench-press", headers=AUTH).json()["image"]
    assert got == {"source": "library", "id": "Barbell_Bench_Press_-_Medium_Grip", "name": "Barbell Bench Press - Medium Grip", "frames": 2, "chosen": False}
    r = client.get("/api/v1/gym/exercises/bench-press/image?frame=1", headers=AUTH)
    assert r.status_code == 200 and r.content == b"\xff\xd8jpeg" and fetched == [("Barbell_Bench_Press_-_Medium_Grip", 1)]
    assert next(e for e in client.get("/api/v1/gym", headers=AUTH).json()["exercises"] if e["id"] == "bench-press")["image"] is True

    # Another from the library, none, your own photo, and back to automatic.
    assert client.get("/api/v1/gym/image-search?q=close grip bench", headers=AUTH).json()["results"][0]["id"] == "Close-Grip_Barbell_Bench_Press"
    pick = client.put("/api/v1/gym/exercises/bench-press/image", headers=AUTH, json={"library_id": "Close-Grip_Barbell_Bench_Press"}).json()
    assert pick["image"]["id"] == "Close-Grip_Barbell_Bench_Press" and pick["image"]["chosen"]
    assert client.put("/api/v1/gym/exercises/bench-press/image", headers=AUTH, json={"library_id": "Nope"}).status_code == 422
    assert client.put("/api/v1/gym/exercises/bench-press/image", headers=AUTH, json={"none": True}).json()["image"] is None
    assert client.get("/api/v1/gym/exercises/bench-press/image", headers=AUTH).status_code == 404
    up = client.post("/api/v1/gym/exercises/bench-press/photo", headers=AUTH, files={"file": ("me.jpg", b"\xff\xd8mine", "image/jpeg")}).json()
    assert up["image"] == {"source": "yours", "frames": 1}
    assert client.get("/api/v1/gym/exercises/bench-press/image", headers=AUTH).content == b"\xff\xd8mine"
    own = store.load().images["bench-press"].split(":", 1)[1]
    assert client.put("/api/v1/gym/exercises/bench-press/image", headers=AUTH, json={}).json()["image"]["id"] == "Barbell_Bench_Press_-_Medium_Grip"
    assert not (store.photo_dir() / own).exists()   # your old photo goes with it
