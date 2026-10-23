"""Projects (4.0): one page per Siris project.

Siris (the vault, through SirisAI) knows the projects: every note of type
project (`/siris/brain/projects`), what's due and what's gone quiet
(insights), and the open tasks in each note. A project's page gathers what
SirisOS can find about it everywhere else, by its name and aliases:

- the note itself: what it's about, its links and what links to it
- open tasks: the note's own, plus SirisOS tasks and SirisAI reminders that
  name the project
- meetings: calendar events in the last fortnight and next month that name it
- emails: the latest with its name in the subject (SirisAI 2.25)

Every source fails alone; `unavailable` names the ones that didn't answer.
"""

from __future__ import annotations

import asyncio
import re
from datetime import date, timedelta
from typing import Any

from app.calendar import service as calendar
from app.hub import sirisai_api
from app.hub.service import Hub
from app.tasks import service as tasks


class NotFound(Exception):
    pass


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
        sirisai_api.get(hub, "/siris/brain/projects"),
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
    for p in listed.get("projects") or []:
        d = deadlines.get(p["title"]) or {}
        out.append({**p, "due": d.get("due"), "days_left": d.get("days_left"), "days_idle": quiet.get(p["title"]),
                    "open_tasks": open_tasks.get(p["title"], 0)})

    def order(p: dict[str, Any]) -> tuple:
        done = p["status"] in ("done", "finished", "archived", "complete", "completed")
        return (done, p["days_left"] is None, p["days_left"] if p["days_left"] is not None else 0, p["title"].lower())

    return {"projects": sorted(out, key=order), "available": True, "date": today.isoformat()}


async def page(hub: Hub, title: str, today: date | None = None) -> dict[str, Any]:
    today = today or tasks.today()
    listed = await sirisai_api.get(hub, "/siris/brain/projects")
    if listed is None:
        raise NotFound("Siris isn't reachable.")
    project = next((p for p in listed.get("projects") or [] if p["title"].lower() == title.lower()), None)
    if project is None:
        raise NotFound(title)
    words = names(project)
    note, insights, todo, cal, mail = await asyncio.gather(
        sirisai_api.get(hub, "/siris/brain/note", params={"title": project["title"]}),
        sirisai_api.get(hub, "/siris/brain/insights", params={"days": 30}),
        tasks.collect(hub, today),
        calendar.events(hub, today - timedelta(days=14), today + timedelta(days=31)),
        sirisai_api.get(hub, "/siris/hub/v1/email/about", params=[("q", w) for w in words if len(w) >= 4][:6] + [("limit", 6)]),
    )
    unavailable = [name for name, value in (("note", note), ("email", mail)) if value is None]
    if cal["events"] is None and not cal["guest_mode"]:
        unavailable.append("calendar")

    open_tasks = [t for group in todo["groups"].values() for t in group
                  if (t["source"] == "siris" and (t.get("note") or "").lower() == project["title"].lower())
                  or (t["source"] != "siris" and (mentions(t["title"], words) or mentions(t.get("detail"), words)))]
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
        "emails": (mail or {}).get("messages") or [],
        "email_configured": bool((mail or {}).get("configured")),
        "guest_mode": bool(cal["guest_mode"] or (mail or {}).get("guest_mode")),
        "unavailable": unavailable,
    }


async def finish(hub: Hub, title: str) -> dict[str, Any]:
    """Mark the project itself done in Siris (its deadline and leftover tasks leave insights)."""
    return await sirisai_api.post(hub, "/siris/brain/done", json={"note": title})
