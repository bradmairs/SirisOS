"""Gym data (6.5): your own exercises, routines, finished sessions and settings,
in one JSON file (SIRISOS_GYM_PATH, gym.json in the data folder).

A session in progress lives on the phone (gyms are often out of signal) and
is sent when it's finished; sending the same one again replaces it, so a
retry from the offline outbox never doubles it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services import json_store

Kind = Literal["weight", "bodyweight", "time", "cardio"]


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CustomExercise(BaseModel):
    id: str = Field(default_factory=lambda: "my-" + new_id(), max_length=60)
    name: str = Field(min_length=1, max_length=80)
    primary: str = Field(max_length=20)
    secondary: list[str] = Field(default_factory=list, max_length=6)
    equipment: str = Field(default="other", max_length=20)
    kind: Kind = "weight"
    custom: bool = True


class SetLog(BaseModel):
    reps: int | None = Field(default=None, ge=0, le=1000)
    weight: float | None = Field(default=None, ge=0, le=2000)
    seconds: int | None = Field(default=None, ge=0, le=86400)
    km: float | None = Field(default=None, ge=0, le=1000)
    done: bool = True
    type: Literal["normal", "warmup", "drop", "failure"] = "normal"
    rpe: float | None = Field(default=None, ge=1, le=10)
    at: str | None = Field(default=None, max_length=40)  # when it was ticked done (6.96), to line it up with the Watch's heart rate


class EntryLog(BaseModel):
    exercise: str = Field(max_length=60)
    sets: list[SetLog] = Field(default_factory=list, max_length=40)
    note: str = Field(default="", max_length=500)
    group: str | None = Field(default=None, max_length=2)  # superset letter (6.7): rest comes after the group


class Session(BaseModel):
    id: str = Field(default_factory=new_id, max_length=40)
    title: str = Field(default="Workout", max_length=80)
    started_at: str = Field(max_length=40)
    ended_at: str | None = Field(default=None, max_length=40)
    routine_id: str | None = Field(default=None, max_length=40)
    day: int | None = Field(default=None, ge=0, le=13)
    entries: list[EntryLog] = Field(default_factory=list, max_length=40)
    note: str = Field(default="", max_length=2000)
    bodyweight: float | None = Field(default=None, ge=0, le=500)
    gym: str | None = Field(default=None, max_length=40)  # which gym profile (6.7)
    deload: bool = False  # a lighter session on purpose (6.8): no records, not a stall


Progression = Literal["double", "linear", "percent"]


class PlanExercise(BaseModel):
    exercise: str = Field(max_length=60)
    sets: int = Field(default=3, ge=1, le=20)
    reps: str = Field(default="8-12", max_length=12, pattern=r"^\d{1,3}(-\d{1,3})?$")
    rest_s: int = Field(default=90, ge=0, le=900)
    note: str = Field(default="", max_length=200)
    group: str | None = Field(default=None, max_length=2)  # superset or circuit letter (6.7)
    # 6.7: double = reach the top of the range, then add; linear = add every
    # session you hit the reps (two misses: back off 10%); percent = a share of
    # your training max (90% of your best recent estimated 1RM), one per set.
    progression: Progression = "double"
    percents: list[float] = Field(default_factory=list, max_length=20)


class RoutineDay(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    exercises: list[PlanExercise] = Field(default_factory=list, max_length=20)
    # Days of the week this is done on (6.94): 0 = Monday ... 6 = Sunday. Empty: in turn, after the last one done.
    weekdays: list[int] = Field(default_factory=list, max_length=7)

    @field_validator("weekdays")
    @classmethod
    def _weekdays(cls, v: list[int]) -> list[int]:
        return sorted({d for d in v if 0 <= d <= 6})


class Routine(BaseModel):
    id: str = Field(default_factory=new_id, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    days: list[RoutineDay] = Field(default_factory=list, max_length=14)
    note: str = Field(default="", max_length=500)
    active: bool = False


PLATES = [25, 20, 15, 10, 5, 2.5, 1.25]


class GymProfile(BaseModel):
    """A gym and what it has (6.7): the bar, the plates (pairs), the dumbbells
    on the rack (empty: any weight), and the machine stack step."""
    id: str = Field(default_factory=new_id, max_length=40)
    name: str = Field(default="Home", min_length=1, max_length=40)
    bar: float = Field(default=20, ge=0, le=60)
    plates: list[float] = Field(default_factory=lambda: list(PLATES), max_length=16)
    dumbbells: list[float] = Field(default_factory=list, max_length=80)
    stack_step: float | None = Field(default=None, gt=0, le=20)


class WarmupStep(BaseModel):
    percent: float = Field(ge=0, le=1)
    reps: int = Field(ge=1, le=20)


class Settings(BaseModel):
    """`bar` and `plates` are the current gym's (kept for everything that reads them)."""
    unit: Literal["kg"] = "kg"  # SI only (6.62): a gym.json kept in lb is converted on load
    bar: float = Field(default=20, ge=0, le=60)
    plates: list[float] = Field(default_factory=lambda: list(PLATES), max_length=16)
    increment: float = Field(default=2.5, gt=0, le=20)
    rest_s: int = Field(default=90, ge=0, le=900)
    gyms: list[GymProfile] = Field(default_factory=list, max_length=10)
    current_gym: str | None = Field(default=None, max_length=40)
    warmups: bool = True
    warmup_steps: list[WarmupStep] = Field(default_factory=lambda: [WarmupStep(percent=0.4, reps=5), WarmupStep(percent=0.6, reps=3),
                                                                     WarmupStep(percent=0.8, reps=2)], max_length=8)
    muscle_targets: dict[str, list[float]] = Field(default_factory=dict)  # muscle -> [low, high] sets a week (6.8)
    deload_until: str | None = Field(default=None, max_length=10)  # a deload week runs to this day (6.8)
    # iPhone Shortcuts to run when a workout starts and finishes (6.92), e.g. one that starts the Watch workout.
    shortcut_start: str = Field(default="", max_length=80)
    shortcut_finish: str = Field(default="", max_length=80)
    # Protein (6.93): grams per kg of bodyweight, on rest days and training days.
    protein_rest: float = Field(default=1.6, ge=0.5, le=3.5)
    protein_training: float = Field(default=2.0, ge=0.5, le=3.5)

    @model_validator(mode="after")
    def _current(self) -> "Settings":
        if not self.gyms:  # before 6.7: one gym, from the bar and plates
            self.gyms = [GymProfile(id="home", name="Home", bar=self.bar, plates=list(self.plates))]
        gym = next((g for g in self.gyms if g.id == self.current_gym), None) or self.gyms[0]
        self.current_gym, self.bar, self.plates = gym.id, gym.bar, list(gym.plates)
        return self

    def gym(self, gym_id: str | None = None) -> GymProfile:
        return next((g for g in self.gyms if g.id == (gym_id or self.current_gym)), self.gyms[0])


