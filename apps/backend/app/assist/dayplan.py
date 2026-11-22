"""A plan for the day (11.3).

Today's tasks (and anything overdue) fitted into the free gaps in today's calendar, from now until wind-down:

- **How long:** a quick call or email 15 minutes, an errand 30, writing, design or a report 60 to 90 (deep work), else 30.
- **Where:** on a weekday, work tasks go in work hours and personal ones outside them; at the weekend, anywhere.
- **Hard things first:** deep work goes in the longest gap, early in the day when readiness is good. On a low-readiness
  day it gets one deep block at most, and the rest is left for tomorrow.
- **Errands together**, in one run.
- **A goal step:** if a yearly goal has slipped, its small step for this week goes in a free personal gap.

It's worked out again every time you look, so a meeting that runs over or a task done early just reshuffles the rest.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub

_QUICK = re.compile(r"\b(call|ring|phone|text|email|message|reply|pay|book|renew|cancel|order|sign|lodge|remind|tell|ask)\b", re.I)
_ERRAND = re.compile(r"\b(buy|pick up|collect|drop off|drop|post|return|bunnings|shop|shopping|groceries|pharmacy|chemist|bank|servo|fuel|car wash)\b", re.I)
_DEEP = re.compile(r"\b(write|draft|report|review|design|plan|prepare|study|calc|calculation|analyse|analyze|model|submit|application|"
                   r"presentation|budget|tender|spec|specification|research|learn)\b", re.I)
BUFFER = 10
STEP = 15


def estimate(title: str) -> tuple[int, str]:
    """(minutes, kind) for a task: deep, quick, errand or normal."""
    if _DEEP.search(title):
        return (90 if re.search(r"\b(report|application|tender|presentation|specification|design)\b", title, re.I) else 60), "deep"
    if _ERRAND.search(title):
        return 30, "errand"
    if _QUICK.search(title):
        return 15, "quick"
    return 30, "normal"


def _m(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def gaps(start: int, end: int, busy: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Free stretches between start and end (minutes since midnight), at least 15 minutes long."""
    out, at = [], start
    for s, e in sorted(busy):
        if s - BUFFER > at:
            out.append((at, min(s - BUFFER, end)))
        at = max(at, e + BUFFER)
        if at >= end:
            break
    if at < end:
        out.append((at, end))
    return [(s, e) for s, e in out if e - s >= STEP]


