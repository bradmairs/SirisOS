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
import re
from datetime import date, datetime, timedelta
from typing import Any

from app.hub import sirisai_api
from app.services import json_store
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
    return {"total": s.get("total"), "required": s.get("required"), "short": s.get("short"),
            "minimums": [{"category": m["category"], "label": m["label"], "hours": m["hours"], "minimum": m["minimum"], "short": m["short"]}
                         for m in s.get("minimums") or []], "window": s.get("window")}


def log_cpd(title: str, hours_: float, category: str, day: date, provider: str = "") -> dict[str, Any]:
    """CPD logged from Work (7.4): kept with the imported records (a re-import never removes it), in your category."""
    import uuid

    from app.career import cpd, store as career

    record = career.CpdRecord(id=f"sirisos-{uuid.uuid4().hex[:10]}", date=day.isoformat(), title=title, provider=provider, type="Logged in SirisOS",
                              hours=hours_, split={category: hours_}, basis="you")
    cpd.merge(career.load(), [record], "SirisOS Work page")
    return record.model_dump()


# -- 7.4: the visuals. Focus time and to-dos ticked here are kept in work.json; work tasks done come from Tasks. --

def _path():
    return json_store.data_path("SIRISOS_WORK_PATH", "work.json")


def _load() -> dict[str, Any]:
    raw = json_store.read(_path(), {})
    return raw if isinstance(raw, dict) else {}


def add_focus(day: date, minutes: int) -> int:
    doc = _load()
    focus = doc.setdefault("focus", {})
    focus[day.isoformat()] = int(focus.get(day.isoformat(), 0)) + max(0, min(minutes, 240))
    doc["focus"] = dict(sorted(focus.items())[-120:])
    json_store.write(_path(), doc)
    return doc["focus"][day.isoformat()]


def add_todo_done(day: date) -> None:
    doc = _load()
    done = doc.setdefault("todos_done", {})
    done[day.isoformat()] = int(done.get(day.isoformat(), 0)) + 1
    doc["todos_done"] = dict(sorted(done.items())[-120:])
    json_store.write(_path(), doc)


def week(day: date) -> dict[str, Any]:
    """Monday to Sunday of this week: work tasks done (Tasks, plus work-note to-dos ticked here) and focus minutes."""
    from app.tasks import store as task_store
    from app.tasks.service import zone

    monday = day - timedelta(days=day.weekday())
    days = [monday + timedelta(days=i) for i in range(7)]
    done = {d.isoformat(): 0 for d in days}
    for t in task_store.load().tasks:
        if t.done_at and tasks.area_of(t.title, t.notes, t.area) == "work":
            d = datetime.fromisoformat(t.done_at).astimezone(zone()).date().isoformat()
            if d in done:
                done[d] += 1
    doc = _load()
    for d in done:
        done[d] += int((doc.get("todos_done") or {}).get(d, 0))
    focus = doc.get("focus") or {}
    return {"days": [{"date": d.isoformat(), "weekday": d.strftime("%a"), "done": done[d.isoformat()], "focus_min": int(focus.get(d.isoformat(), 0))}
                     for d in days], "done_today": done[day.isoformat()], "focus_today": int(focus.get(day.isoformat(), 0))}


WORK_APP = re.compile(r"\b(gvw|goulburn|cmp|timesheets?|sirispm|pm|archive|engineering|civil ?3d|12d|autocad|bentley|drawings?|gis)\b", re.I)


def apps() -> list[dict[str, Any]]:
    """Work apps for the tiles: links in a group named Work, or named like a work app (GVW, CMP, Timesheet, SirisPM, Archive)."""
    from app.links import store as links

    out = []
    for g in links.load().groups:
        for link in g.links:
            if "work" in g.name.lower() or WORK_APP.search(f"{link.name} {link.note}"):
                out.append({"id": link.id, "name": link.name, "url": link.url, "icon": link.icon, "note": link.note})
    return out[:12]


async def _recent_notes(hub: Hub) -> list[dict[str, Any]] | None:
    found = await sirisai_api.get(hub, "/siris/brain/recent", params={"folder": "Work", "limit": 6}, timeout=8.0)
    return found if isinstance(found, list) else None


async def dashboard(hub: Hub, at: datetime) -> dict[str, Any]:
    day = at.date()

    async def safe(coro, empty):
        try:
            return await coro
        except Exception:  # noqa: BLE001 - one part failing leaves the rest
            return empty

    # 7.31: no calendar (Brad's work calendar isn't linked, and he doesn't want it) and no projects (Projects is personal).
    tk, notes, pr = await asyncio.gather(
        safe(_tasks(hub, day), {"groups": {}, "counts": {}}),
        safe(_recent_notes(hub), None),
        safe(_projects(hub), {"projects": None, "todos": None}),
    )
    pr.pop("projects", None)
    return {"date": day.isoformat(), "local_time": at.isoformat(timespec="minutes"), "hours": hours(at), "tasks": tk, **pr,
            "week": week(day), "apps": apps(), "notes": notes,
            "engineering": _engineering(), "cpd": _cpd(day)}
