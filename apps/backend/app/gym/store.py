"""Gym data (6.5): your own exercises, routines, finished sessions and settings,
in one JSON file (SIRISOS_GYM_PATH, gym.json in the data folder).

A session in progress lives on the phone (gyms are often out of signal) and
is sent when it's finished; sending the same one again replaces it, so a
retry from the offline outbox never doubles it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator

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

    @model_validator(mode="after")
    def _current(self) -> "Settings":
        if not self.gyms:  # before 6.7: one gym, from the bar and plates
            self.gyms = [GymProfile(id="home", name="Home", bar=self.bar, plates=list(self.plates))]
        gym = next((g for g in self.gyms if g.id == self.current_gym), None) or self.gyms[0]
        self.current_gym, self.bar, self.plates = gym.id, gym.bar, list(gym.plates)
        return self

    def gym(self, gym_id: str | None = None) -> GymProfile:
        return next((g for g in self.gyms if g.id == (gym_id or self.current_gym)), self.gyms[0])


class GymDoc(BaseModel):
    exercises: list[CustomExercise] = Field(default_factory=list)
    routines: list[Routine] = Field(default_factory=list)
    sessions: list[Session] = Field(default_factory=list)
    settings: Settings = Field(default_factory=Settings)


def _path():
    return json_store.data_path("SIRISOS_GYM_PATH", "gym.json")


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


def load() -> GymDoc:
    raw = json_store.read(_path(), None)
    return GymDoc.model_validate(to_si(raw)) if isinstance(raw, dict) else GymDoc()


def save(doc: GymDoc) -> GymDoc:
    doc.sessions.sort(key=lambda s: s.started_at)
    json_store.write(_path(), doc.model_dump())
    return doc
