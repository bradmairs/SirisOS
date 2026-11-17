"""A picture for each exercise (9.7): the movement's start and end, from Free
Exercise DB (github.com/yuhonas/free-exercise-db), a public-domain (Unlicense)
set of 873 exercises with two photos each. Its names and ids are bundled
(exercise_images.json); the photos are fetched once, when first shown, and
kept in the data folder (gym-images/), so they work offline after that.

- **The built-in exercises** are matched by hand (CURATED).
- **Yours and imported ones** are matched by name: every word of your name
  should be in its name, the equipment mustn't disagree (a barbell exercise
  never gets a dumbbell picture), and anything too loose gets no picture.
- **You decide**: pick another from the library, use your own photo, or have
  none (GymDoc.images: a library id, "none", or "photo:<file>").
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from app.gym import store

INDEX = Path(__file__).with_name("exercise_images.json")
NONE = "none"

CURATED: dict[str, str | None] = {
    "bench-press": "Barbell_Bench_Press_-_Medium_Grip", "incline-bench-press": "Barbell_Incline_Bench_Press_-_Medium_Grip",
    "decline-bench-press": "Decline_Barbell_Bench_Press", "db-bench-press": "Dumbbell_Bench_Press", "incline-db-press": "Incline_Dumbbell_Press",
    "db-fly": "Dumbbell_Flyes", "cable-crossover": "Cable_Crossover", "pec-deck": "Butterfly", "chest-press-machine": "Leverage_Chest_Press",
    "push-up": "Pushups", "dip": "Parallel_Bar_Dip", "deadlift": "Barbell_Deadlift", "trap-bar-deadlift": "Trap_Bar_Deadlift",
    "barbell-row": "Bent_Over_Barbell_Row", "pendlay-row": "Bent_Over_Barbell_Row", "db-row": "One-Arm_Dumbbell_Row",
    "seated-cable-row": "Seated_Cable_Rows", "lat-pulldown": "Wide-Grip_Lat_Pulldown", "pull-up": "Pullups", "chin-up": "Chin-Up",
    "t-bar-row": "T-Bar_Row_with_Handle", "straight-arm-pulldown": "Straight-Arm_Pulldown", "back-extension": "Hyperextensions_Back_Extensions",
    "shrug": "Barbell_Shrug", "rack-pull": "Rack_Pulls", "overhead-press": "Standing_Military_Press", "db-shoulder-press": "Dumbbell_Shoulder_Press",
    "arnold-press": "Arnold_Dumbbell_Press", "lateral-raise": "Side_Lateral_Raise", "cable-lateral-raise": "Cable_Seated_Lateral_Raise",
    "front-raise": "Front_Dumbbell_Raise", "rear-delt-fly": "Cable_Rear_Delt_Fly", "face-pull": "Face_Pull", "upright-row": "Upright_Barbell_Row",
    "shoulder-press-machine": "Machine_Shoulder_Military_Press", "barbell-curl": "Barbell_Curl", "db-curl": "Dumbbell_Bicep_Curl",
    "hammer-curl": "Hammer_Curls", "preacher-curl": "Preacher_Curl", "cable-curl": "Standing_Biceps_Cable_Curl",
    "incline-db-curl": "Incline_Dumbbell_Curl", "tricep-pushdown": "Triceps_Pushdown",
    "overhead-tricep-extension": "Cable_Rope_Overhead_Triceps_Extension", "skull-crusher": "EZ-Bar_Skullcrusher",
    "close-grip-bench": "Close-Grip_Barbell_Bench_Press", "bench-dip": "Bench_Dips", "wrist-curl": "Palms-Up_Barbell_Wrist_Curl_Over_A_Bench",
    "farmers-carry": "Farmers_Walk", "back-squat": "Barbell_Squat", "front-squat": "Front_Barbell_Squat", "goblet-squat": "Goblet_Squat",
    "leg-press": "Leg_Press", "hack-squat": "Hack_Squat", "leg-extension": "Leg_Extensions", "bulgarian-split-squat": "Split_Squats",
    "walking-lunge": "Barbell_Walking_Lunge", "step-up": "Dumbbell_Step_Ups", "romanian-deadlift": "Romanian_Deadlift",
    "db-romanian-deadlift": "Stiff-Legged_Dumbbell_Deadlift", "lying-leg-curl": "Lying_Leg_Curls", "seated-leg-curl": "Seated_Leg_Curl",
    "good-morning": "Good_Morning", "hip-thrust": "Barbell_Hip_Thrust", "glute-bridge": "Barbell_Glute_Bridge",
    "cable-kickback": "One-Legged_Cable_Kickback", "hip-abduction": "Thigh_Abductor", "standing-calf-raise": "Standing_Calf_Raises",
    "seated-calf-raise": "Seated_Calf_Raise", "plank": "Plank", "side-plank": "Push_Up_to_Side_Plank", "crunch": "Crunches",
    "hanging-leg-raise": "Hanging_Leg_Raise", "cable-crunch": "Cable_Crunch", "ab-wheel": "Barbell_Ab_Rollout_-_On_Knees",
    "russian-twist": "Russian_Twist", "pallof-press": "Pallof_Press", "kb-swing": "One-Arm_Kettlebell_Swings", "clean": "Power_Clean",
    "thruster": "Kettlebell_Thruster", "burpee": None, "treadmill": "Running_Treadmill", "rowing-machine": "Rowing_Stationary",
    "exercise-bike": "Bicycling_Stationary", "elliptical": "Elliptical_Trainer", "stair-climber": "Stairmaster", "jump-rope": "Rope_Jumping",
    "air-bike": "Bicycling_Stationary", "ski-erg": None, "run": "Running_Treadmill", "circuit": None, "sled-push": "Sled_Push",
}

_EQUIPMENT_WORDS = {"barbell": "barbell", "dumbbell": "dumbbell", "cable": "cable", "kettlebell": "kettlebell", "smith": "machine",
                    "machine": "machine", "leverage": "machine", "band": "bands", "ez": "e-z curl bar"}
# 9.71: library entries whose names say something else: its "Air Bike" is a bicycle crunch on the floor, not the bike.
_MISLEADING = frozenset({"Air_Bike"})
_EQUIP_TOKENS = frozenset(_EQUIPMENT_WORDS) | {"bar"}
_SYN = {"db": "dumbbell", "bb": "barbell", "kb": "kettlebell", "pullup": "pull up", "pullups": "pull up", "chinup": "chin up",
        "ohp": "overhead press", "rdl": "romanian deadlift", "tricep": "triceps", "bicep": "biceps", "flye": "fly", "flyes": "fly",
        "flys": "fly", "ext": "extension", "leverage": "machine", "single": "one", "adductor": "adductor", "hip": "hip", "pushdowns": "pushdown", "pushup": "push up", "pushups": "push up", "situp": "sit up"}
_STOP = {"with", "the", "a", "on", "of", "and", "to", "in", "grip", "medium", "standing", "seated", "exercise"}


@lru_cache(maxsize=1)
def library() -> dict[str, Any]:
    data = json.loads(INDEX.read_text())
    return {"source": data["source"], "url": data["images"],
            "by_id": {r[0]: {"id": r[0], "name": r[1], "equipment": r[2], "primary": r[3], "frames": r[4]} for r in data["exercises"]}}


@lru_cache(maxsize=4096)
def _tokens(name: str) -> frozenset[str]:
    n = re.sub(r"[^a-z0-9 ]", " ", name.lower().replace("-", " ").replace("_", " "))
    words = " ".join(_SYN.get(w, w) for w in n.split()).split()
    return frozenset(w[:-1] if w.endswith("s") and len(w) > 3 else w for w in words if w not in _STOP)


def _equipment(tokens: frozenset[str]) -> set[str]:
    return {_EQUIPMENT_WORDS[w] for w in tokens if w in _EQUIPMENT_WORDS}


@lru_cache(maxsize=2048)
def guess(name: str, equipment: str = "") -> str | None:
    """The library exercise that's plainly the same thing, or None."""
    want = _tokens(name)
    if not want:
        return None
    ours = _equipment(want) | ({equipment} if equipment in _EQUIPMENT_WORDS.values() else set())
    best, best_score = None, 0.0
    for e in library()["by_id"].values():
        have = _tokens(e["name"])
        if not have or e["id"] in _MISLEADING:
            continue
        theirs = _equipment(have) | ({e["equipment"]} if e["equipment"] in _EQUIPMENT_WORDS.values() else set())
        if ours and theirs and not ours & theirs:
            continue  # a barbell exercise never gets a dumbbell picture
        # The equipment only rules a picture out (above); the rest of the name has to match.
        core_w, core_h = want - _EQUIP_TOKENS, have - _EQUIP_TOKENS
        if not core_w or not core_h:
            continue
        cover = len(core_w & core_h) / len(core_w)
        if cover < 0.75:
            continue
        score = cover * 0.6 + len(core_w & core_h) / len(core_w | core_h) * 0.4 + (0.05 if ours & theirs else 0)
        if score > best_score:
            best, best_score = e["id"], score
    return best if best_score >= 0.6 else None


