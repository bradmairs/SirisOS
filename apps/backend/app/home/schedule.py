"""When each part of the day starts, and which Home sections lead in it (4.8).

Weekdays and weekends have their own times. A weekday runs morning, work,
evening, night; a weekend runs morning, weekend (its daytime), evening,
night. Each part starts at its time and lasts until the next one; night
runs past midnight to the morning. The order of Home's sections ("Now",
"Today", "Home") is set per part of the day. Saved on the server, so every
device follows the same day.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services import json_store

PHASES = ("morning", "work", "weekend", "evening", "night")
SECTIONS = ("Now", "Today", "Home")
_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


class DayTimes(BaseModel):
    """Start times, HH:MM, in the order the day runs."""
    morning: str
    day: str        # work on a weekday, the weekend's daytime on Saturday and Sunday
    evening: str
    night: str

    @field_validator("morning", "day", "evening", "night")
    @classmethod
    def _hhmm(cls, v: str) -> str:
        if not _TIME.match(v):
            raise ValueError("times are HH:MM, 24-hour")
        return v

    @model_validator(mode="after")
    def _in_order(self) -> "DayTimes":
        times = [_minutes(t) for t in (self.morning, self.day, self.evening, self.night)]
        if times != sorted(set(times)) or len(set(times)) != 4:
            raise ValueError("each part of the day starts after the one before it")
        return self


def _default_sections() -> dict[str, list[str]]:
    return {
        "morning": ["Now", "Today", "Home"],
        "work": ["Today", "Now", "Home"],
        "weekend": ["Home", "Today", "Now"],
        "evening": ["Today", "Home", "Now"],
        "night": ["Today", "Home", "Now"],
    }


class Schedule(BaseModel):
    weekday: DayTimes = Field(default_factory=lambda: DayTimes(morning="05:00", day="08:30", evening="16:30", night="23:00"))
    weekend: DayTimes = Field(default_factory=lambda: DayTimes(morning="05:00", day="10:00", evening="17:00", night="23:00"))
    sections: dict[str, list[str]] = Field(default_factory=_default_sections)

    @field_validator("sections")
    @classmethod
    def _orders(cls, v: dict[str, list[str]]) -> dict[str, list[str]]:
        out = _default_sections()
        for phase, order in v.items():
            if phase not in PHASES:
                raise ValueError(f"unknown part of the day {phase!r}")
            if sorted(order) != sorted(SECTIONS):
                raise ValueError(f"{phase} must order exactly {', '.join(SECTIONS)}")
            out[phase] = list(order)
        return out


def _path():
    return json_store.data_path("SIRISOS_HOME_SCHEDULE_PATH", "home-schedule.json")


def load() -> Schedule:
    raw = json_store.read(_path(), {})
    try:
        return Schedule.model_validate(raw if isinstance(raw, dict) else {})
    except ValueError:
        return Schedule()   # a broken file never breaks Home


def save(schedule: Schedule) -> Schedule:
    json_store.write(_path(), schedule.model_dump())
    return schedule


def phase(at: datetime, schedule: Schedule | None = None) -> str:
    s = schedule or load()
    weekend = at.weekday() >= 5
    t = s.weekend if weekend else s.weekday
    now = at.hour * 60 + at.minute
    if now < _minutes(t.morning) or now >= _minutes(t.night):
        return "night"
    if now < _minutes(t.day):
        return "morning"
    if now < _minutes(t.evening):
        return "weekend" if weekend else "work"
    return "evening"