def plan(tasks: list[dict[str, Any]], busy: list[tuple[int, int]], now_min: int, *, work: tuple[int, int] | None, end: int,
         readiness: int | None, goal_step: dict[str, Any] | None = None) -> dict[str, Any]:
    """The pure part: tasks [{id, title, area, time?}] into the free time. Returns blocks and what didn't fit."""
    start = ((now_min + STEP - 1) // STEP) * STEP
    free = [list(g) for g in gaps(start, end, busy)]
    low = readiness is not None and readiness < 40
    blocks: list[dict[str, Any]] = []
    left: list[dict[str, Any]] = []

    def in_window(g: list[int], area: str) -> tuple[int, int] | None:
        s, e = g
        if work:
            ws, we = work
            s, e = (max(s, ws), min(e, we)) if area == "work" else (s, e)
            if area != "work" and s < we and e > ws:  # personal: outside work hours (take the part after, else before)
                after, before = (max(s, we), e), (s, min(e, ws))
                s, e = after if after[1] - after[0] >= before[1] - before[0] else before
        return (s, e) if e - s >= STEP else None

    def place(item: dict[str, Any], minutes: int, kind: str, prefer: str) -> bool:
        options = []
        for g in free:
            w = in_window(g, item.get("area") or "personal")
            if w and w[1] - w[0] >= minutes:
                options.append((g, w))
        if not options:
            return False
        if prefer == "longest":
            g, w = max(options, key=lambda o: (o[1][1] - o[1][0], -o[1][0]))
        else:
            g, w = min(options, key=lambda o: o[1][0])
        s = w[0]
        blocks.append({"start": _hm(s), "end": _hm(s + minutes), "minutes": minutes, "kind": kind, "title": item["title"],
                       "task_id": item.get("id"), "area": item.get("area")})
        # Take the time out of the gap it came from.
        if s == g[0]:
            g[0] = s + minutes
        else:
            free.append([s + minutes, g[1]])
            g[1] = s
        free[:] = [x for x in free if x[1] - x[0] >= STEP]
        return True

    timed = [t for t in tasks if t.get("time")]
    for t in timed:  # a task with its own time keeps it
        s = _m(t["time"])
        if s >= start - 60:
            blocks.append({"start": t["time"], "end": _hm(s + 15), "minutes": 15, "kind": "set", "title": t["title"], "task_id": t.get("id"), "area": t.get("area")})
    rest = [t for t in tasks if not t.get("time")]
    sized = [(t, *estimate(t["title"])) for t in rest]
    deep = [x for x in sized if x[2] == "deep"]
    errands = [x for x in sized if x[2] == "errand"]
    others = [x for x in sized if x[2] in ("quick", "normal")]
    for i, (t, minutes, kind) in enumerate(deep):
        if low and i >= 1:
            left.append({**t, "why": "Low readiness today: one deep block is enough."})
            continue
        if not place(t, minutes, kind, "longest"):
            left.append({**t, "why": "No gap long enough today."})
    if errands:
        run = {"title": "Errands: " + ", ".join(t["title"] for t, _, _ in errands), "id": None, "area": "personal"}
        total = min(120, sum(m for _, m, _ in errands) - 10 * (len(errands) - 1))
        if not place(run, max(30, total), "errand", "first"):
            left.extend({**t, "why": "No free time outside work today."} for t, _, _ in errands)
        else:
            blocks[-1]["task_ids"] = [t.get("id") for t, _, _ in errands]
    for t, minutes, kind in sorted(others, key=lambda x: x[1]):
        if not place(t, minutes, kind, "first"):
            left.append({**t, "why": "The day's full."})
    if goal_step and place({"title": goal_step["step"], "id": None, "area": "personal"}, goal_step.get("minutes", 30), "goal", "first"):
        blocks[-1]["goal"] = goal_step.get("goal")
    blocks.sort(key=lambda b: b["start"])
    return {"blocks": blocks, "left": left, "free_minutes": sum(e - s for s, e in free)}


async def today(hub: Hub, now: datetime) -> dict[str, Any]:
    from app.home import schedule
    from app.tasks import service as tasks

    day = now.date()
    col = await tasks.collect(hub, day)
    items = [{"id": i["id"], "title": i["title"], "area": i.get("area"), "time": i.get("time") if i.get("due") == day.isoformat() else None}
             for g in ("overdue", "today") for i in col["groups"].get(g, [])]
    cal = await sirisai_api.get(hub, "/siris/hub/v1/calendar", params={"start": day.isoformat(), "end": (day + timedelta(days=1)).isoformat()}, timeout=8.0) or {}
    busy = []
    for e in cal.get("events") or []:
        if not isinstance(e, dict) or e.get("all_day") or "T" not in str(e.get("start")) or not e.get("end"):
            continue
        try:
            s = datetime.fromisoformat(str(e["start"]).replace("Z", "+00:00")).astimezone(now.tzinfo)
            f = datetime.fromisoformat(str(e["end"]).replace("Z", "+00:00")).astimezone(now.tzinfo)
        except ValueError:
            continue
        if f.date() < day or s.date() > day:
            continue
        busy.append((s.hour * 60 + s.minute if s.date() == day else 0, f.hour * 60 + f.minute if f.date() == day else 24 * 60))
    health = await sirisai_api.get(hub, "/siris/hub/v1/health/overview", timeout=10.0) or {}
    readiness = (health.get("readiness") or {}).get("score") if isinstance(health.get("readiness"), dict) else None
    sch = schedule.load()
    t = sch.weekend if day.weekday() >= 5 else sch.weekday
    work = None if day.weekday() >= 5 else (_m(t.day), _m(t.evening))
    end = _m(t.winddown)
    from app.assist import goals_steer

    step = await goals_steer.step_for_today(hub, day)
    out = plan(items, busy, now.hour * 60 + now.minute, work=work, end=end, readiness=readiness, goal_step=step)
    return {"date": day.isoformat(), "readiness": readiness, "until": _hm(end), **out, "tasks": len(items),
            "events": [{"start": _hm(s), "end": _hm(e)} for s, e in sorted(busy)]}
