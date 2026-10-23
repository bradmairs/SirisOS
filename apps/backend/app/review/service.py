"""The weekly review (3.5): on Sunday, how the week went and what's coming.

- **The week in numbers** (Monday to today): tasks done, notes learned or
  updated in Siris, CPD hours dated this week, runs and exercise (from
  SirisAI's health data), meetings, and evenings wrapped up.
- **Going quiet**: Siris projects nobody has touched in three weeks.
- **Next week's crunch points**: busy days (4+ meetings, or meetings that
  overlap), tasks and project deadlines due.
- **What matters next week**: one note, saved to Siris (tagged
  `weekly-review`) and shown on the This week screen.

A notification on SIRISOS_REVIEW_WEEKDAY (6 = Sunday) from
SIRISOS_REVIEW_HOUR (16) offers it, once, unless it's done.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any

from app.brief.service import zone
from app.calendar import service as calendar
from app.career import store as career_store
from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store
from app.tasks import service as tasks
from app.tasks import store as task_store
from app.wrapup import service as wrapup


def _path():
    return json_store.data_path("SIRISOS_REVIEW_PATH", "review.json")


def week_of(day: date) -> tuple[date, date]:
    """Monday and Sunday of the week `day` is in."""
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def saved(monday: date) -> dict[str, Any] | None:
    return json_store.read(_path(), {}).get(monday.isoformat())


def latest_focus(on: date) -> dict[str, Any] | None:
    """The 'what matters' note for the week `on` is in (written the Sunday before), or None."""
    monday, _ = week_of(on)
    entry = saved(monday - timedelta(days=7))
    return {"week_of": monday.isoformat(), "text": entry["focus"]} if entry and entry.get("focus") else None


def _int(env: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(os.getenv(env, str(default)))))
    except ValueError:
        return default


def _timed(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [e for e in events or [] if not e.get("all_day") and "T" in str(e.get("start") or "")]


def _busy_days(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_day: dict[str, list[dict[str, Any]]] = {}
    for e in events:
        by_day.setdefault(str(e["start"])[:10], []).append(e)
    out = []
    for day, items in sorted(by_day.items()):
        spans = []
        for e in items:
            try:
                spans.append((datetime.fromisoformat(str(e["start"])), datetime.fromisoformat(str(e.get("end") or e["start"])), e.get("title")))
            except ValueError:
                continue
        spans.sort()
        clashes = [f"{a[2]} and {b[2]}" for i, a in enumerate(spans) for b in spans[i + 1:] if b[0] < a[1]]
        if len(items) >= 4 or clashes:
            out.append({"date": day, "meetings": len(items), "clashes": clashes[:3]})
    return out


async def overview(hub: Hub, today: date | None = None) -> dict[str, Any]:
    today = today or tasks.today()
    monday, sunday = week_of(today)
    next_monday = monday + timedelta(days=7)

    done = [t for t in task_store.load().tasks if t.done_at and monday <= datetime.fromisoformat(t.done_at).astimezone(zone()).date() <= today]
    insights = await sirisai_api.get(hub, "/siris/brain/insights", params={"days": 14}) or {}
    summary = insights.get("summary") or {}
    health = await sirisai_api.get(hub, "/siris/hub/v1/health/days", params={"days": 7}) or {}
    days = [d for d in health.get("days") or [] if monday.isoformat() <= d.get("date", "") <= today.isoformat()]
    ran = round(sum(d["metrics"].get("running_km", 0) for d in days), 1)
    runs = sum(1 for d in days if d["metrics"].get("running_km", 0) > 0)
    exercise = round(sum(d["metrics"].get("exercise_minutes", 0) for d in days))
    cpd = round(sum(r.hours for r in career_store.load().cpd.records if r.date and monday.isoformat() <= r.date <= today.isoformat()), 1)
    this_week = await calendar.events(hub, monday, today + timedelta(days=1))
    wrapped = sum(1 for i in range((today - monday).days + 1) if wrapup.saved(monday + timedelta(days=i)))

    ahead = await calendar.events(hub, next_monday, next_monday + timedelta(days=7))
    listing = await tasks.collect(hub, today)
    due_next = [t for g in ("week", "later") for t in listing["groups"][g] if t.get("due") and next_monday.isoformat() <= t["due"] < (next_monday + timedelta(days=7)).isoformat()]
    deadlines = [d for d in insights.get("deadlines") or [] if 0 <= (d.get("days_left") or 99) <= (next_monday - today).days + 6]

    return {
        "week_of": monday.isoformat(),
        "today": today.isoformat(),
        "numbers": {
            "tasks_done": len(done),
            "notes": summary.get("this_week"),
            "notes_before": summary.get("previous_week"),
            "cpd_hours": cpd,
            "runs": runs if health.get("days") is not None else None,
            "run_km": ran if health.get("days") is not None else None,
            "exercise_minutes": exercise if health.get("days") is not None else None,
            "meetings": len(_timed(this_week["events"])) if this_week["events"] is not None else None,
            "wrapped_up": wrapped,
        },
        "done": [t.title for t in done][:12],
        "quiet": (insights.get("stale_projects") or [])[:6],
        "next_week": {
            "busy_days": _busy_days(_timed(ahead["events"])),
            "meetings": len(_timed(ahead["events"])) if ahead["events"] is not None else None,
            "tasks": due_next[:10],
            "deadlines": deadlines[:6],
        },
        "saved": saved(monday),
    }


async def save(hub: Hub, today: date, focus: str) -> dict[str, Any]:
    monday, _ = week_of(today)
    text = focus.strip()
    saved_as = None
    if text:
        week = monday.isocalendar().week
        try:
            r = await sirisai_api.post(hub, "/siris/brain/capture", json={
                "title": f"Week {week} review ({monday.year})", "text": f"What matters next week:\n\n{text}", "tags": ["weekly-review"]})
            saved_as = (r or {}).get("title")
        except sirisai_api.SirisAIError:
            saved_as = None
    state = json_store.read(_path(), {})
    state[monday.isoformat()] = {"focus": text, "saved_as": saved_as, "at": datetime.now(zone()).isoformat(timespec="minutes")}
    json_store.write(_path(), dict(sorted(state.items())[-26:]))
    from app.trends import log

    log.mark("review", today)
    return state[monday.isoformat()]


def push_message(now: datetime) -> list[dict[str, Any]]:
    local = now.astimezone(zone())
    if local.weekday() != _int("SIRISOS_REVIEW_WEEKDAY", 6, 0, 6) or local.hour < _int("SIRISOS_REVIEW_HOUR", 16, 0, 23):
        return []
    if saved(week_of(local.date())[0]):
        return []
    return [{"key": f"review:{local.date().isoformat()}", "topic": "brief", "title": "Your weekly review",
             "body": "Five minutes: how the week went, and what matters next week.", "url": "/review", "urgency": "normal"}]
