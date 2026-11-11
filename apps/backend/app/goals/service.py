"""Yearly goals (4.4), on the Your year page: set in January, tracked all year.

A goal is one of:

- **measured**: running km, CPD hours, journal days, tasks done, or how
  ready the Chartered application is (Career → Application, 4.6). SirisOS
  counts it from what it already knows for that calendar year (SirisAI's
  health by day, career records, the wrap-up and the daily log), e.g.
  "Run 1,000 km", "40 CPD hours".
- **counted by hand**: a number you move up yourself, e.g. "Read 12 books".
- **done or not**: e.g. "Get chartered".

Each one says whether it's on track: how far along it is against how far
through the year it is.

8.3: SirisAI asks on Home all through January to set the year's goals, until you
say they're set; and all through December to review them, until you finish the
review, where what isn't done carries into the next year. A December review
missed is asked for first thing in January. Each also sends one notification.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.career import store as career_store
from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store
from app.tasks import service as tasks
from app.tasks import store as task_store
from app.trends import log

Kind = Literal["running_km", "cpd_hours", "journal_days", "tasks_done", "chartered_ready", "count", "done", "lift"]
MEASURED: dict[str, tuple[str, str]] = {
    "running_km": ("km", "Running"),
    "cpd_hours": ("h", "CPD hours"),
    "journal_days": ("days", "Journal days"),
    "tasks_done": ("tasks", "Tasks done"),
    "chartered_ready": ("%", "Chartered application"),
}


class Goal(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    title: str = Field(min_length=1, max_length=200)
    kind: Kind = "done"
    target: float | None = Field(default=None, gt=0, le=1_000_000)
    unit: str = Field(default="", max_length=20)
    progress: float = Field(default=0, ge=0, le=1_000_000)  # "count" goals only
    done: bool = False  # "done" goals only
    notes: str = Field(default="", max_length=1000)
    exercise: str | None = Field(default=None, max_length=60)  # "lift" goals (8.7): a SirisGym exercise's best estimated 1RM this year


def _path():
    return json_store.data_path("SIRISOS_GOALS_PATH", "goals.json")


def _load() -> dict[str, list[dict[str, Any]]]:
    value = json_store.read(_path(), {})
    return value if isinstance(value, dict) else {}


def goals(year: int) -> list[Goal]:
    return [Goal.model_validate(g) for g in _load().get(str(year), [])]


def _save(year: int, items: list[Goal]) -> None:
    doc = _load()
    doc[str(year)] = [g.model_dump() for g in items]
    json_store.write(_path(), doc)


def add(year: int, goal: Goal) -> Goal:
    if goal.kind in MEASURED and not goal.unit:
        goal.unit = MEASURED[goal.kind][0]
    if goal.kind == "lift" and not goal.unit:
        goal.unit = "kg"
    _save(year, [*goals(year), goal])
    return goal


def update(year: int, goal_id: str, changes: dict[str, Any]) -> Goal:
    items = goals(year)
    for i, g in enumerate(items):
        if g.id == goal_id:
            items[i] = Goal.model_validate({**g.model_dump(), **changes, "id": g.id})
            _save(year, items)
            return items[i]
    raise LookupError(goal_id)


def delete(year: int, goal_id: str) -> None:
    items = goals(year)
    if not any(g.id == goal_id for g in items):
        raise LookupError(goal_id)
    _save(year, [g for g in items if g.id != goal_id])


async def measured(hub: Hub, year: int, today: date) -> dict[str, float | None]:
    """This calendar year so far, for each measured kind (None: no source answered)."""
    start = date(year, 1, 1)
    end = min(today, date(year, 12, 31))
    if end < start:
        return {k: 0.0 for k in MEASURED}
    first, last = start.isoformat(), end.isoformat()
    within = lambda iso: first <= iso[:10] <= last  # noqa: E731

    days_back = (today - start).days + 1
    health = await sirisai_api.get(hub, "/siris/hub/v1/health/days", params={"days": min(400, days_back)}) if days_back <= 400 else None
    running = None if health is None else round(sum(float((d.get("metrics") or {}).get("running_km") or 0)
                                                    for d in health.get("days") or [] if within(str(d.get("date")))), 1)

    cpd = round(sum(r.hours for r in career_store.load().cpd.records if r.date and within(r.date)), 1)

    daily = log.days()
    log_from = min(daily) if daily else None
    journal = {iso for iso, e in daily.items() if e.get("journal") and within(iso)}
    from app.wrapup import service as wrapup

    journal |= {iso for iso, e in wrapup._load().items() if e.get("journal") and within(iso)}
    done = sum(int(e.get("tasks_done") or 0) for iso, e in daily.items() if within(iso))
    done += sum(1 for t in task_store.load().tasks if t.done_at and within(t.done_at) and (log_from is None or t.done_at[:10] < log_from))
    from app.career import application

    ready = float(application.readiness(career_store.load())["percent"])
    return {"running_km": running, "cpd_hours": cpd, "journal_days": float(len(journal)), "tasks_done": float(done),
            "chartered_ready": ready}


def _fraction_of_year(year: int, today: date) -> float:
    start, end = date(year, 1, 1), date(year, 12, 31)
    if today < start:
        return 0.0
    if today > end:
        return 1.0
    return ((today - start).days + 1) / ((end - start).days + 1)


async def overview(hub: Hub, year: int | None = None, today: date | None = None) -> dict[str, Any]:
    today = today or tasks.today()
    year = year or today.year
    items = goals(year)
    counts = await measured(hub, year, today) if any(g.kind in MEASURED for g in items) else {}
    through = _fraction_of_year(year, today)
    out = []
    for g in items:
        if g.kind == "done":
            value, pct = (1.0 if g.done else 0.0), (100 if g.done else 0)
        else:
            value = (lift_best(g.exercise, year) if g.kind == "lift" else counts.get(g.kind) if g.kind in MEASURED else g.progress)
            pct = None if value is None or not g.target else min(100, round(value / g.target * 100))
        if g.kind == "done":
            state = "done" if g.done else "open"
        elif pct is None:
            state = "unknown"
        elif pct >= 100:
            state = "done"
        else:
            state = "on_track" if pct >= through * 100 - 5 else "behind"
        out.append({**g.model_dump(), "value": value, "percent": pct, "state": state,
                    "source": MEASURED[g.kind][1] if g.kind in MEASURED else "SirisGym" if g.kind == "lift" else None})
    asked = prompt(today)
    return {"year": year, "today": today.isoformat(), "through_year": round(through * 100), "goals": out,
            "set_them": not items and today.year == year and today.month == 1,
            "setting_due": bool(asked and asked["kind"] == "set" and asked["year"] == year),
            "review_due": bool(asked and asked["kind"] == "review" and asked["year"] == year),
            "reviewed": f"review:{year}" in _marks()}


MARKS = "_marks"  # in goals.json beside the years: "set:2027" / "review:2026" -> when you said so


def _marks() -> dict[str, str]:
    found = _load().get(MARKS)
    return found if isinstance(found, dict) else {}


def mark(kind: Literal["set", "review"], year: int) -> dict[str, str]:
    doc = _load()
    marks = dict(_marks())
    marks[f"{kind}:{year}"] = datetime.now().isoformat(timespec="seconds")
    doc[MARKS] = marks
    json_store.write(_path(), doc)
    return marks


def prompt(today: date) -> dict[str, Any] | None:
    """What SirisAI asks on Home about goals today: review a year (December, or a missed one in January), else set the new one (January)."""
    marks = _marks()
    if today.month == 12 and f"review:{today.year}" not in marks:
        return {"kind": "review", "year": today.year, "goals": len(goals(today.year))}
    if today.month == 1:
        last = today.year - 1
        if goals(last) and f"review:{last}" not in marks:
            return {"kind": "review", "year": last, "goals": len(goals(last))}
        if f"set:{today.year}" not in marks:
            return {"kind": "set", "year": today.year, "goals": len(goals(today.year))}
    return None


def carry(year: int, ids: list[str]) -> list[Goal]:
    """The goals picked from `year`, started afresh in the next one. One already there by name isn't doubled."""
    nxt = goals(year + 1)
    have = {g.title.casefold() for g in nxt}
    moved = []
    for g in goals(year):
        if g.id in ids and g.title.casefold() not in have:
            fresh = Goal(title=g.title, kind=g.kind, target=g.target, unit=g.unit, notes=(f"Carried from {year}. " + g.notes).strip()[:1000])
            nxt.append(fresh)
            moved.append(fresh)
    _save(year + 1, nxt)
    return moved


def lift_best(exercise: str | None, year: int) -> float | None:
    """The best estimated 1RM of a SirisGym exercise in `year` (8.7), for a goal like "Bench 120 kg"."""
    if not exercise:
        return None
    from app.gym import service as gym, store as gym_store

    rows = [r["e1rm"] for r in gym.history(gym_store.load(), exercise) if r["e1rm"] and r["date"].startswith(str(year))]
    return max(rows) if rows else 0.0


def push_message(now: datetime) -> list[dict[str, Any]]:
    """One notification for each prompt: setting the year's goals, and reviewing them."""
    asked = prompt(now.date())
    if asked is None:
        return []
    if asked["kind"] == "review":
        return [{"key": f"goals:review:{asked['year']}", "topic": "brief", "title": f"Review your {asked['year']} goals",
                 "body": "See how the year went, and carry what you didn't finish into the next one.", "url": f"/year?review={asked['year']}", "urgency": "normal"}]
    return [{"key": f"goals:set:{asked['year']}", "topic": "brief", "title": f"Set your goals for {asked['year']}",
             "body": "A few things to aim for this year. SirisOS tracks the running, CPD and journal ones for you.",
             "url": "/year", "urgency": "normal"}]
