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

from pydantic import BaseModel, Field

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


class PlanExercise(BaseModel):
    exercise: str = Field(max_length=60)
    sets: int = Field(default=3, ge=1, le=20)
    reps: str = Field(default="8-12", max_length=12, pattern=r"^\d{1,3}(-\d{1,3})?$")
    rest_s: int = Field(default=90, ge=0, le=900)
    note: str = Field(default="", max_length=200)


class RoutineDay(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    exercises: list[PlanExercise] = Field(default_factory=list, max_length=20)


class Routine(BaseModel):
    id: str = Field(default_factory=new_id, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    days: list[RoutineDay] = Field(default_factory=list, max_length=14)
    note: str = Field(default="", max_length=500)
    active: bool = False


class Settings(BaseModel):
    unit: Literal["kg", "lb"] = "kg"
    bar: float = Field(default=20, ge=0, le=60)
    plates: list[float] = Field(default_factory=lambda: [25, 20, 15, 10, 5, 2.5, 1.25], max_length=12)
    increment: float = Field(default=2.5, gt=0, le=20)
    rest_s: int = Field(default=90, ge=0, le=900)


class GymDoc(BaseModel):
    exercises: list[CustomExercise] = Field(default_factory=list)
    routines: list[Routine] = Field(default_factory=list)
    sessions: list[Session] = Field(default_factory=list)
    settings: Settings = Field(default_factory=Settings)


def _path():
    return json_store.data_path("SIRISOS_GYM_PATH", "gym.json")


def load() -> GymDoc:
    raw = json_store.read(_path(), None)
    return GymDoc.model_validate(raw) if isinstance(raw, dict) else GymDoc()


def save(doc: GymDoc) -> GymDoc:
    doc.sessions.sort(key=lambda s: s.started_at)
    json_store.write(_path(), doc.model_dump())
    return doc
