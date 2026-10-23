"""Talk to SirisOS (4.3): one sentence, spoken or typed, does the thing.

What SirisOS can do itself, it does, quickly and the same way every time:

- **a task**: "add a task to call the plumber Friday", "remind me to put the
  bins out tonight"
- **CPD**: "log 1.5 hours CPD for today's stormwater webinar" adds a task to
  log it in Engineers Australia tomorrow (the hours themselves come from the
  EA export, as with the wrap-up)
- **the calendar**: "what's on tomorrow", "what's on today", "what's on
  Friday"
- **a note for Siris**: "note: the Werribee levels are in the shared drive"

Anything else is a question for SirisAI, answered in a sentence or two.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from app.brief.service import zone
from app.calendar import service as calendar
from app.hub import sirisai_api
from app.hub.service import Hub, shared_client
from app.tasks import service as tasks
from app.tasks import store as task_store

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

TASK = re.compile(r"^\s*(?:(?:please\s+)?add\s+(?:a\s+)?(?:task|to-?do)\s+(?:to\s+)?|new\s+task:?\s+|(?=remind me\b|todo\b|to do\b|task:))", re.I)
CPD = re.compile(r"^\s*(?:log|record|add)\s+(\d+(?:\.\d+)?|an?|one|half an?)\s*(?:hours?|hrs?|h)\b(?:\s+of)?\s+(?:cpd|professional development)\s*(?:for|on|from|:)?\s*(.*)$", re.I)
WHATS_ON = re.compile(r"^\s*(?:what(?:'s| is)|whats|what do i have|anything)\s+(?:on|happening|in my calendar|on my calendar)?\s*(today|tonight|tomorrow|this afternoon|this morning|on\s+\w+day|\w+day)?\s*\??\s*$", re.I)
NOTE = re.compile(r"^\s*(?:note|capture|remember(?: that)?|jot down)\s*:?\s+(.+)$", re.I | re.S)


def _hours(word: str) -> float:
    w = word.lower()
    if w in ("a", "an", "one"):
        return 1.0
    if w.startswith("half"):
        return 0.5
    return float(w)


def _day_of(word: str | None, today: date) -> tuple[date, str]:
    w = (word or "today").lower().removeprefix("on ").strip()
    if w in ("today", "tonight", "this afternoon", "this morning"):
        return today, "today"
    if w == "tomorrow":
        return today + timedelta(days=1), "tomorrow"
    if w in WEEKDAYS:
        ahead = (WEEKDAYS.index(w) - today.weekday()) % 7
        return today + timedelta(days=ahead), "today" if ahead == 0 else w.capitalize()
    return today, "today"


def _when(task: task_store.Task, today: date) -> str:
    if not task.due:
        return ""
    d = date.fromisoformat(task.due)
    word = "today" if d == today else "tomorrow" if d == today + timedelta(days=1) else d.strftime("%A") if (d - today).days < 7 else d.strftime("%-d %B")
    return f", {word}" + (f" at {datetime.strptime(task.time, '%H:%M').strftime('%-I:%M %p').lower().replace(':00', '')}" if task.time else "")


async def _whats_on(hub: Hub, day: date, label: str) -> dict[str, Any]:
    found = await calendar.events(hub, day, day + timedelta(days=1))
    if found["guest_mode"]:
        return {"intent": "calendar", "reply": "Guest mode is on, so the calendar is hidden.", "link": None}
    if found["events"] is None:
        return {"intent": "calendar", "reply": "The calendar isn't answering right now.", "link": "/week"}
    events = [e for e in found["events"] if (e.get("start") or "")[:10] <= day.isoformat()]
    if not events:
        return {"intent": "calendar", "reply": f"Nothing in the calendar {'for ' if label not in ('today', 'tomorrow') else ''}{label}.", "link": "/week"}
    parts = []
    for e in events[:6]:
        start = e.get("start") or ""
        if e.get("all_day") or len(start) <= 10:
            parts.append(f"{e['title']} (all day)")
        else:
            at = datetime.fromisoformat(start).astimezone(zone())
            parts.append(f"{at.strftime('%-I:%M %p').lower().replace(':00', '')} {e['title']}")
    more = f", and {len(events) - 6} more" if len(events) > 6 else ""
    return {"intent": "calendar", "reply": f"{label.capitalize()}: " + "; ".join(parts) + more + ".", "link": "/week", "events": events[:6]}


async def _ask(hub: Hub, text: str) -> dict[str, Any]:
    connector = sirisai_api.connector(hub)
    if connector is None:
        return {"intent": "ask", "reply": "SirisAI isn't connected, so I can only add tasks, notes and CPD reminders, and read the calendar.", "link": None}
    try:
        response = await shared_client().post(f"{connector.base_url}/siris/ask", headers=connector.headers(),
                                              json={"prompt": f"(Asked aloud through SirisOS: answer in one or two short sentences.) {text}"}, timeout=90.0)
    except httpx.HTTPError:
        return {"intent": "ask", "reply": "SirisAI didn't answer.", "link": "/assistant"}
    if response.status_code >= 400:
        return {"intent": "ask", "reply": f"SirisAI couldn't answer ({response.status_code}).", "link": "/assistant"}
    return {"intent": "ask", "reply": response.text.strip() or "SirisAI had nothing to say.", "link": "/assistant",
            "conversation_id": response.headers.get("x-conversation-id")}


async def run(hub: Hub, text: str, today: date | None = None) -> dict[str, Any]:
    """Do what `text` asks: {intent, reply (one or two sentences to say), link, ...}."""
    today = today or tasks.today()
    text = text.strip().rstrip(".")
    if m := CPD.match(text):
        hours, what = _hours(m.group(1)), (m.group(2) or "").strip(" .") or "CPD activity"
        what = re.sub(r"^(?:the|today'?s|this morning'?s|this afternoon'?s)\s+", "", what, flags=re.I)
        task = tasks.add(task_store.Task(title=f"Log “{what[:1].upper() + what[1:]}” ({hours:g} h) as CPD in Engineers Australia",
                                         due=(today + timedelta(days=1)).isoformat(), notes="Said to SirisOS", created_at=task_store.now()))
        return {"intent": "cpd", "reply": f"I'll remind you tomorrow to log {hours:g} hour{'s' if hours != 1 else ''} for {what} in Engineers Australia.",
                "link": "/career?view=cpd", "task": task.model_dump()}
    if TASK.match(text):
        task = tasks.parse(TASK.sub("", text, count=1), today)
        tasks.add(task)
        return {"intent": "task", "reply": f"Added: {task.title}{_when(task, today)}.", "link": "/tasks", "task": task.model_dump()}
    if m := WHATS_ON.match(text):
        day, label = _day_of(m.group(1), today)
        return await _whats_on(hub, day, label)
    if m := NOTE.match(text):
        body = m.group(1).strip()
        try:
            saved = await sirisai_api.post(hub, "/siris/brain/capture", json={"text": body, "tags": ["voice"]})
        except sirisai_api.SirisAIError as exc:
            return {"intent": "note", "reply": f"Couldn't save that to Siris: {exc}", "link": None}
        return {"intent": "note", "reply": "Saved to Siris.", "link": "/brain", "title": (saved or {}).get("title")}
    return await _ask(hub, text)