class Measurement(BaseModel):
    """Body measurements in cm (6.9); any can be left out."""
    id: str = Field(default_factory=new_id, max_length=40)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    waist: float | None = Field(default=None, gt=0, le=300)
    chest: float | None = Field(default=None, gt=0, le=300)
    hips: float | None = Field(default=None, gt=0, le=300)
    neck: float | None = Field(default=None, gt=0, le=100)
    arm: float | None = Field(default=None, gt=0, le=100)
    thigh: float | None = Field(default=None, gt=0, le=150)
    calf: float | None = Field(default=None, gt=0, le=100)
    note: str = Field(default="", max_length=200)


class Photo(BaseModel):
    """A progress photo (6.9): kept as a file next to gym.json, never sent anywhere."""
    id: str = Field(default_factory=new_id, max_length=40)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    pose: Literal["front", "side", "back", "other"] = "front"
    note: str = Field(default="", max_length=200)
    file: str = Field(max_length=80)


class GymDoc(BaseModel):
    exercises: list[CustomExercise] = Field(default_factory=list)
    routines: list[Routine] = Field(default_factory=list)
    sessions: list[Session] = Field(default_factory=list)
    settings: Settings = Field(default_factory=Settings)
    measurements: list[Measurement] = Field(default_factory=list)
    photos: list[Photo] = Field(default_factory=list)
    cleaned_empty: bool = True  # the one-time tidy of exercises with no data (6.95); False only in files from before it
    import_times_local: bool = True  # imported start times moved from UTC to local (6.96); False only in files from before it


def _path():
    return json_store.data_path("SIRISOS_GYM_PATH", "gym.json")


def photo_dir():
    d = _path().parent / "gym-photos"
    d.mkdir(parents=True, exist_ok=True)
    return d


LB = 0.45359237


def to_si(raw: dict) -> dict:
    """A gym kept in pounds (6.5-6.61 allowed it) becomes kilograms: every
    logged weight, the bar, the plates and the increment."""
    settings = raw.get("settings") or {}
    if settings.get("unit") != "lb":
        return raw
    kg = lambda v: round(v * LB, 2) if isinstance(v, (int, float)) else v  # noqa: E731
    settings.update(unit="kg", bar=kg(settings.get("bar", 45)), increment=kg(settings.get("increment", 5)),
                    plates=[kg(p) for p in settings.get("plates") or []])
    for s in raw.get("sessions") or []:
        for e in s.get("entries") or []:
            for x in e.get("sets") or []:
                x["weight"] = kg(x.get("weight"))
        s["bodyweight"] = kg(s.get("bodyweight"))
    return raw


