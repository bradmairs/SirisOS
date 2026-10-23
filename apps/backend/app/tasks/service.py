"""One task list (2.9) from three places:

- **SirisOS's own** tasks (tasks.json): added on the Tasks screen or by
  "remind me to…" in quick capture, with a due date, an optional time and a
  repeat. A repeating task moves to its next date when ticked.
- **Siris notes**: every open `- [ ]` task in the vault (SirisAI's
  /siris/brain/tasks). Ticking one ticks it in its note.
- **SirisAI reminders** ("remind me at 7" said to SirisAI). Ticking one
  cancels it.

Each comes back in one shape and in one of these groups: overdue, today,
this week, later or someday. Snoozing moves a task to a later day; for notes
and reminders that's remembered here, and their home is left as it is.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Any

from app.brief.service import zone
from app.hub import sirisai_api
from app.hub.service import Hub
from app.tasks import store

GROUPS = ("overdue", "today", "week", "later", "someday")
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def today() -> date:
    return datetime.now(zone()).date()


def group_of(due: date | None, on: date) -> str:
    if due is None:
        return "someday"
    if due < on:
        return "overdue"
    if due == on:
        return "today"
    if due <= on + timedelta(days=6):
        return "week"
    return "later"


# -- "remind me to…" ---------------------------------------------------------------

_LEAD = re.compile(r"^\s*(?:remind me to|remind me|todo:?|to do:?|task:?)\s+", re.I)
_TIME = re.compile(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b|\bat\s+(\d{1,2}):(\d{2})\b", re.I)
_REPEAT = re.compile(r"\b(every\s+(?:day|weekday|week|fortnight|month)|daily|weekly|fortnightly|monthly|on weekdays)\b", re.I)
_ON = re.compile(r"\b(?:on\s+)?(today|tonight|tomorrow|next week|this weekend|" + "|".join(WEEKDAYS) + r")\b", re.I)
_DATE = re.compile(r"\b(?:on\s+)?(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?\b")


def is_task_text(text: str) -> bool:
    return bool(_LEAD.match(text))


def parse(text: str, on: date | None = None) -> store.Task:
    """'remind me to call the plumber tomorrow at 9am' -> a task due tomorrow 09:00.
    Understands today/tonight/tomorrow/a weekday/next week/this weekend, d/m dates,
    a time (9am, 5:30pm, at 17:00) and every day/weekday/week/fortnight/month."""
    on = on or today()
    rest = _LEAD.sub("", text.strip())
    due: date | None = None
    at: str | None = None
    repeat: store.Repeat = "none"

    if m := _REPEAT.search(rest):
        word = m.group(1).lower()
        repeat = ("daily" if "day" in word and "week" not in word else "weekdays" if "weekday" in word else
                  "fortnightly" if "fortnight" in word else "monthly" if "month" in word else "weekly")
        rest = rest[:m.start()] + rest[m.end():]
        due = on
    if m := _TIME.search(rest):
        if m.group(1):
            hour, minute, mer = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower()
            hour = hour % 12 + (12 if mer == "pm" else 0)
        else:
            hour, minute = int(m.group(4)), int(m.group(5))
        if 0 <= hour < 24 and 0 <= minute < 60:
            at = f"{hour:02d}:{minute:02d}"
            rest = rest[:m.start()] + rest[m.end():]
            due = due or on
    if m := _ON.search(rest):
        word = m.group(1).lower()
        if word in ("today", "tonight"):
            due = on
            at = at or ("19:00" if word == "tonight" else None)
        elif word == "tomorrow":
            due = on + timedelta(days=1)
        elif word == "next week":
            due = on + timedelta(days=7 - on.weekday())
        elif word == "this weekend":
            due = on + timedelta(days=max(0, 5 - on.weekday()))
        else:
            ahead = (WEEKDAYS.index(word) - on.weekday()) % 7 or 7
            due = on + timedelta(days=ahead)
        rest = rest[:m.start()] + rest[m.end():]
    elif m := _DATE.search(rest):
        try:
            year = int(m.group(3)) if m.group(3) else on.year
            year += 2000 if year < 100 else 0
            due = date(year, int(m.group(2)), int(m.group(1)))
            if not m.group(3) and due < on:
                due = date(year + 1, due.month, due.day)
            rest = rest[:m.start()] + rest[m.end():]
        except ValueError:
            pass
    title = re.sub(r"\s{2,}", " ", rest).strip(" ,.-") or text.strip()
    return store.Task(title=title[:1].upper() + title[1:], due=due.isoformat() if due else None, time=at, repeat=repeat, created_at=store.now())


# -- the list ----------------------------------------------------------------------

def _key_siris(t: dict[str, Any]) -> str:
    return f"siris:{t.get('note')}|{t.get('task')}"


def _snoozed(doc: store.TasksDocument, key: str) -> date | None:
    o = doc.overlays.get(key)
    return date.fromisoformat(o.snoozed_until) if o and o.snoozed_until else None


async def collect(hub: Hub, on: date | None = None) -> dict[str, Any]:
    """{groups: {overdue: [...], ...}, counts, sources: {siris, reminders}}.
    A source that didn't answer is marked False in `sources`, and the rest still show."""
    on = on or today()
    doc = store.load()
    items: list[dict[str, Any]] = []

    for t in doc.tasks:
        if t.done_at:
            continue
        due = date.fromisoformat(t.due) if t.due else None
        items.append({"id": f"sirisos:{t.id}", "source": "sirisos", "title": t.title, "detail": t.notes or None,
                      "due": t.due, "time": t.time, "repeat": t.repeat, "group": group_of(due, on)})

    vault = await sirisai_api.get(hub, "/siris/brain/tasks")
    for t in (vault or {}).get("tasks") or []:
        key = _key_siris(t)
        snooze = _snoozed(doc, key)
        due = date.fromisoformat(t["due"]) if t.get("due") else None
        shown = max(due, snooze) if (due and snooze) else (snooze or due)
        items.append({"id": key, "source": "siris", "title": t.get("task"), "detail": t.get("note"), "due": t.get("due"),
                      "time": None, "repeat": "none", "group": group_of(shown, on), "snoozed_until": snooze.isoformat() if snooze else None,
                      "note": t.get("note")})

    reminders = await sirisai_api.get(hub, "/siris/hub/v1/reminders")
    for r in (reminders or {}).get("reminders") or []:
        try:
            local = datetime.fromisoformat(str(r["due_at"]).replace("Z", "+00:00")).astimezone(zone())
        except ValueError:
            continue
        key = f"reminder:{r['id']}"
        snooze = _snoozed(doc, key)
        shown = max(local.date(), snooze) if snooze else local.date()
        items.append({"id": key, "source": "reminder", "title": r.get("message"), "detail": "SirisAI reminder",
                      "due": local.date().isoformat(), "time": local.strftime("%H:%M"), "repeat": "none", "group": group_of(shown, on)})

    def order(i: dict[str, Any]) -> tuple:
        return (i["due"] is None, i["due"] or "", i.get("time") or "99:99", (i["title"] or "").lower())

    groups = {g: sorted((i for i in items if i["group"] == g), key=order) for g in GROUPS}
    return {"date": on.isoformat(), "groups": groups, "counts": {g: len(v) for g, v in groups.items()},
            "sources": {"siris": vault is not None, "reminders": reminders is not None}}