def choice(doc: store.GymDoc, exercise_id: str, name: str, equipment: str = "") -> dict[str, Any] | None:
    """What picture an exercise has: yours, the library's, or none."""
    set_ = doc.images.get(exercise_id)
    if set_ == NONE:
        return None
    if set_ and set_.startswith("photo:"):
        return {"source": "yours", "frames": 1}
    lib_id = set_ or (CURATED.get(exercise_id) if exercise_id in CURATED else guess(name, equipment))
    found = library()["by_id"].get(lib_id or "")
    if not found:
        return None
    return {"source": "library", "id": found["id"], "name": found["name"], "frames": max(1, min(2, found["frames"])), "chosen": bool(set_)}


def search(q: str, limit: int = 12) -> list[dict[str, Any]]:
    want = _tokens(q)
    if not want:
        return []
    scored = []
    for e in library()["by_id"].values():
        have = _tokens(e["name"])
        hit = len(want & have)
        if hit:
            scored.append((hit / len(want) + hit / max(1, len(have)) * 0.2, e))
    scored.sort(key=lambda t: -t[0])
    return [{"id": e["id"], "name": e["name"], "equipment": e["equipment"]} for _, e in scored[:limit]]


def image_dir() -> Path:
    d = store.photo_dir().parent / "gym-images"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def library_file(lib_id: str, frame: int, client: httpx.AsyncClient | None = None) -> Path | None:
    """The library photo on disk, fetched the first time it's wanted."""
    if lib_id not in library()["by_id"] or frame not in (0, 1):
        return None
    path = image_dir() / re.sub(r"[^A-Za-z0-9_.-]", "_", lib_id) / f"{frame}.jpg"
    if path.is_file():
        return path
    url = library()["url"].format(id=lib_id, n=frame)
    own = client is None
    client = client or httpx.AsyncClient(timeout=15.0, follow_redirects=True)
    try:
        r = await client.get(url)
    except httpx.HTTPError:
        return None
    finally:
        if own:
            await client.aclose()
    if r.status_code != 200 or not r.headers.get("content-type", "image/jpeg").startswith("image/"):
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)
    return path
