"""Work (7.2): the dashboard for the working day, from 8:00 to 4:30 on weekdays
(the "work" part of the day in Times of day).

Everything an engineering day at work needs, from what SirisOS already has:

- **the day**: how long until home time (7.31: no calendar, which Brad doesn't link for work);
- **tasks**: SirisOS tasks that are work (set, or guessed from their words),
  overdue, today and this week;
- **to-dos in work notes**: open tasks in Siris' work notes (under Work/ or
  named for a work organisation: GVW, CMP), not shown as projects (7.31);
- **the engineering project** picked in Engineering, and the other active ones;
- **CPD**: hours in Engineers Australia's three-year window against 150.

Each part is fetched on its own: one that fails or isn't set up is empty, never the whole page.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
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

    # 7.31: no calendar (Brad's work calendar isn't linked, and he doesn't want it) and no projects (Projects is personal).
    tk, pr = await asyncio.gather(
        safe(_tasks(hub, day), {"groups": {}, "counts": {}}),
        safe(_projects(hub), {"projects": None, "todos": None}),
    )
    pr.pop("projects", None)
    return {"date": day.isoformat(), "local_time": at.isoformat(timespec="minutes"), "hours": hours(at), "tasks": tk, **pr,
            "engineering": _engineering(), "cpd": _cpd(day)}
