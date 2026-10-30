"""The evening wrap-up (2.10): two minutes at the end of the day.

1. What got done today, and what's still open from today: tick it or move it
   to tomorrow (the Tasks list, app/tasks).
2. Today's meetings that look like CPD: "Log it" marks it and adds a task to
   log it in Engineers Australia tomorrow (EA stays the only record); "Not
   CPD" stops it being suggested.
3. Tomorrow's top 3, saved as tasks due tomorrow and shown first in
   tomorrow's brief.
4. A line or two about the day. Each sentence goes to Siris as its own
   memory (SirisAI 2.66 `kind: "memory"`), filed overnight onto the note
   it's about ("Running", "SirisOS"...), or a new note when nothing fits.
   There's no day note: those cluttered the brain (4.4). Tomorrow's top 3
   stay in SirisOS (5.61).

Saved per day in wrapup.json (60 days kept). A phone notification at
SIRISOS_WRAPUP_HOUR (17) offers it once, unless it's already done.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from typing import Any

from app.brief.service import zone
from app.calendar import service as calendar
from app.career import store as career_store
from app.career import suggest
from app.hub import sirisai_api
from app.hub.service import Hub
from app.services import json_store
from app.tasks import service as tasks
from app.tasks import store as task_store

KEEP_DAYS = 60


def _path():
    return json_store.data_path("SIRISOS_WRAPUP_PATH", "wrapup.json")


def _load() -> dict[str, Any]:
    return json_store.read(_path(), {})


def saved(day: date) -> dict[str, Any] | None:
    return _load().get(day.isoformat())


def top3_for(day: date) -> list[str]:
    """Tomorrow's top 3 as picked in the wrap-up the evening before `day`."""
    entry = saved(day - timedelta(days=1))
    return list((entry or {}).get("top3") or [])


def hour() -> int:
    try:
        return max(0, min(23, int(os.getenv("SIRISOS_WRAPUP_HOUR", "17"))))
    except ValueError:
        return 17


def _timed_today(events: list[dict[str, Any]] | None, day: date) -> list[dict[str, Any]]:
    out = []
    for e in events or []:
        start = str(e.get("start") or "")
        if e.get("all_day") or "T" not in start or start[:10] != day.isoformat():
            continue
        out.append(e)
    return out


async def overview(hub: Hub, day: date | None = None) -> dict[str, Any]:
    day = day or tasks.today()
    listing = await tasks.collect(hub, day)
    open_today = listing["groups"]["overdue"] + listing["groups"]["today"]
    tomorrow = day + timedelta(days=1)
    suggested_top3 = [t["title"] for t in listing["groups"]["week"] if t.get("due") == tomorrow.isoformat()][:3]

    cal = await calendar.events(hub, day, tomorrow)
    meetings = _timed_today(cal["events"], day)
    doc = career_store.load()
    cpd_keys = {s["key"]: s for s in suggest.suggestions(doc, meetings, day)}
    return {
        "date": day.isoformat(),
        "done": tasks.done_today(day),
        "open": open_today,
        "meetings": [{
            "title": e.get("title"), "start": e.get("start"), "end": e.get("end"), "location": e.get("location"),
            "cpd": cpd_keys.get(suggest.key(e)),
        } for e in meetings],
        "calendar_unavailable": cal["events"] is None,
        "suggested_top3": suggested_top3,
        "saved": saved(day),
    }


async def save(hub: Hub, day: date, top3: list[str], journal: str) -> dict[str, Any]:
    """Store the wrap-up; add the top 3 as tasks due tomorrow (once), and the
    line about the day to Siris."""
    tomorrow = (day + timedelta(days=1)).isoformat()
    picks = [t.strip() for t in top3 if t and t.strip()][:3]
    doc = task_store.load()
    have = {t.title.lower() for t in doc.tasks if not t.done_at}
    for title in picks:
        if title.lower() not in have:
            doc.tasks.append(task_store.Task(title=title, due=tomorrow, created_at=task_store.now(), notes="Top 3 for the day"))
        else:
            for t in doc.tasks:
                if not t.done_at and t.title.lower() == title.lower() and (not t.due or t.due > tomorrow):
                    t.due = tomorrow
    task_store.save(doc)

    line = journal.strip()
    journal_saved = await remember(hub, day, line)
    entry = {"top3": picks, "journal": line, "journal_saved_as": journal_saved,
             "at": datetime.now(zone()).isoformat(timespec="minutes")}
    state = _load()
    state[day.isoformat()] = entry
    cutoff = (day - timedelta(days=KEEP_DAYS)).isoformat()
    json_store.write(_path(), {k: v for k, v in state.items() if k >= cutoff})
    from app.trends import log

    log.mark("wrapup", day)
    if line:
        log.mark("journal", day)
    return entry


def sentences(text: str) -> list[str]:
    """The summary's sentences (and lines), each whole, nothing reworded."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p.strip(" -•\t") for p in parts if len(p.strip(" -•\t").split()) >= 2]


async def remember(hub: Hub, day: date, line: str) -> str | None:
    """The day's summary into Siris, one memory per sentence (5.61), so each is
    filed on its own: onto the existing note it's about, or as a new note when
    nothing fits (SirisAI's nightly filing). Tomorrow's top 3 stay in SirisOS
    (tasks and the brief); they don't go to Siris. "memories" when they went in."""
    stamp = day.strftime("%A %-d %B %Y")
    memories = [f"{stamp}: {s}" for s in sentences(line)]
    if not memories:
        return None
    try:
        for text in memories:
            await sirisai_api.post(hub, "/siris/brain/capture", json={"text": text, "kind": "memory", "tags": ["wrap-up"]})
    except sirisai_api.SirisAIError:
        return None
    return "memories"


def log_cpd(day: date, key: str, title: str, hours: float) -> dict[str, Any]:
    """Mark a meeting as CPD to log, and add a task to log it in Engineers Australia tomorrow."""
    doc = career_store.load()
    marks = dict(doc.cpd.suggestions)
    marks[key[:40]] = "logged"
    career_store.save(doc.model_copy(update={"cpd": doc.cpd.model_copy(update={"suggestions": dict(list(marks.items())[-500:])})}))
    task = tasks.add(task_store.Task(title=f"Log “{title}” ({hours:g} h) as CPD in Engineers Australia",
                                     due=(day + timedelta(days=1)).isoformat(), notes=f"From the {day.isoformat()} wrap-up"))
    return {"key": key, "task": task.model_dump()}


def push_message(now: datetime) -> list[dict[str, Any]]:
    """'Wrap up your day' once, from SIRISOS_WRAPUP_HOUR, unless it's been done."""
    local = now.astimezone(zone())
    if local.hour < hour() or saved(local.date()):
        return []
    return [{"key": f"wrapup:{local.date().isoformat()}", "topic": "brief", "title": "Wrap up your day",
             "body": "Two minutes: tick off what's done, pick tomorrow's top 3.", "url": "/wrapup", "urgency": "normal"}]
