"""Resurfacing (5.1): one older Siris note a day, related to what you're
working on, so the useful ones don't get buried.

What you're working on: your personal projects, your open tasks, and
what's on your calendar today and tomorrow. Each becomes a search of the
brain. A note qualifies when its last update (its `as_of`: the newest
dated update, `updated` or `created`) is at least 30 days old, it wasn't
shown in the last 90 days, and you haven't said it's not useful. It isn't
one of the projects you searched for, a daily note, dashboard or template,
or a work note (SirisOS keeps work out, as Projects does). The best match wins, and it's kept for the rest of the day.
"Not useful" never shows it again and picks another; "Seen it" just
closes it for today.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any

from app.calendar import service as calendar
from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store
from app.siris_projects import service as projects
from app.tasks import service as tasks
from app.tasks import store as task_store

MIN_AGE_DAYS = 30
REST_DAYS = 90
SKIP_TYPES = {"daily", "dashboard", "template", "templates"}
SKIP_FOLDERS = ("Daily/", "Templates/", "00-Inbox/", "Work/")  # work has its own apps


def _path():
    return json_store.data_path("SIRISOS_RESURFACE_PATH", "resurface.json")


def _load() -> dict[str, Any]:
    doc = json_store.read(_path(), {})
    doc = doc if isinstance(doc, dict) else {}
    doc.setdefault("days", {})
    doc.setdefault("shown", {})
    doc.setdefault("dismissed", [])
    return doc


def _save(doc: dict[str, Any], today: date) -> None:
    keep_from = (today - timedelta(days=REST_DAYS)).isoformat()
    doc["days"] = {d: v for d, v in doc["days"].items() if d >= keep_from}
    doc["shown"] = {t: d for t, d in doc["shown"].items() if d >= keep_from}
    doc["dismissed"] = doc["dismissed"][-500:]
    json_store.write(_path(), doc)


async def _context(hub: Hub, today: date) -> list[tuple[str, str]]:
    """(query, why) pairs: what you're working on."""
    out: list[tuple[str, str]] = []
    listed = await projects._listed(hub)  # noqa: SLF001 - the same personal-project filter
    for p in (listed or [])[:12]:
        if (p.get("status") or "active") in ("active", ""):
            out.append((p["title"], f"Related to your project {p['title']}"))
    open_tasks = [t for t in task_store.load().tasks if not t.done_at]
    for t in open_tasks[:5]:
        out.append((t.title, f"Related to your task “{t.title}”"))
    cal = await calendar.events(hub, today, today + timedelta(days=1))
    for e in (cal.get("events") or [])[:5]:
        title = str(e.get("summary") or e.get("title") or "").strip()
        if len(title) >= 4 and not projects.mentions(title, projects._excluded_words()):  # noqa: SLF001
            out.append((title, f"Related to “{title}” on your calendar"))
    return out


def _skip(hit: dict[str, Any], context_titles: set[str], doc: dict[str, Any], today: date) -> bool:
    title = str(hit.get("title") or "")
    if not title or title.lower() in context_titles or title in doc["dismissed"]:
        return True
    if str(hit.get("type") or "").lower() in SKIP_TYPES or str(hit.get("path") or "").startswith(SKIP_FOLDERS):
        return True
    last = doc["shown"].get(title)
    return bool(last and last >= (today - timedelta(days=REST_DAYS)).isoformat() and last != today.isoformat())


async def pick(hub: Hub, today: date | None = None, exclude: set[str] | None = None) -> dict[str, Any] | None:
    today = today or tasks.today()
    doc = _load()
    exclude = exclude or set()
    context = await _context(hub, today)
    if not context:
        return None
    context_titles = {q.lower() for q, _ in context}
    results = await asyncio.gather(*(sirisai_api.get(hub, "/siris/brain/search", params={"q": q, "limit": 6}) for q, _ in context))
    candidates: dict[str, dict[str, Any]] = {}
    for (query, why), hits in zip(context, results):
        for rank, hit in enumerate(hits if isinstance(hits, list) else []):
            if not isinstance(hit, dict) or hit.get("title") in exclude or _skip(hit, context_titles, doc, today):
                continue
            score = float(hit.get("score") or 0) or (6 - rank)
            c = candidates.setdefault(hit["title"], {"hit": hit, "score": 0.0, "why": why})
            c["score"] += score
    for c in sorted(candidates.values(), key=lambda c: c["score"], reverse=True)[:8]:
        hit = c["hit"]
        note = await sirisai_api.get(hub, "/siris/brain/note", params={"title": hit["title"]})
        as_of = str((note or {}).get("as_of") or "")[:10]
        try:
            age = (today - date.fromisoformat(as_of)).days if as_of else None
        except ValueError:
            age = None
        if age is not None and age < MIN_AGE_DAYS:
            continue
        excerpts = [e for e in hit.get("excerpts") or [] if isinstance(e, str)]
        chosen = {
            "date": today.isoformat(), "title": hit["title"], "path": hit.get("path"), "tags": hit.get("tags") or [],
            "excerpt": (excerpts[0] if excerpts else projects._blurb(str((note or {}).get("body") or "")))[:400],  # noqa: SLF001
            "why": c["why"], "as_of": as_of or None, "age_days": age,
        }
        doc["days"][today.isoformat()] = chosen
        doc["shown"][hit["title"]] = today.isoformat()
        _save(doc, today)
        return chosen
    return None


async def today_note(hub: Hub, today: date | None = None) -> dict[str, Any]:
    today = today or tasks.today()
    kept = _load()["days"].get(today.isoformat())
    if kept is not None:
        return {"note": kept or None}
    chosen = await pick(hub, today)
    if chosen is None:
        doc = _load()
        doc["days"][today.isoformat()] = {}  # nothing today: don't search again on every visit
        _save(doc, today)
    return {"note": chosen}


async def respond(hub: Hub, title: str, answer: str, today: date | None = None) -> dict[str, Any]:
    """"not_useful": never again, and another for today. "seen": closed for today."""
    today = today or tasks.today()
    doc = _load()
    current = doc["days"].get(today.isoformat()) or {}
    if answer == "not_useful":
        if title not in doc["dismissed"]:
            doc["dismissed"].append(title)
        doc["days"].pop(today.isoformat(), None)
        _save(doc, today)
        chosen = await pick(hub, today, exclude={title})
        if chosen is None:
            doc = _load()
            doc["days"][today.isoformat()] = {}
            _save(doc, today)
        return {"note": chosen}
    if current.get("title") == title:
        doc["days"][today.isoformat()] = {**current, "seen": True}
        _save(doc, today)
    return {"note": None}
