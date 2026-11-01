"""Programme builder (6.9): a routine drafted from a goal, for you to edit.

Say it in words ("4 days, hypertrophy, bad left shoulder, 60 minutes at
home with dumbbells") or pick the options. The split follows the days a
week: 2-3 full body, 4 upper/lower, 5 upper/lower/push/pull/legs, 6 push,
pull, legs twice. Each day is built from movement patterns (squat, hinge,
push, pull and the smaller muscles), each filled from the library with the
first exercise that suits your equipment and stays off an injured area
(shoulder, elbow, wrist, lower back, knee), varied across the week. Sets,
reps and rest follow the goal (strength 3-6 reps on the main lifts, muscle
6-12, general 8-12), and the day is trimmed to fit the minutes you have.
It's a starting point, saved only when you save it.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.gym import library
from app.gym.store import PlanExercise, Routine, RoutineDay

Goal = Literal["strength", "muscle", "general"]
Equipment = Literal["gym", "dumbbells", "bodyweight"]
AREAS = ("shoulder", "elbow", "wrist", "lower back", "knee")

PATTERNS: dict[str, list[str]] = {
    "squat": ["back-squat", "front-squat", "hack-squat", "leg-press", "goblet-squat", "bulgarian-split-squat"],
    "hinge": ["deadlift", "trap-bar-deadlift", "romanian-deadlift", "db-romanian-deadlift", "hip-thrust", "kb-swing", "glute-bridge"],
    "hpush": ["bench-press", "db-bench-press", "chest-press-machine", "incline-db-press", "push-up"],
    "vpush": ["overhead-press", "db-shoulder-press", "shoulder-press-machine", "arnold-press"],
    "hpull": ["barbell-row", "seated-cable-row", "db-row", "t-bar-row", "pendlay-row"],
    "vpull": ["pull-up", "lat-pulldown", "chin-up", "straight-arm-pulldown"],
    "incline": ["incline-bench-press", "incline-db-press", "cable-crossover", "db-fly", "push-up"],
    "single-leg": ["bulgarian-split-squat", "walking-lunge", "step-up", "leg-extension", "goblet-squat", "leg-press"],
    "hamstring": ["lying-leg-curl", "seated-leg-curl", "romanian-deadlift", "db-romanian-deadlift", "glute-bridge"],
    "delts": ["lateral-raise", "cable-lateral-raise", "face-pull", "rear-delt-fly"],
    "rear": ["face-pull", "rear-delt-fly", "lateral-raise"],
    "biceps": ["db-curl", "hammer-curl", "cable-curl", "incline-db-curl", "barbell-curl"],
    "triceps": ["tricep-pushdown", "overhead-tricep-extension", "skull-crusher", "bench-dip", "close-grip-bench"],
    "calves": ["standing-calf-raise", "seated-calf-raise"],
    "core": ["plank", "hanging-leg-raise", "pallof-press", "cable-crunch", "ab-wheel", "side-plank", "crunch"],
}
MAIN = {"squat", "hinge", "hpush", "vpush", "hpull", "vpull"}
# Exercises that load an injured area.
HARD_ON: dict[str, set[str]] = {
    "shoulder": {"overhead-press", "arnold-press", "upright-row", "dip", "bench-dip", "bench-press", "incline-bench-press", "decline-bench-press",
                 "close-grip-bench", "shoulder-press-machine", "db-shoulder-press", "front-raise", "push-up", "thruster", "clean"},
    "elbow": {"skull-crusher", "close-grip-bench", "overhead-tricep-extension", "preacher-curl", "barbell-curl", "chin-up", "dip", "bench-dip"},
    "wrist": {"front-squat", "barbell-curl", "wrist-curl", "push-up", "clean", "skull-crusher", "thruster"},
    "lower back": {"deadlift", "rack-pull", "barbell-row", "pendlay-row", "good-morning", "back-squat", "front-squat", "romanian-deadlift",
                   "t-bar-row", "clean", "kb-swing", "back-extension", "trap-bar-deadlift"},
    "knee": {"back-squat", "front-squat", "hack-squat", "walking-lunge", "bulgarian-split-squat", "step-up", "leg-extension", "thruster",
             "burpee", "jump-rope", "goblet-squat"},
}
EQUIPMENT_OK: dict[str, set[str]] = {
    "gym": set(library.EQUIPMENT),
    "dumbbells": {"dumbbell", "bodyweight", "kettlebell", "band", "other"},
    "bodyweight": {"bodyweight", "other"},
}
UNLOADED_OK = {"bulgarian-split-squat", "walking-lunge", "step-up", "glute-bridge", "goblet-squat"}  # fine with no weight
SPLITS: dict[int, list[tuple[str, list[str]]]] = {
    2: [("Full body A", ["squat", "hpush", "hpull", "hamstring", "delts", "core"]),
        ("Full body B", ["hinge", "vpush", "vpull", "single-leg", "biceps", "triceps"])],
    3: [("Full body A", ["squat", "hpush", "hpull", "delts", "core"]),
        ("Full body B", ["hinge", "vpush", "vpull", "single-leg", "biceps"]),
        ("Full body C", ["squat", "incline", "hpull", "hamstring", "triceps", "calves"])],
    4: [("Upper 1", ["hpush", "hpull", "vpush", "vpull", "biceps", "triceps"]),
        ("Lower 1", ["squat", "hinge", "single-leg", "calves", "core"]),
        ("Upper 2", ["incline", "vpull", "hpull", "delts", "triceps", "biceps"]),
        ("Lower 2", ["hinge", "squat", "hamstring", "calves", "core"])],
    5: [("Upper", ["hpush", "hpull", "vpush", "vpull", "biceps", "triceps"]),
        ("Lower", ["squat", "hinge", "single-leg", "calves", "core"]),
        ("Push", ["incline", "vpush", "hpush", "delts", "triceps"]),
        ("Pull", ["vpull", "hpull", "rear", "biceps", "core"]),
        ("Legs", ["hinge", "squat", "hamstring", "single-leg", "calves"])],
    6: [("Push A", ["hpush", "vpush", "incline", "delts", "triceps"]),
        ("Pull A", ["hinge", "vpull", "hpull", "rear", "biceps"]),
        ("Legs A", ["squat", "hamstring", "single-leg", "calves", "core"]),
        ("Push B", ["vpush", "incline", "hpush", "delts", "triceps"]),
        ("Pull B", ["vpull", "hpull", "rear", "biceps", "core"]),
        ("Legs B", ["hinge", "squat", "single-leg", "calves", "core"])],
}
DOSE: dict[str, dict[str, tuple[int, str, int]]] = {  # goal -> main / accessory: sets, reps, rest
    "strength": {"main": (4, "3-6", 180), "acc": (3, "6-10", 90)},
    "muscle": {"main": (3, "6-10", 120), "acc": (3, "10-15", 60)},
    "general": {"main": (3, "8-12", 90), "acc": (2, "10-15", 60)},
}


class BuildRequest(BaseModel):
    text: str = Field(default="", max_length=500)
    days: int | None = Field(default=None, ge=2, le=6)
    goal: Goal | None = None
    minutes: int | None = Field(default=None, ge=20, le=150)
    equipment: Equipment | None = None
    avoid: list[str] = Field(default_factory=list, max_length=5)


def read(text: str) -> dict[str, Any]:
    """What a sentence says: days, goal, minutes, equipment and areas to spare."""
    t = text.lower()
    out: dict[str, Any] = {}
    if m := re.search(r"\b([2-6])\s*(?:x\s*)?(?:days?|sessions?|times)\b", t):
        out["days"] = int(m.group(1))
    elif m := re.search(r"\b(two|three|four|five|six)\s+(?:days?|sessions?|times)", t):
        out["days"] = ["two", "three", "four", "five", "six"].index(m.group(1)) + 2
    if re.search(r"hypertroph|muscle|size|bulk|bodybuild|aesthetic", t):
        out["goal"] = "muscle"
    elif re.search(r"strength|stronger|strong|powerlift|1rm|max", t):
        out["goal"] = "strength"
    elif re.search(r"general|fitness|health|tone|fat|lean", t):
        out["goal"] = "general"
    if m := re.search(r"(\d{2,3})\s*(?:min|minutes|mins)\b", t):
        out["minutes"] = max(20, min(150, int(m.group(1))))
    elif re.search(r"\b(an|1|one)\s+hour\b", t):
        out["minutes"] = 60
    if re.search(r"no equipment|bodyweight|body weight|calisthenics", t):
        out["equipment"] = "bodyweight"
    elif re.search(r"dumbbell|at home|home gym|home", t):
        out["equipment"] = "dumbbells"
    elif re.search(r"\bgym\b", t):
        out["equipment"] = "gym"
    avoid = []
    for area, words in (("shoulder", r"shoulder|rotator"), ("elbow", r"elbow|tennis elbow|golfer"), ("wrist", r"wrist"),
                        ("lower back", r"lower back|back pain|bad back|sore back|disc|spine"), ("knee", r"knee|acl|meniscus|patella")):
        if re.search(words, t):
            avoid.append(area)
    if avoid:
        out["avoid"] = avoid
    return out


def _ok(ex_id: str, equipment: str, avoid: list[str]) -> bool:
    ex = library.BUILTIN.get(ex_id)
    if not ex or any(ex_id in HARD_ON.get(a, set()) for a in avoid):
        return False
    return ex["equipment"] in EQUIPMENT_OK[equipment] or (equipment != "gym" and ex_id in UNLOADED_OK)


def build(req: BuildRequest) -> dict[str, Any]:
    said = read(req.text)
    days = req.days or said.get("days") or 3
    goal = req.goal or said.get("goal") or "general"
    minutes = req.minutes or said.get("minutes") or 60
    equipment = req.equipment or said.get("equipment") or "gym"
    avoid = [a for a in dict.fromkeys([*(req.avoid or []), *said.get("avoid", [])]) if a in AREAS]
    used: dict[str, int] = {}
    out_days = []
    skipped: list[str] = []
    for name, slots in SPLITS[days]:
        picks: list[PlanExercise] = []
        for i, slot in enumerate(slots):
            options = [e for e in PATTERNS[slot] if _ok(e, equipment, avoid) and e not in {p.exercise for p in picks}]
            if not options:
                skipped.append(slot)
                continue
            choice = min(options, key=lambda e: (used.get(e, 0), PATTERNS[slot].index(e)))
            used[choice] = used.get(choice, 0) + 1
            role = "main" if slot in MAIN and i < 3 else "acc"
            sets, reps, rest = DOSE[goal][role]
            if library.BUILTIN[choice]["kind"] == "time":
                reps = "30-60"
            progression = "linear" if goal == "strength" and role == "main" and library.BUILTIN[choice]["equipment"] == "barbell" else "double"
            picks.append(PlanExercise(exercise=choice, sets=sets, reps=reps if progression == "double" else reps.split("-")[0], rest_s=rest,
                                      progression=progression))
        while len(picks) > 3 and _minutes(picks) > minutes:
            picks.pop()
        out_days.append(RoutineDay(name=name, exercises=picks))
    labels = {"strength": "strength", "muscle": "muscle", "general": "general fitness"}
    note = (f"{days} days a week for {labels[goal]}, about {minutes} minutes, {'in a gym' if equipment == 'gym' else 'with ' + equipment}."
            + (f" Spares the {', '.join(avoid)}: no exercises that load {'it' if len(avoid) == 1 else 'them'} hard; stop anything that hurts." if avoid else ""))
    routine = Routine(id="", name=f"{labels[goal].capitalize()}, {days} days", days=out_days, note=note[:500], active=False)
    return {"routine": routine.model_dump(), "chosen": {"days": days, "goal": goal, "minutes": minutes, "equipment": equipment, "avoid": avoid},
            "read": said, "note": note}


def _minutes(picks: list[PlanExercise]) -> float:
    return 6 + sum(p.sets * (p.rest_s + 45) / 60 for p in picks)
