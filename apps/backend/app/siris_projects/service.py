"""Projects (4.0): one page per Siris project.

Siris (the vault, through SirisAI) knows the projects: every note of type
project (`/siris/brain/projects`), what's due and what's gone quiet
(insights), and the open tasks in each note. A project's page gathers what
SirisOS can find about it everywhere else, by its name and aliases:

- the note itself: what it's about, its links and what links to it
- open tasks: the note's own, plus SirisOS tasks that name the project
- calendar: events in the last fortnight and next month that name it

Only personal projects and the home lab (4.4): work ones are left out, i.e.
anything under `Work/` in the vault and anything whose name has a word from
SIRISOS_PROJECTS_EXCLUDE (default "CMP,GVW").

Every source fails alone; `unavailable` names the ones that didn't answer.
"""

from __future__ import annotations

import asyncio
import os
import re
from datetime import date, timedelta
from typing import Any

from app.calendar import service as calendar
from app.hub import sirisai_api
from app.hub.service import Hub
from app.tasks import service as tasks


class NotFound(Exception):
    pass


def _excluded_words() -> list[str]:
    return [w.strip() for w in os.getenv("SIRISOS_PROJECTS_EXCLUDE", "CMP,GVW").split(",") if w.strip()]


def personal(project: dict[str, Any]) -> bool:
    """Not a work project: outside the vault's Work/ folder and not named for a work organisation."""
    if str(project.get("path") or "").replace("\\", "/").startswith("Work/"):
        return False
    return not mentions(" ".join([project.get("title") or "", *(project.get("aliases") or [])]), _excluded_words())


async def _listed(hub: Hub) -> list[dict[str, Any]] | None:
    found = await sirisai_api.get(hub, "/siris/brain/projects")
    return None if found is None else [p for p in found.get("projects") or [] if personal(p)]


def names(project: dict[str, Any]) -> list[str]:
    """The project's title and aliases, longest first (2 letters or more)."""
    found = [project["title"], *(project.get("aliases") or [])]
    return sorted({n.strip() for n in found if isinstance(n, str) and len(n.strip()) >= 2}, key=len, reverse=True)


def mentions(text: str | None, words: list[str]) -> bool:
    """Whole words; a short alias like "WD" only in the same case, so it isn't any "wd"."""
    if not text:
        return False
    return any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", text, 0 if len(w) <= 3 else re.I) for w in words)


def _blurb(body: str) -> str:
    """The note's first paragraph of prose, links unwrapped."""
    for block in re.split(r"\n\s*\n", body or ""):
        text = block.strip()
        if not text or text.startswith(("#", "---", "- ", "* ", "|", "```", ">")):
            continue
        text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
        text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
        return re.sub(r"\s+", " ", text)[:600]
    return ""


async def overview(hub: Hub, today: date | None = None) -> dict[str, Any]:
    """Every project with what's due, how quiet it's been and its open tasks."""
    today = today or tasks.today()
    listed, insights, vault = await asyncio.gather(
        _listed(hub),
        sirisai_api.get(hub, "/siris/brain/insights", params={"days": 30}),
        sirisai_api.get(hub, "/siris/brain/tasks"),
    )
    if listed is None:
        return {"projects": [], "available": False}
    deadlines = {d.get("title"): d for d in (insights or {}).get("deadlines") or [] if isinstance(d, dict)}
    quiet = {p.get("title"): p.get("days_idle") for p in (insights or {}).get("stale_projects") or [] if isinstance(p, dict)}
    open_tasks: dict[str, int] = {}
    for t in (vault or {}).get("tasks") or []:
        open_tasks[t.get("note")] = open_tasks.get(t.get("note"), 0) + 1
    out = []
    for p in listed:
        d = deadlines.get(p["title"]) or {}
        out.append({**p, "due": d.get("due"), "days_left": d.get("days_left"), "days_idle": quiet.get(p["title"]),
                    "open_tasks": open_tasks.get(p["title"], 0)})

    def order(p: dict[str, Any]) -> tuple:
        done = p["status"] in ("done", "finished", "archived", "complete", "completed")
        return (done, p["days_left"] is None, p["days_left"] if p["days_left"] is not None else 0, p["title"].lower())

    return {"projects": sorted(out, key=order), "available": True, "date": today.isoformat()}


async def page(hub: Hub, title: str, today: date | None = None) -> dict[str, Any]:
    today = today or tasks.today()
    listed = await _listed(hub)
    if listed is None:
        raise NotFound("Siris isn't reachable.")
    project = next((p for p in listed if p["title"].lower() == title.lower()), None)
    if project is None:
        raise NotFound(title)
    words = names(project)
    note, insights, todo, vault, cal = await asyncio.gather(
        sirisai_api.get(hub, "/siris/brain/note", params={"title": project["title"]}),
        sirisai_api.get(hub, "/siris/brain/insights", params={"days": 30}),
        tasks.collect(hub, today),
        sirisai_api.get(hub, "/siris/brain/tasks"),
        calendar.events(hub, today - timedelta(days=14), today + timedelta(days=31)),
    )
    unavailable = ["note"] if note is None else []
    if cal["events"] is None and not cal["guest_mode"]:
        unavailable.append("calendar")

    own = [t for group in todo["groups"].values() for t in group if mentions(t["title"], words) or mentions(t.get("detail"), words)]
    in_note = [{"id": tasks._key_siris(t), "source": "siris", "title": t.get("task"), "detail": t.get("note"),
                "note": t.get("note"), "due": t.get("due"), "time": None, "repeat": "none", "group": tasks.group_of(date.fromisoformat(t["due"]) if t.get("due") else None, today)}
               for t in (vault or {}).get("tasks") or [] if (t.get("note") or "").lower() == project["title"].lower()]
    open_tasks = in_note + own
    events = [e for e in cal["events"] or [] if mentions(e.get("title"), words) or mentions(e.get("location"), words)]
    start_today = today.isoformat()
    deadline = next((d for d in (insights or {}).get("deadlines") or [] if d.get("title") == project["title"]), None)
    meta = (note or {}).get("meta") or {}
    return {
        **project,
        "names": words,
        "about": _blurb((note or {}).get("body") or ""),
        "areas": meta.get("areas") or [],
        "source": meta.get("source"),
        "updated": (note or {}).get("as_of"),
        "links": (note or {}).get("links") or [],
        "backlinks": (note or {}).get("backlinks") or [],
        "deadline": deadline,
        "days_idle": next((p.get("days_idle") for p in (insights or {}).get("stale_projects") or [] if p.get("title") == project["title"]), None),
        "tasks": open_tasks,
        "meetings": {"upcoming": [e for e in events if (e.get("start") or "")[:10] >= start_today],
                     "recent": [e for e in reversed(events) if (e.get("start") or "")[:10] < start_today]},
        "guest_mode": bool(cal["guest_mode"]),
        "unavailable": unavailable,
    }


async def finish(hub: Hub, title: str) -> dict[str, Any]:
    """Mark the project itself done in Siris (its deadline and leftover tasks leave insights)."""
    return await sirisai_api.post(hub, "/siris/brain/done", json={"note": title})