def done_today(on: date | None = None) -> list[dict[str, Any]]:
    """SirisOS tasks ticked today (local), for the evening wrap-up."""
    on = on or today()
    out = []
    for t in store.load().tasks:
        if t.done_at and datetime.fromisoformat(t.done_at).astimezone(zone()).date() == on:
            out.append({"id": f"sirisos:{t.id}", "title": t.title})
    return out


# -- actions -------------------------------------------------------------------------

class NotFound(Exception):
    pass


def add(task: store.Task) -> store.Task:
    doc = store.load()
    task.created_at = task.created_at or store.now()
    doc.tasks.append(task)
    store.save(doc)
    return task


def _own(doc: store.TasksDocument, task_id: str) -> store.Task:
    found = next((t for t in doc.tasks if f"sirisos:{t.id}" == task_id), None)
    if found is None:
        raise NotFound(task_id)
    return found


def update(task_id: str, changes: dict[str, Any]) -> store.Task:
    doc = store.load()
    t = _own(doc, task_id)
    merged = store.Task.model_validate({**t.model_dump(), **{k: v for k, v in changes.items() if k in ("title", "due", "time", "notes", "repeat")}})
    doc.tasks = [merged if x.id == t.id else x for x in doc.tasks]
    store.save(doc)
    return merged


