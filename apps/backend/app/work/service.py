"""Work (7.2): the dashboard for the working day, from 8:00 to 4:30 on weekdays
(the "work" part of the day in Times of day).

Everything an engineering day at work needs, from what SirisOS already has:

- **the day**: how long until home time, today's meetings and the next one;
- **tasks**: SirisOS tasks that are work (set, or guessed from their words),
  overdue, today and this week;
- **work projects**: Siris' projects under Work/ or named for a work
  organisation (GVW, CMP: SIRISOS_PROJECTS_EXCLUDE), the ones Projects leaves
  out, with what's due and their open to-dos;
- **to-dos in work notes**: open tasks in those notes;
- **the engineering project** picked in Engineering, and the other active ones;
- **CPD**: hours in Engineers Australia's three-year window against 150.

Each part is fetched on its own: one that fails or isn't set up is empty, never the whole page.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Any

from app.hub import sirisai_api
from app.hub.service import Hub
from app.siris_projects import service as projects
from app.tasks import service as tasks


def hours(at: datetime) -> dict[str, Any]:
    """The working day from Times of day: start, finish, whether it's on now, minutes left."""
    from app.home import schedule

    plan = schedule.load()
    t = plan.weekday
    start, end = t.day, t.evening
    now = at.hour * 60 + at.minute
    s = int(start[:2]) * 60 + int(start[3:])
    e = int(end[:2]) * 60 + int(end[3:])
    on = at.weekday() < 5 and s <= now < e
    return {"start": start, "end": end, "on": on, "workday": at.weekday() < 5,
            "minutes_left": e - now if on else None, "minutes_in": now - s if on else None}


def _work_project(p: dict[str, Any]) -> bool:
    return not projects.personal(p)


async def _events(hub: Hub, day: date, at: datetime) -> dict[str, Any]:
    body = await sirisai_api.get(hub, "/siris/hub/v1/calendar", params={"start": day.isoformat(), "end": (day + timedelta(days=1)).isoformat()},
                                 timeout=8.0)
    if body is None or body.get("guest_mode"):
        return {"events": None, "next": None}
    out = []
    for e in body.get("events") or []:
        start = str(e.get("start") or "")
        if not start.startswith(day.isoformat()):
            continue
        out.append({"title": e.get("title") or "Event", "start": start, "end": e.get("end"), "all_day": bool(e.get("all_day")),
                    "location": e.get("location") or None})
    out.sort(key=lambda e: (not e["all_day"], e["start"]))
    nxt = None
    for e in out:
        if e["all_day"]:
            continue
        try:
            when = datetime.fromisoformat(e["start"].replace("Z", "+00:00"))
            when = when if when.tzinfo else when.replace(tzinfo=at.tzinfo)
        except ValueError:
            continue
        mins = round((when - at).total_seconds() / 60)
        end_ok = True
        if e.get("end"):
            try:
                fin = datetime.fromisoformat(str(e["end"]).replace("Z", "+00:00"))
                end_ok = (fin if fin.tzinfo else fin.replace(tzinfo=at.tzinfo)) > at
            except ValueError:
                pass
        if end_ok and mins > -600:
            nxt = {**e, "in_minutes": mins, "now": mins <= 0}
            break
    return {"events": out, "next": nxt}


async def _tasks(hub: Hub, day: date) -> dict[str, Any]:
    found = await tasks.collect(hub, day)
    groups = {g: [t for t in found["groups"].get(g, []) if t.get("area") == "work"] for g in ("overdue", "today", "week")}
    return {"groups": groups, "counts": {g: len(v) for g, v in groups.items()}}


async def _projects(hub: Hub) -> dict[str, Any]:
    listed, insights, vault = await asyncio.gather(
        sirisai_api.get(hub, "/siris/brain/projects"),
        sirisai_api.get(hub, "/siris/brain/insights", params={"days": 30}),
        sirisai_api.get(hub, "/siris/brain/tasks"),
    )
    if listed is None:
        return {"projects": None, "todos": None}
    work = [p for p in listed.get("projects") or [] if _work_project(p)]
    deadlines = {d.get("title"): d for d in (insights or {}).get("deadlines") or [] if isinstance(d, dict)}
    titles = {p["title"] for p in work}
    words = projects._excluded_words()
    todos = [t for t in (vault or {}).get("tasks") or [] if t.get("note") in titles or projects.mentions(t.get("note"), words)]
    counts: dict[str, int] = {}
    for t in todos:
        counts[t["note"]] = counts.get(t["note"], 0) + 1
    out = []
    for p in work:
        if str(p.get("status") or "").lower() in ("done", "finished", "archived", "complete", "completed"):
            continue
        d = deadlines.get(p["title"]) or {}
        out.append({"title": p["title"], "path": p.get("path"), "status": p.get("status"), "due": d.get("due"), "days_left": d.get("days_left"),
                    "open_tasks": counts.get(p["title"], 0)})
    out.sort(key=lambda p: (p["days_left"] is None, p["days_left"] if p["days_left"] is not None else 0, -p["open_tasks"], p["title"].lower()))
    todos.sort(key=lambda t: (t.get("due") is None, t.get("due") or "", t.get("note") or ""))
    return {"projects": out[:12], "todos": todos[:15]}


def _engineering() -> dict[str, Any]:
    from app.api import projects as eng

    try:
        svc = eng._service()
        current = svc.current_project().project
        active = [p for p in svc.list_projects() if p.status == "active"]
    except Exception:  # noqa: BLE001 - the store may not exist yet
        return {"current": None, "active": []}
    pick = lambda p: {"id": p.id, "name": p.name, "kind": p.kind, "tags": p.tags}  # noqa: E731
    return {"current": pick(current) if current else None, "active": [pick(p) for p in active[:8]]}


def _cpd(day: date) -> dict[str, Any] | None:
    from app.career import cpd, store as career

    try:
        s = cpd.summary(career.load(), day)
    except Exception:  # noqa: BLE001
        return None
    return {"total": s.get("total"), "required": s.get("required"), "short": s.get("short")}


async def dashboard(hub: Hub, at: datetime) -> dict[str, Any]:
    day = at.date()

    async def safe(coro, empty):
        try:
            return await coro
        except Exception:  # noqa: BLE001 - one part failing leaves the rest
            return empty

    ev, tk, pr = await asyncio.gather(
        safe(_events(hub, day, at), {"events": None, "next": None}),
        safe(_tasks(hub, day), {"groups": {}, "counts": {}}),
        safe(_projects(hub), {"projects": None, "todos": None}),
    )
    return {"date": day.isoformat(), "local_time": at.isoformat(timespec="minutes"), "hours": hours(at), **ev, "tasks": tk, **pr,
            "engineering": _engineering(), "cpd": _cpd(day)}