def _has_data(x: "SetLog") -> bool:
    return bool(x.weight or x.reps or x.seconds or x.km)


def clean_empty(doc: "GymDoc") -> dict[str, Any]:
    """Exercises with nothing logged (6.95). An early JEFIT import read the
    export's table of workout sessions as exercises: each session's name
    became an exercise of yours with empty sets. This takes out sets with no
    data, entries left with none, and your own exercises that have no data
    anywhere and aren't in a routine. Workouts are never removed."""
    entries = 0
    for s in doc.sessions:
        kept = []
        for e in s.entries:
            e.sets = [x for x in e.sets if _has_data(x)]
            if e.sets:
                kept.append(e)
            else:
                entries += 1
        s.entries = kept
    used = {e.exercise for s in doc.sessions for e in s.entries}
    in_routines = {p.exercise for r in doc.routines for d in r.days for p in d.exercises}
    gone = [e for e in doc.exercises if e.id not in used and e.id not in in_routines]
    doc.exercises = [e for e in doc.exercises if e not in gone]
    return {"entries_removed": entries, "exercises_removed": len(gone), "names": [e.name for e in gone][:50], "sessions_kept": len(doc.sessions)}


def local_import_times(doc: "GymDoc") -> dict[str, Any]:
    """Imported workouts filed by UTC (6.96). JEFIT's timestamps are UTC, and
    the importer before 6.96 kept them as if local, so a morning workout in
    Melbourne was filed under the day before. When most imported start times
    fall between 6pm and 4am (the sign they're UTC), each one with a time
    (07:00 is the importer's stand-in for "no time") moves to local time and
    its local day; its id becomes import-<that day>, joining a workout already
    there. Nothing is lost."""
    from app.tasks.service import zone

    imported = [s for s in doc.sessions if s.id.startswith("import-") and "+" not in s.started_at[10:] and not s.started_at.endswith("Z")
                and s.started_at[11:19] not in ("", "07:00:00")]
    if not imported:
        return {"moved": 0, "utc": False}
    night = sum(1 for s in imported if int(s.started_at[11:13] or 0) >= 18 or int(s.started_at[11:13] or 0) < 4)
    if night < 0.7 * len(imported):
        return {"moved": 0, "utc": False}
    tz = zone()
    moving = {id(s) for s in imported}
    placed: dict[str, Session] = {s.id: s for s in doc.sessions if id(s) not in moving}  # sessions that stay where they are
    keep: list[Session] = [s for s in doc.sessions if id(s) not in moving]
    for s in imported:
        local = datetime.fromisoformat(s.started_at).replace(tzinfo=timezone.utc).astimezone(tz).replace(tzinfo=None)
        s.started_at = local.isoformat(timespec="seconds")
        s.id = f"import-{local.date().isoformat().replace('-', '')}"
        if s.id in placed:  # another workout already on that day: join it
            target = placed[s.id]
            target.entries = (target.entries + s.entries)[:40]
            target.started_at = min(target.started_at, s.started_at)
        else:
            placed[s.id] = s
            keep.append(s)
    doc.sessions = keep
    moved = len(imported)
    return {"moved": moved, "utc": True}


def backup(tag: str) -> None:
    p = _path()
    if p.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        (p.parent / f"gym.{tag}.{stamp}.json").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")


def load() -> GymDoc:
    raw = json_store.read(_path(), None)
    if not isinstance(raw, dict):
        return GymDoc()
    doc = GymDoc.model_validate({"cleaned_empty": False, "import_times_local": False, **to_si(raw)})
    if not doc.import_times_local:
        moved = local_import_times(doc)
        doc.import_times_local = True
        if moved["moved"]:
            backup("before-local-times")
        save(doc)
    if not doc.cleaned_empty:
        # Once (6.95): take out the exercises an early import made from workout names. A copy is kept first.
        out = clean_empty(doc)
        doc.cleaned_empty = True
        if out["entries_removed"] or out["exercises_removed"]:
            backup("before-cleanup")
        save(doc)
    return doc


def save(doc: GymDoc) -> GymDoc:
    doc.sessions.sort(key=lambda s: s.started_at)
    json_store.write(_path(), doc.model_dump())
    return doc
