"""Meeting prep (3.2): before a meeting, what Siris knows about it and the
latest emails from the people in it; after it, a notes box that files into
Siris, with `- [ ]` lines turned into tasks.

Notes come from SirisAI's brain search (the meeting's title words and the
attendees' names); emails from /siris/hub/v1/email/with, using the
attendees on the calendar event (SirisAI 2.14). Nothing is sent anywhere
except the notes you save.
"""

from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta
from typing import Any

from app.brief.service import zone
from app.calendar import service as calendar
from app.hub import sirisai_api
from app.hub.service import Hub
from app.tasks import service as tasks
from app.tasks import store as task_store

STOP = {"the", "and", "for", "with", "meeting", "catch", "up", "catchup", "call", "chat", "sync", "weekly", "monthly", "re", "of", "to",
        "a", "an", "on", "in", "at", "review", "discussion", "online", "teams", "zoom", "meet", "-", "&"}
_cache: dict[str, tuple[float, Any]] = {}
CACHE_SECONDS = 300


def name_of(address: str) -> str:
    """dana.lee@example.com -> Dana Lee."""
    local = address.split("@", 1)[0]
    parts = [p for p in re.split(r"[._\-+]+", local) if p and not p.isdigit()]
    return " ".join(p.capitalize() for p in parts) or address


def keywords(title: str) -> str:
    words = [w for w in re.findall(r"[A-Za-z0-9][\w'-]*", title) if w.lower() not in STOP and len(w) > 2]
    return " ".join(words[:6])


async def _events(hub: Hub, start: date, days: int) -> list[dict[str, Any]]:
    key = f"{start.isoformat()}:{days}"
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    cal = await calendar.events(hub, start, start + timedelta(days=days))
    events = [e for e in cal["events"] or [] if not e.get("all_day") and "T" in str(e.get("start") or "")]
    _cache[key] = (time.monotonic(), events)
    return events


async def upcoming(hub: Hub, now: datetime | None = None) -> list[dict[str, Any]]:
    """Today's and tomorrow's timed meetings that haven't ended."""
    now = (now or datetime.now(zone())).astimezone(zone())
    out = []
    for e in await _events(hub, now.date(), 2):
        try:
            end = datetime.fromisoformat(str(e.get("end") or e.get("start")))
        except ValueError:
            continue
        if end.astimezone(zone()) >= now:
            out.append({"title": e.get("title"), "start": e.get("start"), "end": e.get("end"), "location": e.get("location"),
                        "attendees": e.get("attendees") or []})
    return out


async def find(hub: Hub, title: str, start: str | None) -> dict[str, Any] | None:
    day = date.fromisoformat(start[:10]) if start else datetime.now(zone()).date()
    for e in await _events(hub, day, 1):
        if e.get("title") == title and (not start or str(e.get("start"))[:16] == start[:16]):
            return e
    return None


async def prep(hub: Hub, title: str, start: str | None) -> dict[str, Any]:
    event = await find(hub, title, start) or {"title": title, "start": start, "attendees": []}
    attendees = [a for a in event.get("attendees") or [] if "@" in a]
    people = [{"email": a, "name": name_of(a)} for a in attendees]

    queries = [q for q in [keywords(title), *[p["name"] for p in people[:4] if " " in p["name"]]] if q]
    notes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for q in queries:
        for n in await sirisai_api.get(hub, "/siris/brain/search", params={"q": q, "limit": 4}) or []:
            t = str(n.get("title"))
            if t not in seen:
                seen.add(t)
                notes.append({"title": t, "excerpt": next(iter(n.get("excerpts") or []), ""), "type": n.get("type")})
    emails = None
    if attendees:
        found = await sirisai_api.get(hub, "/siris/hub/v1/email/with", params=[("address", a) for a in attendees[:8]] + [("limit", 5)])
        emails = (found or {}).get("messages")

    words = {w.lower() for w in keywords(title).split()}
    listing = await tasks.collect(hub)
    related = [t for g in listing["groups"].values() for t in g
               if words & {w.lower() for w in re.findall(r"[\w'-]+", f"{t['title']} {t.get('detail') or ''}")}][:6]
    return {
        "title": title, "start": event.get("start"), "end": event.get("end"), "location": event.get("location"),
        "found": "end" in event, "people": people, "notes": notes[:8], "emails": emails, "tasks": related,
    }


_TASK_LINE = re.compile(r"^\s*(?:[-*]\s*\[\s?\]\s*|todo:?\s+|action:?\s+)(.+)$", re.I)


async def save_notes(hub: Hub, title: str, start: str | None, text: str) -> dict[str, Any]:
    """File the notes into Siris; each `- [ ] …`, `todo …` or `action …` line also becomes a task."""
    day = (start or datetime.now(zone()).isoformat())[:10]
    made = []
    for line in text.splitlines():
        m = _TASK_LINE.match(line)
        if m and m.group(1).strip():
            t = tasks.parse(m.group(1).strip())
            t.notes = f"From {title} ({day})"
            made.append(tasks.add(t).title)
    saved = await sirisai_api.post(hub, "/siris/brain/capture", json={
        "title": f"Meeting: {title} ({day})", "text": text.strip(), "tags": ["meeting"]})
    return {"saved_as": (saved or {}).get("title") or f"Meeting: {title} ({day})", "tasks": made}


async def push_messages(hub: Hub, now: datetime) -> list[dict[str, Any]]:
    """'In 10 minutes: …' for a meeting with people in it, once."""
    now = now.astimezone(zone())
    out = []
    for e in await _events(hub, now.date(), 1):
        try:
            start = datetime.fromisoformat(str(e["start"])).astimezone(zone())
        except (KeyError, ValueError):
            continue
        if timedelta(0) < start - now <= timedelta(minutes=10) and e.get("attendees"):
            from urllib.parse import quote

            out.append({"key": f"meeting:{e.get('title')}:{e['start']}", "topic": "inbox", "title": f"In {max(1, int((start - now).total_seconds() // 60))} min: {e.get('title')}",
                        "body": "Your prep is ready: notes and the latest emails from the people in it.",
                        "url": f"/meeting?title={quote(str(e.get('title')))}&start={quote(str(e['start']))}", "urgency": "normal"})
    return out