def delete(task_id: str) -> None:
    doc = store.load()
    t = _own(doc, task_id)
    doc.tasks = [x for x in doc.tasks if x.id != t.id]
    store.save(doc)


async def complete(hub: Hub, task_id: str, *, note: str | None = None, title: str | None = None) -> dict[str, Any]:
    """Tick a task wherever it lives. A repeating SirisOS task moves to its next date instead."""
    result = await _complete(hub, task_id, note=note, title=title)
    from app.trends import log

    log.task_done()  # the year view counts it (4.1)
    return result


async def _complete(hub: Hub, task_id: str, *, note: str | None = None, title: str | None = None) -> dict[str, Any]:
    if task_id.startswith("sirisos:"):
        doc = store.load()
        t = _own(doc, task_id)
        if t.repeat != "none":
            base = date.fromisoformat(t.due) if t.due else today()
            nxt = store.next_due(max(base, today()) if base < today() else base, t.repeat)
            t.due, t.reminded_for = nxt.isoformat(), None
            store.save(doc)
            return {"id": task_id, "action": "repeated", "next_due": t.due}
        t.done_at = store.now()
        store.save(doc)
        return {"id": task_id, "action": "done"}
    if task_id.startswith("siris:"):
        note_title, _, task_text = task_id[len("siris:"):].partition("|")
        result = await sirisai_api.post(hub, "/siris/brain/done", json={"note": note or note_title, "task": title or task_text})
        return {"id": task_id, "action": (result or {}).get("action", "done")}
    if task_id.startswith("reminder:"):
        await sirisai_api.post(hub, f"/siris/hub/v1/reminders/{task_id.split(':', 1)[1]}/done")
        return {"id": task_id, "action": "done"}
    raise NotFound(task_id)


def snooze(task_id: str, until: date) -> dict[str, Any]:
    doc = store.load()
    if task_id.startswith("sirisos:"):
        t = _own(doc, task_id)
        t.due, t.reminded_for = until.isoformat(), None
    else:
        doc.overlays[task_id] = store.Overlay(snoozed_until=until.isoformat())
    store.save(doc)
    return {"id": task_id, "snoozed_until": until.isoformat()}


def snooze_target(when: str, on: date | None = None) -> date:
    on = on or today()
    if when == "tomorrow":
        return on + timedelta(days=1)
    if when == "weekend":
        return on + timedelta(days=max(1, 5 - on.weekday()) if on.weekday() < 5 else 7)
    if when == "next-week":
        return on + timedelta(days=7 - on.weekday())
    return date.fromisoformat(when)


def due_now(now: datetime | None = None) -> list[store.Task]:
    """SirisOS tasks whose time has come and that haven't been notified yet (for push)."""
    now = (now or datetime.now(zone())).astimezone(zone())
    out = []
    for t in store.load().tasks:
        if t.done_at or not t.due or not t.time:
            continue
        at = datetime.combine(date.fromisoformat(t.due), time.fromisoformat(t.time), zone())
        if at <= now < at + timedelta(hours=6) and t.reminded_for != f"{t.due}T{t.time}":
            out.append(t)
    return out


def mark_reminded(task_ids: list[str]) -> None:
    doc = store.load()
    for t in doc.tasks:
        if t.id in task_ids:
            t.reminded_for = f"{t.due}T{t.time}"
    store.save(doc)
