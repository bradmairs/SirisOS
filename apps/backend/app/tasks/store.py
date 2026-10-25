"""SirisOS's own tasks (tasks.json): ones added here or by "remind me…" in
quick capture, with an optional due date and time and a repeat. Tasks that
live elsewhere (Siris notes, SirisAI reminders) keep their home; only how
they're snoozed here is remembered, under `overlays`."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, Field

from app.services import json_store

Repeat = Literal["none", "daily", "weekdays", "weekly", "fortnightly", "monthly"]


class Task(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = Field(min_length=1, max_length=300)
    due: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    notes: str = Field(default="", max_length=2000)
    repeat: Repeat = "none"
    # Work or personal, for Home's work hours and evenings (4.9); None lets service.area_of guess.
    area: Literal["work", "personal"] | None = None
    created_at: str = ""
    done_at: str | None = None
    reminded_for: str | None = None  # the due date+time a notification already went out for


class Overlay(BaseModel):
    snoozed_until: str | None = None


class TasksDocument(BaseModel):
    tasks: list[Task] = []
    overlays: dict[str, Overlay] = {}


def _path():
    return json_store.data_path("SIRISOS_TASKS_PATH", "tasks.json")


def load() -> TasksDocument:
    return TasksDocument.model_validate(json_store.read(_path(), {}))


def save(doc: TasksDocument) -> TasksDocument:
    # Done one-off tasks are kept 60 days, for the wrap-up and the weekly review.
    cutoff = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    doc.tasks = [t for t in doc.tasks if not t.done_at or t.done_at >= cutoff]
    json_store.write(_path(), doc.model_dump())
    return doc


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def next_due(due: date, repeat: Repeat) -> date:
    """The next occurrence after `due` (monthly keeps the day, clamped to month end)."""
    if repeat == "daily":
        return due + timedelta(days=1)
    if repeat == "weekdays":
        nxt = due + timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += timedelta(days=1)
        return nxt
    if repeat == "weekly":
        return due + timedelta(days=7)
    if repeat == "fortnightly":
        return due + timedelta(days=14)
    if repeat == "monthly":
        year, month = (due.year + 1, 1) if due.month == 12 else (due.year, due.month + 1)
        for day in range(due.day, 27, -1):
            try:
                return date(year, month, day)
            except ValueError:
                continue
        return date(year, month, min(due.day, 28))
    return due
